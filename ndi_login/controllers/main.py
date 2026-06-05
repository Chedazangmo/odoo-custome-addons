import json
import logging
import requests
import uuid

from odoo import http, fields, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)

# =============================================================================
# NDI API ENDPOINTS
# =============================================================================
NDI_AUTH_URL      = "https://staging.bhutanndi.com/authentication/v1/authenticate"
NDI_PROOF_URL     = "https://demo-client.bhutanndi.com/verifier/v1/proof-request"
NDI_WEBHOOK_SUB   = "https://demo-client.bhutanndi.com/webhook/v1/subscribe"
NDI_WEBHOOK_UNSUB = "https://demo-client.bhutanndi.com/webhook/v1/unsubscribe"

NDI_SCHEMA_CID     = "https://dev-schema.ngotag.com/schemas/c7952a0a-e9b5-4a4b-a714-1e5d0a1ae076"
NDI_SCHEMA_MOBILE  = "https://dev-schema.ngotag.com/schemas/a2dcb671-3d64-47ec-ba59-97a3e642c724"
NDI_SCHEMA_EMAIL   = "https://dev-schema.ngotag.com/schemas/50add817-e7f1-4651-bd62-5471b2f5918f"
NDI_SCHEMA_ADDRESS = "https://dev-schema.ngotag.com/schemas/e3b606d0-e477-4fc2-b5ab-0adc4bd75c54"

PERM_ADDR_FIELDS = [
    "Dzongkhag",
    "Gewog",
    "Village",       # mapped → place_of_birth (City field) on hr.employee
    "House Number",
    "Thram Number",
]


# =============================================================================
# HELPERS
# =============================================================================
def _su_env():
    return request.env(user=SUPERUSER_ID)


def _param(key, default=''):
    return _su_env()['ir.config_parameter'].get_param(key, default)


def _set_param(key, value):
    _su_env()['ir.config_parameter'].set_param(key, value)


