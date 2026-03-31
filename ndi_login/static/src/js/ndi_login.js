/**
 * NDI Login — QR Generation + Status Polling
 */
(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {

        // ── 1. Generate QR Code ───────────────────────────────────────
        var qrUrl = (typeof NDI_QR_URL !== "undefined") ? NDI_QR_URL : "";

        if (qrUrl && document.getElementById("ndi_qrcode")) {
            try {
                new QRCode(document.getElementById("ndi_qrcode"), {
                    text: qrUrl,
                    width: 200,
                    height: 200,
                    colorDark: "#003087",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.M,
                });
            } catch (e) {
                console.error("NDI: QR generation failed:", e);
                document.getElementById("ndi_qrcode").innerHTML =
                    '<p style="color:red;font-size:12px;text-align:center;">' +
                    'QR generation failed.<br/>Check browser console.</p>';
            }
        }

        // ── 2. Status helpers ─────────────────────────────────────────
        function setStatus(type, text) {
            var bar  = document.getElementById("ndi_status_bar");
            var span = document.getElementById("ndi_status_text");
            if (!bar || !span) return;
            bar.className    = "o_ndi_status " + type;
            span.textContent = text;
            var spinner = bar.querySelector(".o_ndi_spinner");
            if (spinner) {
                spinner.style.display = (type === "pending") ? "inline-block" : "none";
            }
        }

        // ── 3. Get CSRF token ─────────────────────────────────────────
        function getCsrfToken() {
            if (window.odoo && window.odoo.csrf_token) return window.odoo.csrf_token;
            var meta = document.querySelector('meta[name="csrf-token"]');
            if (meta && meta.getAttribute("content")) return meta.getAttribute("content");
            var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
            if (match) return decodeURIComponent(match[1]);
            if (window.odoo && window.odoo.__csrf_token) return window.odoo.__csrf_token;
            return "";
        }

        // ── 4. Polling ────────────────────────────────────────────────
        var pollUrl      = (typeof NDI_POLL_URL !== "undefined") ? NDI_POLL_URL : "/ndi/login/status";
        var pollCount    = 0;
        var maxPolls     = 100;
        var pollTimer    = null;
        var isRedirecting = false;

        function stopPolling() {
            if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
        }

        function poll() {
            if (isRedirecting) return;
            pollCount++;

            if (pollCount > maxPolls) {
                stopPolling();
                setStatus("failed", "Session timed out. Redirecting to login...");
                setTimeout(function () { window.location.replace("/web/login"); }, 2000);
                return;
            }

            var csrfToken = getCsrfToken();
            var xhr = new XMLHttpRequest();
            xhr.open("POST", pollUrl, true);
            xhr.setRequestHeader("Content-Type", "application/json");
            if (csrfToken) xhr.setRequestHeader("X-Csrf-Token", csrfToken);

            xhr.onreadystatechange = function () {
                if (xhr.readyState !== 4) return;
                if (xhr.status !== 200) {
                    console.warn("NDI poll HTTP error:", xhr.status, xhr.responseText.substring(0, 200));
                    return;
                }
                var resp, data;
                try {
                    resp = JSON.parse(xhr.responseText);
                    data = (resp && resp.result) ? resp.result : resp;
                } catch (e) {
                    console.warn("NDI poll parse error:", e);
                    return;
                }
                console.log("NDI poll response:", data);
                if (!data || !data.status) return;

                switch (data.status) {
                    case "pending":
                        break;

                    case "validated":
                        stopPolling();
                        isRedirecting = true;
                        setStatus("pending", "Verifying credentials, please wait...");
                        var dest = data.redirect || "/web";
                        console.log("NDI: navigating to finalize:", dest);
                        setTimeout(function () { window.location.replace(dest); }, 400);
                        break;

                    case "failed":
                        stopPolling();
                        setStatus("failed", "Verification failed or rejected. Redirecting...");
                        setTimeout(function () { window.location.replace("/web/login?ndi_error=1"); }, 2500);
                        break;

                    case "error":
                        stopPolling();
                        setStatus("failed", "Error: " + (data.message || "Unknown error"));
                        setTimeout(function () { window.location.replace("/web/login?ndi_error=1"); }, 2500);
                        break;
                }
            };

            xhr.onerror = function () {
                console.warn("NDI poll network error — will retry on next interval");
            };

            var body = { jsonrpc: "2.0", method: "call", id: pollCount, params: {} };
            if (csrfToken) body.params.csrf_token = csrfToken;
            xhr.send(JSON.stringify(body));
        }

        poll();
        pollTimer = setInterval(poll, 3000);
    });

}());