def _get_ndi_access_token():
    client_id     = _param('ndi_login.client_id')
    client_secret = _param('ndi_login.client_secret')
    if not client_id or not client_secret:
        raise ValueError("NDI credentials not configured in Settings > NDI Integration.")
    resp = requests.post(
        NDI_AUTH_URL,
        json={
            "client_id":     client_id,
            "client_secret": client_secret,
            "grant_type":    "client_credentials",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data  = resp.json()
    token = data.get('access_token') or data.get('token')
    if not token:
        raise ValueError("NDI auth response missing access_token: %s" % data)
    return token


def _create_proof_request(access_token):
    proof_attributes = [
        {"name": "ID Number",     "restrictions": [{"schema_name": NDI_SCHEMA_CID}]},
        {"name": "Full Name",     "restrictions": [{"schema_name": NDI_SCHEMA_CID}]},
        {"name": "Date of Birth", "restrictions": [{"schema_name": NDI_SCHEMA_CID}]},
        {"name": "Gender",        "restrictions": [{"schema_name": NDI_SCHEMA_CID}]},
        {"name": "Mobile Number", "restrictions": [{"schema_name": NDI_SCHEMA_MOBILE}]},
        {"name": "Email",         "restrictions": [{"schema_name": NDI_SCHEMA_EMAIL}]},
    ] + [
        {"name": field_name, "restrictions": [{"schema_name": NDI_SCHEMA_ADDRESS}]}
        for field_name in PERM_ADDR_FIELDS
    ]

    payload = {
        "proofName":           "Odoo PMS Login Verification",
        "purpose":             "login",
        "authenticationLevel": "Standard",
        "autoAcceptProof":     "true",
        "proofAttributes":     proof_attributes,
    }
    _logger.info("NDI proof payload: %s", json.dumps(payload))

    resp = requests.post(
        NDI_PROOF_URL,
        json=payload,
        headers={
            "Authorization": "Bearer %s" % access_token,
            "Content-Type":  "application/json",
        },
        timeout=15,
    )
    if not resp.ok:
        _logger.error("NDI proof request failed %s: %s", resp.status_code, resp.text)
    resp.raise_for_status()

    data       = resp.json()
    proof_data = data.get('data') or data
    thread_id  = proof_data.get('proofRequestThreadId') or proof_data.get('threadId')
    qr_url     = proof_data.get('proofRequestURL')      or proof_data.get('qrUrl')

    if not thread_id or not qr_url:
        raise ValueError("NDI proof response missing threadId or qrUrl: %s" % proof_data)

    return {
        "threadId":    thread_id,
        "qrUrl":       qr_url,
        "deepLinkUrl": proof_data.get('deepLinkURL') or proof_data.get('deepLinkUrl') or '',
    }


def _subscribe_webhook(access_token, thread_id):
    webhook_id = _param('ndi_login.webhook_id', 'odoo-ndi-webhook')
    resp = requests.post(
        NDI_WEBHOOK_SUB,
        json={"webhookId": webhook_id, "threadId": thread_id},
        headers={"Authorization": "Bearer %s" % access_token},
        timeout=10,
    )
    if not resp.ok:
        _logger.warning("NDI webhook subscribe %s: %s", resp.status_code, resp.text)
    resp.raise_for_status()


def _unsubscribe_webhook(access_token, thread_id):
    try:
        requests.post(
            NDI_WEBHOOK_UNSUB,
            json={"threadId": thread_id},
            headers={"Authorization": "Bearer %s" % access_token},
            timeout=10,
        )
    except Exception as e:
        _logger.warning("NDI unsubscribe failed for %s: %s", thread_id, e)


def _attr(revealed, self_attested, key):
    val = (revealed.get(key) or [{}])[0].get('value', '') or ''
    if not val:
        val = (self_attested.get(key) or [{}])[0].get('value', '') or ''
    val = val.strip() if val else ''
    if not val:
        _logger.debug("NDI ATTR: '%s' not found in proof response", key)
    return val


# =============================================================================
# CID VERIFICATION
# =============================================================================

def _normalize_cid(cid):
    if not cid:
        return ''
    return ''.join(filter(str.isdigit, cid.strip()))


def _verify_cid_against_employee(id_number):
    env       = _su_env()
    Employee  = env['hr.employee']
    ndi_cid   = (id_number or '').strip()
    ndi_cid_n = _normalize_cid(ndi_cid)

    all_emps = Employee.search([('active', '=', True)], limit=50)
    db_cids  = [(e.id, e.name, e.cid_number) for e in all_emps]
    _logger.info(
        "NDI CID VERIFY: NDI CID='%s' (normalized='%s') | DB employees: %s",
        ndi_cid, ndi_cid_n, db_cids
    )

    employee = Employee.search([
        ('cid_number', '=', ndi_cid), ('active', '=', True),
    ], limit=1)
    if employee:
        _logger.info("NDI CID VERIFY: exact match → employee id=%s name='%s'",
                     employee.id, employee.name)
        return employee

    if ndi_cid_n and ndi_cid_n != ndi_cid:
        employee = Employee.search([
            ('cid_number', '=', ndi_cid_n), ('active', '=', True),
        ], limit=1)
        if employee:
            _logger.info("NDI CID VERIFY: normalized match → employee id=%s", employee.id)
            return employee

    _logger.warning(
        "NDI CID VERIFY: NO MATCH for CID='%s'. DB CIDs: %s",
        ndi_cid, [e[2] for e in db_cids]
    )
    raise ValueError("CID '%s' is not registered to any active employee." % ndi_cid)


# =============================================================================
# USER FIND / CREATE
# =============================================================================

def _get_or_create_user(ndi_data):
    id_number = ndi_data.get('id_number', '').strip()
    full_name = ndi_data.get('full_name', '').strip()
    email     = ndi_data.get('email',    '').strip()
    now       = fields.Datetime.now()

    if not id_number:
        raise ValueError("NDI: ID Number (CID) is required but was not returned.")

    env      = _su_env()
    employee = _verify_cid_against_employee(id_number)
    user     = employee.user_id

    if user:
        _logger.info("NDI AUTH: employee id=%s → linked user uid=%s", employee.id, user.id)
        update_vals = {'ndi_verified': True, 'ndi_last_login': now}
        if email and user.email != email:
            update_vals['email'] = email
        user.write(update_vals)
        return user, False

    _logger.info("NDI AUTH: employee id=%s has no linked user — creating.", employee.id)
    legacy_login = 'ndi_%s' % id_number
    login        = email if email else legacy_login
    Users        = env['res.users']
    user         = Users.search([('login', '=', login)], limit=1)

    if not user:
        user = Users.with_context(no_reset_password=True).create({
            'name':           full_name or employee.name,
            'login':          login,
            'email':          email or ('%s@ndi.bt' % legacy_login),
            'password':       str(uuid.uuid4()),
            'ndi_cid':        id_number,
            'ndi_verified':   True,
            'ndi_last_login': now,
            'active':         True,
        })
        internal_group = env.ref('base.group_user', raise_if_not_found=False)
        if internal_group:
            user.write({'group_ids': [(4, internal_group.id)]})
    else:
        user.write({'ndi_verified': True, 'ndi_last_login': now})

    employee.write({'user_id': user.id})
    return user, True


# =============================================================================
# EMPLOYEE SYNC  (Odoo 19)
# =============================================================================

def _sync_employee(user, ndi_data):
    env = _su_env()

    if 'hr.employee' not in env:
        _logger.error("NDI SYNC: hr.employee model not found!")
        return None

    employee = env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
    if not employee:
        _logger.info("NDI SYNC: no employee linked to uid=%s, skipping", user.id)
        return None

    available_fields = list(employee._fields.keys())
    _logger.info(
        "NDI SYNC: employee id=%s — relevant fields present: "
        "gender=%s place_of_birth=%s birthday=%s "
        "private_phone=%s private_email=%s mobile_phone=%s",
        employee.id,
        'gender'          in available_fields,
        'place_of_birth'  in available_fields,
        'birthday'        in available_fields,
        'private_phone'   in available_fields,
        'private_email'   in available_fields,
        'mobile_phone'    in available_fields,
    )

    full_name = ndi_data.get('full_name',    '').strip()
    dob       = ndi_data.get('dob',          '').strip()
    gender    = ndi_data.get('gender',       '').strip()
    phone     = ndi_data.get('phone',        '').strip()
    email     = ndi_data.get('email',        '').strip()
    dzongkhag = ndi_data.get('dzongkhag',    '').strip()
    gewog     = ndi_data.get('gewog',        '').strip()
    village   = ndi_data.get('village',      '').strip()
    house_no  = ndi_data.get('house_number', '').strip()
    thram_no  = ndi_data.get('thram_number', '').strip()

    _logger.info(
        "NDI SYNC: raw NDI values for employee id=%s — "
        "full_name='%s' dob='%s' gender='%s' phone='%s' "
        "email='%s' village='%s' dzongkhag='%s'",
        employee.id, full_name, dob, gender, phone, email, village, dzongkhag
    )

    vals = {}

    if full_name and 'name' in employee._fields:
        vals['name'] = full_name
        if user.name != full_name:
            user.write({'name': full_name})

    if dob and 'birthday' in employee._fields:
        from datetime import datetime as dt
        parsed_dob = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
            try:
                parsed_dob = dt.strptime(dob, fmt).date()
                break
            except ValueError:
                continue
        if parsed_dob:
            vals['birthday'] = parsed_dob
            _logger.info("NDI SYNC: birthday='%s' for employee id=%s", parsed_dob, employee.id)
        else:
            _logger.warning(
                "NDI SYNC: could not parse DOB='%s' for employee id=%s", dob, employee.id
            )

    if gender and 'gender' in employee._fields:
        g = gender.strip().lower()
        mapped = g if g in ('male', 'female', 'other') else 'other'
        vals['gender'] = mapped
        _logger.info(
            "NDI SYNC: gender NDI='%s' → Odoo='%s' for employee id=%s",
            gender, mapped, employee.id
        )
    else:
        _logger.warning(
            "NDI SYNC: gender='%s' skipped — "
            "field present=%s for employee id=%s",
            gender, 'gender' in employee._fields, employee.id
        )

    if village and 'place_of_birth' in employee._fields:
        vals['place_of_birth'] = village
        _logger.info(
            "NDI SYNC: place_of_birth='%s' (NDI Village) for employee id=%s",
            village, employee.id
        )
    else:
        _logger.warning(
            "NDI SYNC: place_of_birth skipped — "
            "village='%s' field present=%s for employee id=%s",
            village, 'place_of_birth' in employee._fields, employee.id
        )

    if phone and 'private_phone' in employee._fields:
        vals['private_phone'] = phone
        _logger.info(
            "NDI SYNC: private_phone='%s' for employee id=%s", phone, employee.id
        )
    else:
        _logger.warning(
            "NDI SYNC: private_phone skipped — "
            "phone='%s' field present=%s for employee id=%s",
            phone, 'private_phone' in employee._fields, employee.id
        )

    if phone and 'mobile_phone' in employee._fields:
        vals['mobile_phone'] = phone

    if email and 'private_email' in employee._fields:
        if not employee.private_email:
            vals['private_email'] = email

    if email and 'work_email' in employee._fields:
        if not employee.work_email:
            vals['work_email'] = email

    addr_lines = []
    if dzongkhag: addr_lines.append('Dzongkhag   : %s' % dzongkhag)
    if gewog:     addr_lines.append('Gewog        : %s' % gewog)
    if village:   addr_lines.append('Village      : %s' % village)
    if house_no:  addr_lines.append('House No.    : %s' % house_no)
    if thram_no:  addr_lines.append('Thram No.    : %s' % thram_no)

    if addr_lines and 'notes' in employee._fields:
        import re
        addr_block    = 'Permanent Address (NDI):\n' + '\n'.join(addr_lines)
        existing      = (employee.notes or '').strip()
        cleaned       = re.sub(
            r'Permanent Address \(NDI\):.*?(?=\n\n|\Z)', '', existing, flags=re.DOTALL
        ).strip()
        vals['notes'] = (cleaned + '\n\n' + addr_block).strip() if cleaned else addr_block
        _logger.info(
            "NDI SYNC: address block for employee id=%s: %s",
            employee.id, ', '.join(addr_lines)
        )

    if vals:
        _logger.info(
            "NDI SYNC: writing to hr.employee id=%s — fields+values: %s",
            employee.id,
            {k: v for k, v in vals.items() if k != 'notes'}
        )
        employee.write(vals)
        _logger.info(
            "NDI SYNC: write complete for employee id=%s — updated: %s",
            employee.id, sorted(vals.keys())
        )
    else:
        _logger.warning(
            "NDI SYNC: vals dict is empty for employee id=%s — "
            "nothing was written. Check NDI returned values above.",
            employee.id
        )

    return employee


# =============================================================================
# SESSION
# =============================================================================

def _set_session(user):
    request.session.uid     = user.id
    request.session.login   = user.login
    request.session.db      = request.db
    request.session.context = dict(
        _su_env()['res.users'].browse(user.id).context_get()
    )
    try:
        request.session.finalize(request.env)
        _logger.info("NDI SESSION: finalized uid=%s login=%s", user.id, user.login)
    except Exception as e:
        _logger.warning("NDI SESSION: finalize() failed (%s) — using manual token", e)
        try:
            request.session.session_token = (
                _su_env()['res.users']
                .browse(user.id)
                ._compute_session_token(request.session.sid)
            )
        except Exception as e2:
            _logger.error("NDI SESSION: token fallback also failed: %s", e2)


def _get_post_login_redirect(user):
    """
    Determine the correct landing page after NDI login.
    - Avoids /odoo/discuss to prevent the Discuss dropdown leaking on the login page.
    - Sends admins to /odoo (backend home).
    - Sends portal/public users to /web/login (should not normally happen).
    """
    env = _su_env()
    try:
        portal_group   = env.ref('base.group_portal',  raise_if_not_found=False)
        internal_group = env.ref('base.group_user',    raise_if_not_found=False)
        is_internal    = internal_group and (internal_group in user.groups_id)
        is_portal      = portal_group   and (portal_group   in user.groups_id)

        if is_internal:
            return '/odoo'        # Odoo 17+ backend home — no Discuss dropdown issue
        if is_portal:
            return '/my'          # Portal home
    except Exception as e:
        _logger.warning("NDI REDIRECT: could not determine user group: %s", e)

    return '/odoo'                # Safe default


# =============================================================================
# CONTROLLER
# =============================================================================
class NDILoginController(http.Controller):

    # ── 0. ROOT REDIRECT  (http://localhost:8069 → /web/login) ────────────────
    @http.route('/', type='http', auth='none', sitemap=False, website=False)
    def root_redirect(self, **kw):
        """
        Redirect bare root URL to the login page.
        Prevents the Website homepage from loading when hitting localhost:8069.
        If the user already has a valid session, redirect to the backend instead.
        """
        if request.session.uid:
            _logger.info("ROOT REDIRECT: session uid=%s already set → /odoo", request.session.uid)
            return request.redirect('/odoo', code=302)
        _logger.info("ROOT REDIRECT: no session → /web/login")
        return request.redirect('/web/login', code=302)

    # ── 1. START ──────────────────────────────────────────────────────────────
    @http.route('/ndi/login/start', type='http', auth='none', csrf=False, website=False)
    def ndi_login_start(self, **kw):
        try:
            access_token = _get_ndi_access_token()
            proof        = _create_proof_request(access_token)
            thread_id    = proof['threadId']

            request.session['ndi_thread_id']    = thread_id
            request.session['ndi_access_token'] = access_token
            request.session['ndi_login_status'] = 'pending'

            _subscribe_webhook(access_token, thread_id)
            _logger.info("NDI START: webhook subscribed threadId=%s", thread_id)

            return _su_env()['ir.ui.view']._render_template(
                'ndi_login.ndi_qr_page',
                {
                    'qr_url':        proof['qrUrl'],
                    'deep_link_url': proof['deepLinkUrl'],
                    'thread_id':     thread_id,
                }
            )
        except Exception as e:
            _logger.error("NDI START failed: %s", e, exc_info=True)
            return request.redirect('/web/login?ndi_error=1')

    # ── 2. WEBHOOK ─────────────────────────────────────────────────────────────
    @http.route('/ndi/webhook', type='http', auth='none', csrf=False, methods=['POST'], website=False)
    def ndi_webhook(self, **kw):
        try:
            raw = request.httprequest.get_data(as_text=True)
            _logger.info("NDI WEBHOOK raw body: %s", raw)

            auth_header = request.httprequest.headers.get('Authorization', '')
            expected    = _param('ndi_login.webhook_token', '')
            if expected and auth_header != ("Bearer %s" % expected):
                _logger.warning("NDI WEBHOOK: invalid auth, rejecting")
                return request.make_response(
                    'Unauthorized', status=401,
                    headers=[('Content-Type', 'text/plain')]
                )

            payload = json.loads(raw) if raw else {}
            thid    = payload.get('thid') or payload.get('threadId')
            mtype   = payload.get('type', '')
            _logger.info("NDI WEBHOOK type=%s thid=%s", mtype, thid)

            if mtype == 'present-proof/presentation-result':
                revealed      = payload.get('requested_presentation', {}).get('revealed_attrs', {})
                self_attested = payload.get('requested_presentation', {}).get('self_attested_attrs', {})

                def a(key):
                    return _attr(revealed, self_attested, key)

                id_number = a('ID Number')
                full_name = a('Full Name')

                _logger.info(
                    "NDI WEBHOOK: CID='%s' name='%s' | "
                    "All revealed keys: %s | "
                    "All self-attested keys: %s",
                    id_number, full_name,
                    list(revealed.keys()),
                    list(self_attested.keys()),
                )

                if id_number:
                    proof_data = {
                        'status':       'validated',
                        'id_number':    id_number,
                        'full_name':    full_name,
                        'dob':          a('Date of Birth'),
                        'gender':       a('Gender'),
                        'phone':        a('Mobile Number'),
                        'email':        a('Email'),
                        'dzongkhag':    a('Dzongkhag'),
                        'gewog':        a('Gewog'),
                        'village':      a('Village'),
                        'house_number': a('House Number'),
                        'thram_number': a('Thram Number'),
                    }
                    _logger.info(
                        "NDI WEBHOOK: proof stored — "
                        "gender='%s' dob='%s' phone='%s' "
                        "village='%s' dzongkhag='%s'",
                        proof_data['gender'], proof_data['dob'],
                        proof_data['phone'],  proof_data['village'],
                        proof_data['dzongkhag'],
                    )
                    _set_param('ndi_proof_%s' % thid, json.dumps(proof_data))
                else:
                    _logger.warning("NDI WEBHOOK: no ID Number in proof thid=%s", thid)
                    if thid:
                        _set_param('ndi_proof_%s' % thid, json.dumps({'status': 'failed'}))

            elif mtype == 'present-proof/rejected':
                _logger.warning("NDI WEBHOOK: rejected thid=%s", thid)
                if thid:
                    _set_param('ndi_proof_%s' % thid, json.dumps({'status': 'failed'}))
            else:
                _logger.info("NDI WEBHOOK: unhandled type=%s", mtype)

            return request.make_response(
                json.dumps({"message": "Accepted"}), status=202,
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.error("NDI WEBHOOK error: %s", e, exc_info=True)
            return request.make_response(
                json.dumps({"message": "Accepted"}), status=202,
                headers=[('Content-Type', 'application/json')]
            )

    # ── 3. STATUS POLLING ──────────────────────────────────────────────────────
    @http.route('/ndi/login/status', type='jsonrpc', auth='none', csrf=False, website=False)
    def ndi_login_status(self, **kw):
        thread_id = request.session.get('ndi_thread_id')
        if not thread_id:
            return {'status': 'error', 'message': 'No active NDI session'}

        param_key = 'ndi_proof_%s' % thread_id
        raw       = _param(param_key)
        if not raw:
            return {'status': 'pending'}

        try:
            result = json.loads(raw)
        except Exception:
            return {'status': 'pending'}

        status = result.get('status')
        if status == 'failed':
            _set_param(param_key, False)
            return {'status': 'failed', 'message': 'Proof rejected or failed'}
        if status != 'validated':
            return {'status': 'pending'}

        finalize_token = str(uuid.uuid4())
        _set_param('ndi_finalize_%s' % finalize_token, json.dumps({
            'id_number':    result.get('id_number',    ''),
            'full_name':    result.get('full_name',    ''),
            'dob':          result.get('dob',          ''),
            'gender':       result.get('gender',       ''),
            'phone':        result.get('phone',        ''),
            'email':        result.get('email',        ''),
            'dzongkhag':    result.get('dzongkhag',    ''),
            'gewog':        result.get('gewog',        ''),
            'village':      result.get('village',      ''),
            'house_number': result.get('house_number', ''),
            'thram_number': result.get('thram_number', ''),
            'thread_id':    thread_id,
        }))
        _set_param(param_key, False)

        return {
            'status':   'validated',
            'redirect': '/ndi/login/finalize?token=%s' % finalize_token,
        }

    # ── 4. FINALIZE ────────────────────────────────────────────────────────────
    @http.route('/ndi/login/finalize', type='http', auth='none', csrf=False, website=False)
    def ndi_login_finalize(self, token=None, **kw):
        _logger.info("NDI FINALIZE token=%s", token)
        if not token:
            return request.redirect('/web/login?ndi_error=1')

        raw = _param('ndi_finalize_%s' % token)
        if not raw:
            return request.redirect('/web/login?ndi_error=1')

        _set_param('ndi_finalize_%s' % token, False)

        try:
            data = json.loads(raw)
        except Exception as e:
            _logger.error("NDI FINALIZE JSON error: %s", e)
            return request.redirect('/web/login?ndi_error=1')

        thread_id    = data.get('thread_id', '')
        access_token = request.session.get('ndi_access_token')

        request.session.pop('ndi_thread_id',    None)
        request.session.pop('ndi_access_token', None)
        request.session.pop('ndi_login_status', None)

        if access_token and thread_id:
            _unsubscribe_webhook(access_token, thread_id)

        try:
            user, is_new = _get_or_create_user(data)
            _logger.info("NDI FINALIZE: uid=%s is_new=%s", user.id, is_new)

            _set_session(user)

            try:
                emp = _sync_employee(user, data)
                if emp:
                    _logger.info("NDI FINALIZE: employee synced id=%s", emp.id)
            except Exception as se:
                _logger.error(
                    "NDI FINALIZE: sync failed (login still OK): %s", se, exc_info=True)

            # ── FIXED: redirect to backend home, NOT /odoo/discuss ────────────
            # Redirecting to /odoo/discuss was causing the Discuss dropdown to
            # leak back onto the login page when session cookies persisted.
            # _get_post_login_redirect() chooses /odoo for internal users.
            redirect_url = _get_post_login_redirect(user)
            _logger.info("NDI FINALIZE: redirecting uid=%s → %s", user.id, redirect_url)
            return request.redirect(redirect_url, code=303)

        except ValueError as ve:
            _logger.warning("NDI FINALIZE: CID verification failed — %s", ve)
            return request.redirect('/web/login?ndi_error=cid_not_found')

        except Exception as e:
            _logger.error("NDI FINALIZE failed: %s", e, exc_info=True)
            return request.redirect('/web/login?ndi_error=1')

    # ── 5. CANCEL ─────────────────────────────────────────────────────────────
    @http.route('/ndi/login/cancel', type='http', auth='none', csrf=False, website=False)
    def ndi_login_cancel(self, **kw):
        thread_id    = request.session.get('ndi_thread_id')
        access_token = request.session.get('ndi_access_token')
        if thread_id and access_token:
            _unsubscribe_webhook(access_token, thread_id)
            _set_param('ndi_proof_%s' % thread_id, False)
        request.session.pop('ndi_thread_id',    None)
        request.session.pop('ndi_access_token', None)
        request.session.pop('ndi_login_status', None)
        return request.redirect('/web/login')

    # ── 6. DEBUG (remove in production) ───────────────────────────────────────
    @http.route('/ndi/debug/employee', type='http', auth='user', csrf=False, website=False)
    def ndi_debug_employee(self, uid=None, **kw):
        env      = _su_env()
        uid      = int(uid) if uid else request.session.uid
        employee = env['hr.employee'].search([('user_id', '=', uid)], limit=1)
        if not employee:
            return request.make_response(
                'No employee found for uid=%s' % uid, status=404,
                headers=[('Content-Type', 'text/plain')]
            )
        info = {
            'employee_id':     employee.id,
            'employee_name':   employee.name,
            'model':           employee._name,
            'gender_field_exists':         'gender'         in employee._fields,
            'place_of_birth_field_exists': 'place_of_birth' in employee._fields,
            'birthday_field_exists':       'birthday'       in employee._fields,
            'private_phone_field_exists':  'private_phone'  in employee._fields,
            'private_email_field_exists':  'private_email'  in employee._fields,
            'current_gender':         str(employee.gender         or ''),
            'current_place_of_birth': str(employee.place_of_birth or ''),
            'current_birthday':       str(employee.birthday       or ''),
            'current_private_phone':  str(employee.private_phone  or ''),
            'current_mobile_phone':   str(employee.mobile_phone   or ''),
            'hr_employee_private_model_exists': 'hr.employee.private' in env,
        }
        return request.make_response(
            json.dumps(info, indent=2), status=200,
            headers=[('Content-Type', 'application/json')]
        )