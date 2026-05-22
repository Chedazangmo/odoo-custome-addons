/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

class PMSDashboard extends Component {
    static template = "hr_pms_dashboard.Dashboard";
     static props = {
        action: { type: Object, optional: true },
        actionId: { type: [Number, String], optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
        globalState: { type: Object, optional: true },
    };




    closeCompletedCycleModal = () => {
        this.state.show_completed_cycle_modal = false;
        this.state.selected_completed_cycle = null;
        this.state.completed_cycle_employees = [];
    }


    setup() {
        this.action = this.env.services.action;
        const initialTab = (this.props.action && this.props.action.params && this.props.action.params.tab) || 'overview';
        console.log("Initial tab:", initialTab);
         const actionParams = this.props.action?.params || {};
        const requestedRole = actionParams.role || 'overview';

        this.state = useState({

            loading: true,
            error: null,
            role: null,
            roles: [],
            employee_id: 0,
            employee_name: "",
            stats: {},
            active_cycles: [],
            score_engine: null,
            appraisal_breakdown: [],
            planning_dates: null,
            planning_is_historical: false,
            planning_cycle_name: '',
            planning_end_date: '',
            appraisal_dates: null,
            participation: null,
            top_performers: [],
            bottom_performers: [],
            supervisor: null,
            secondary: null,
            reviewer: null,
            employee: null,
            activeTab: initialTab,
            pending_manager_list: [],
            pending_secondary_list: [],
            pending_reviewer_list: [],
            pending_appraisal_manager_list: [],
            pending_appraisal_secondary_list: [],
            pending_appraisal_reviewer_list: [],

            employees_no_plan: [],
            employees_no_appraisal: [],
            hierarchy_employees: [],
            filtered_no_plan_employees: [],
            filtered_no_appraisal_employees: [],
            filtered_hierarchy_employees: [],
             filtered_cycle_appraisal_data: [],
            no_plan_search: '',
            no_appraisal_search: '',
            hierarchy_search: '',
            hierarchy_dept_filter: '',
            hierarchy_group_filter: '',
            hierarchy_cycle_filter: '',
            department_list: [],
            evaluation_group_list: [],
            employees_no_plan_count: 0,
            employees_no_appraisal_count: 0,
            employees_with_plan: [],

            completed_cycle_employees: [],  // ← ADD THIS
    filtered_completed_cycle_employees: [],  // ← ADD THIS

            planning_pending_supervisor: [],
            planning_pending_reviewer: [],
            employees_without_plan: [],
            planning_employee_list: [],
            planning_employee_list_filtered: null,
            selected_plan: null,
            planningSearch: "",
              show_full_plan_details: false,
            selected_full_plan: null,

            dept_completion_data: [],
            dept_lagging: [],
            appraisal_started: 0,
appraisal_approved: 0,

            appraisal_search: '',
            filtered_appraisal_employees: [],
            appraisal_not_started_list: [],
            filtered_appraisal_not_started: [],
            appraisal_not_started_search: '',
            selected_appraisal: null,
             performance_employees_list: [],      // Original full list
    filtered_performance_employees: [],  // Filtered list for display
    performance_filter: 'all',


            appraisal_employees: [],
            appraisal_dept_chart: null,
                 show_all_appraisals_modal: false,
        all_appraisals_data: [],
        all_appraisals_summary: null,


            appraisal_no_record_list: [],
            filtered_appraisal_no_record: [],
            appraisal_no_record_search: '',
            appraisal_draft_list: [],
            filtered_appraisal_draft: [],
            appraisal_draft_search: '',
            employees_not_started: [],
            employees_no_plan_ever: [],


                show_completed_cycle_modal: false,
    selected_completed_cycle: null,
    completed_cycle_employees: [],

            all_cycles: [],
            active_cycles_list: [],
            completed_cycles_list: [],
            all_cycles_count: 0,
            active_cycles_count: 0,
            completed_cycles_count: 0,
            overview_stats: {},

            cycle_top_performers: [],
            cycle_bottom_performers: [],
            performance_employees_list: [],      // Original full list (all employees with scores)
          // Filtered list for display

            filtered_completed_cycles_list: [],  // Filtered list for display
            completed_cycles_search: '',

            selected_cycle: null,
            selected_cycle_id: null,
            show_cycle_detail: false,
            cycle_planning_data: [],
            cycle_appraisal_data: [],
            cycle_active_tab: 'planning',
            filtered_cycle_planning_data: [],
            cycle_planning_search: '',
            cycle_pending_supervisor_list: [],
            cycle_pending_secondary_list: [],
            cycle_pending_reviewer_list: [],
            cycle_pending_supervisor_count: 0,
            cycle_pending_secondary_count: 0,
            cycle_pending_reviewer_count: 0,
            cycle_reminder_employees: [],
            current_view: 'overview',
            requestedRole: requestedRole,

            completed_cycle_search: '',
            filtered_past_cycles: [],

             show_all_plans_preview: false,
    all_plans_data: [],
    all_plans_loading: false,
    all_plans_cycle_name: '',


        });
        this.allPlansPreviewContainer = useRef("allPlansPreviewContainer");

        // Chart refs
        this.stateChartRef = useRef("stateChart");
        this.phaseChartRef = useRef("phaseChart");
        this.evalGroupChartRef = useRef("evalGroupChart");
        this.deptGroupChartRef = useRef("deptGroupChart");
        this.participationChartRef = useRef("participationChart");
        this.scoreDeptChartRef = useRef("scoreDeptChart");
        this.scoreGroupChartRef = useRef("scoreGroupChart");
        this.scoreDistChartRef = useRef("scoreDistChart");
        this.empAppraisalChartRef = useRef("empAppraisalChart");

        this.appraisalStatusChartRef = useRef("appraisalStatusChart");
        this.appraisalEvalGroupChartRef = useRef("appraisalEvalGroupChart");

        this.empDeptChartRef = useRef("empDeptChart");
        this.empEvalGroupChartRef = useRef("empEvalGroupChart");
        this.empGenderChartRef = useRef("empGenderChart");

        this.empPlanningStatusChartRef = useRef("empPlanningStatusChart");
        this.empAppraisalStatusChartRef = useRef("empAppraisalStatusChart");

        this.overviewPlanningParticipationChartRef = useRef("overviewPlanningParticipationChart");
        this.overviewAppraisalParticipationChartRef = useRef("overviewAppraisalParticipationChart");
        this.overviewPlanningStatusChartRef = useRef("overviewPlanningStatusChart");
        this.overviewAppraisalStatusChartRef = useRef("overviewAppraisalStatusChart");
        this.overviewScoreDeptChartRef = useRef("overviewScoreDeptChart");
        this.overviewScoreGroupChartRef = useRef("overviewScoreGroupChart");
        this.overviewEmpDeptChartRef = useRef("overviewEmpDeptChart");
        this.overviewEmpGroupChartRef = useRef("overviewEmpGroupChart");

        this.appraisalDeptChartRef = useRef("appraisalDeptChart");
        this.cycleScoreDeptChartRef = useRef("cycleScoreDeptChart");
        this.cycleScoreGroupChartRef = useRef("cycleScoreGroupChart");
        this.cycleScoreDistChartRef = useRef("cycleScoreDistChart");
        this.cyclePlansDeptChartRef = useRef("cyclePlansDeptChart");
        this.cyclePlansGroupChartRef = useRef("cyclePlansGroupChart");
        this.cyclePlanStatusChartRef = useRef("cyclePlanStatusChart");

        this.supervisorDeptChartRef = useRef("supervisorDeptChart");
this.supervisorScoreChartRef = useRef("supervisorScoreChart");
this.reviewerDeptChartRef = useRef("reviewerDeptChart");
this.reviewerScoreChartRef = useRef("reviewerScoreChart");

        this.chartInstances = [];
        this._dataCache = null;
        this._refreshInterval = null;

        onMounted(async () => {
            await this._loadData();
          this._refreshInterval = setInterval(async () => {
    try {
        await this._loadData();
    } catch {
        console.log('Refresh skipped');
    }
}, 30000);
        });

        onWillUnmount(() => {
            this._destroyAllCharts();
            if (this._refreshInterval) clearInterval(this._refreshInterval);
        });
    }

    navigateTo(model, domain, name) {
        domain = domain || [];
        name = name || "Records";
        let url = '/web#model=' + model + '&view=list';
        if (domain && domain.length > 0) {
            var domainStr = JSON.stringify(domain);
            url += '&domain=' + encodeURIComponent(domainStr);
        }
        window.open(url, '_blank');
    }

    async loadPlanningTabData() {
        try {
            const result = await rpc("/hr_pms_dashboard/planning_data", {});

            if (result.error || result.message === 'Error loading data') {
                console.error("Planning data server error:", result.message, result.traceback || '');
                this.state.planning_is_historical = false;
                this.state.planning_employee_list = [];
                this.state.planning_pending_supervisor = [];
                this.state.planning_pending_reviewer = [];
                this.state.employees_not_started = [];
                return;
            }

            this.state.planning_pending_supervisor = result.pending_supervisor || [];
            this.state.planning_pending_reviewer = result.pending_reviewer || [];
            this.state.employees_not_started = result.employees_not_started || [];
            this.state.planning_employee_list = result.all_plans || [];
            this.state.planning_employee_list_filtered = null;
            this.state.planning_is_historical = result.is_historical || false;
            this.state.planning_cycle_name = result.cycle_name || '';
            this.state.planning_end_date = result.cycle_end_date || '';
            this.state.planning_cycle_state = result.cycle_state || '';

            const deptData = await rpc("/hr_pms_dashboard/dept_completion_data", {});
            this.state.dept_completion_data = deptData.dept_rows || [];
            this.state.dept_lagging = deptData.dept_lagging || [];

        } catch (error) {
            console.error("Error loading planning data:", error);
            this.state.employees_not_started = [];
            this.state.planning_employee_list = [];
            this.state.planning_pending_supervisor = [];
            this.state.planning_pending_reviewer = [];
            this.state.planning_is_historical = false;
        }
    }
// Load performance data for completed appraisals
loadPerformanceData = async () => {
    try {
        const cycle = this.state.selected_cycle;
        if (!cycle || !cycle.id) return;

        const result = await rpc("/hr_pms_dashboard/get_cycle_performance_data", {
            cycle_id: cycle.id,
        });

        console.log("=== PERFORMANCE DATA DEBUG ===");
        console.log("Full result:", JSON.stringify(result, null, 2));
        console.log("Employees array:", result.employees);
        console.log("Employees length:", result.employees?.length);

        if (result && result.employees && result.employees.length > 0) {
            this.state.performance_employees_list = result.employees;
            this.state.filtered_performance_employees = [...result.employees];
            this.state.performance_filter = 'all';
            console.log("✅ Loaded", result.employees.length, "employees");
        } else {
            console.warn("⚠️ No employees found in performance data");
            this.state.performance_employees_list = [];
            this.state.filtered_performance_employees = [];
        }
    } catch (error) {
        console.error("Error loading performance data:", error);
        this.state.performance_employees_list = [];
        this.state.filtered_performance_employees = [];
    }
}
async refreshPlanData() {
    this.state.isRefreshing = true;
    try {
        const result = await this.orm.call(
            "pms.dashboard",
            "get_dashboard_data",
            [],
            {}
        );

        if (result.employee && this.state.role === "employee") {
            // Mirror exactly what your main load does
            this.state.employee = result.employee;
            this.state.employee_id = result.employee_id || 0;
            this.state.employee_name = result.employee_name || "";

            // Re-apply past cycles + search filter
            if (result.employee.past_cycles) {
                this.state.filtered_past_cycles = [...result.employee.past_cycles];
                if (this.state.completed_cycle_search) {
                    this.filterCompletedCycles();
                }
            }

            // Rebuild charts with fresh data
            this._destroyAllCharts();
            await this._renderEmployeeDashboardCharts(result);
        }
    } catch (e) {
        console.error("Plan refresh failed:", e);
    } finally {
        this.state.isRefreshing = false;
    }
}
openCycleDetail = async (cycle) => {
    console.log("=== Cycle clicked ===");
    console.log("Cycle ID:", cycle.id);
    console.log("Cycle name:", cycle.name);
    console.log("Cycle state:", cycle.state);

    this.state.cycle_planning_search = '';
    this.state.cycle_appraisal_search = '';
     this.filterCyclePlanningData();

    if (cycle.state === 'completed') {
        console.log("Completed cycle - opening modal");
        await this.loadCompletedCycleDetails(cycle);
        return;
    }

    this.state.current_view = 'cycle_detail';
    this.state.show_cycle_detail = true;
    this.state.selected_cycle_id = cycle.id;

    // Set tab default based on phase
    this.state.cycle_active_tab = cycle.state === 'appraisal' ? 'appraisal' : 'planning';

    // Immediately set safe defaults so OWL doesn't crash during async load
    this.state.selected_cycle = this._safeCycle(cycle);

    // Load full cycle data from backend
    await this.loadCycleData(cycle.id);

    // After loadCycleData, re-apply _safeCycle to guarantee all arrays exist
    // (in case loadCycleData set state.selected_cycle without some fields)
    this.state.selected_cycle = this._safeCycle(this.state.selected_cycle);

    // Render charts
    if (this.state.cycle_active_tab === 'planning') {
        await this._renderPlanningChartsByRole();
    } else {
        await this._renderAppraisalChartsByRole();
    }
}

_safeCycle(cycle) {
    return {
        ...cycle,

        // Planning arrays
        pending_plan_list: Array.isArray(cycle.pending_plan_list) ? cycle.pending_plan_list : [],
        team_plans: Array.isArray(cycle.team_plans) ? cycle.team_plans : [],
        employees_without_plan: Array.isArray(cycle.employees_without_plan) ? cycle.employees_without_plan : [],
        pending_approval_plans: Array.isArray(cycle.pending_approval_plans) ? cycle.pending_approval_plans : [],
        all_plans: Array.isArray(cycle.all_plans) ? cycle.all_plans : [],

        // Appraisal arrays
        pending_appraisal_list: Array.isArray(cycle.pending_appraisal_list) ? cycle.pending_appraisal_list : [],
        team_appraisals: Array.isArray(cycle.team_appraisals) ? cycle.team_appraisals : [],
        employees_without_appraisal: Array.isArray(cycle.employees_without_appraisal) ? cycle.employees_without_appraisal : [],
        pending_approval_appraisals: Array.isArray(cycle.pending_approval_appraisals)
            ? cycle.pending_approval_appraisals
            : (Array.isArray(cycle.pending_appraisal_reviewer_list) ? cycle.pending_appraisal_reviewer_list : []),
        pending_appraisal_supervisor_list: Array.isArray(cycle.pending_appraisal_supervisor_list) ? cycle.pending_appraisal_supervisor_list : [],
        pending_appraisal_secondary_list: Array.isArray(cycle.pending_appraisal_secondary_list) ? cycle.pending_appraisal_secondary_list : [],
        pending_appraisal_reviewer_list: Array.isArray(cycle.pending_appraisal_reviewer_list) ? cycle.pending_appraisal_reviewer_list : [],
        all_appraisals: Array.isArray(cycle.all_appraisals) ? cycle.all_appraisals : [],

        // Performance arrays
        top_performers: Array.isArray(cycle.top_performers) ? cycle.top_performers : [],
        bottom_performers: Array.isArray(cycle.bottom_performers) ? cycle.bottom_performers : [],
        rating_distribution: Array.isArray(cycle.rating_distribution) ? cycle.rating_distribution : [],

        // Scalar defaults — only use fallback if value is null/undefined
        total_employees: cycle.total_employees ?? 0,
        total_team_members: cycle.total_team_members ?? 0,
        pending_plan_count: cycle.pending_plan_count ?? 0,
        pending_appraisal_count: cycle.pending_appraisal_count ?? 0,
        approved_plan_count: cycle.approved_plan_count ?? 0,
        submitted_plan_count: cycle.submitted_plan_count ?? 0,
        completed_appraisal_count: cycle.completed_appraisal_count ?? 0,
        employees_without_plan_count: cycle.employees_without_plan_count ?? 0,
        employees_without_appraisal_count: cycle.employees_without_appraisal_count ?? 0,
        avg_score: cycle.avg_score ?? 0,
        appraisal_started: cycle.appraisal_started ?? 0,
        appraisal_approved: cycle.appraisal_approved ?? 0,
        plans_submitted: cycle.plans_submitted ?? 0,
        plans_approved: cycle.plans_approved ?? 0,
    };
}

closeCycleDetail = () => {
    this.state.show_cycle_detail = false;
    this.state.is_monitoring_cycle = false;
    this.state.selected_cycle = null;
    this.state.selected_cycle_id = null;
    this.state.cycle_active_tab = 'planning';
    this.state.current_view = 'overview';
}

// Helper methods for chart rendering
_renderPlanningChartsByRole = async () => {
    if (this.state.role === 'supervisor') {
        await this._renderSupervisorPlanningCharts(this.state.selected_cycle);
    } else if (this.state.role === 'reviewer') {
        await this._renderReviewerPlanningCharts(this.state.selected_cycle);
    } else if (this.state.role === 'hr_manager') {
        await this._renderCyclePlanningCharts();
    }
}

_renderAppraisalChartsByRole = async () => {
    if (this.state.role === 'supervisor') {
        await this._renderSupervisorAppraisalCharts(this.state.selected_cycle);
    } else if (this.state.role === 'reviewer') {
        await this._renderReviewerAppraisalCharts(this.state.selected_cycle);
    }
}

loadCompletedCycleDetails = async (cycle) => {
    console.log("=== loadCompletedCycleDetails called ===");
    console.log("Cycle ID:", cycle.id);

    this.state.show_completed_cycle_detail = true;
    this.state.selected_completed_cycle = {
        ...cycle,
        total_employees: cycle.total_employees || 0,
        avg_score: cycle.avg_score || 0,
        top_rating: cycle.top_rating || '-',
        completed_count: cycle.completed_count || 0,
    };
    this.state.completed_cycle_employees = [];  // ← Clear existing data
    this.state.completed_cycle_search = '';

    try {
        const response = await fetch('/hr_pms_dashboard/get_completed_cycle_appraisals', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Odoo-CSRF-Token': odoo.csrf_token,
            },
            body: JSON.stringify({
                cycle_id: cycle.id,
            }),
        });

        const data = await response.json();
        console.log("API Response:", data);

        const result = data.result;
        console.log("Result data:", result);

        if (result && result.appraisals) {
            // ✅ FIX: Set completed_cycle_employees (this is what your modal uses)
            this.state.completed_cycle_employees = result.appraisals;

            // Keep these for other parts of the dashboard
            this.state.completed_cycle_data = result.appraisals;
            this.state.filtered_completed_cycle_data = result.appraisals;

            // Create performance employees list (all employees with scores)
            this.state.performance_employees_list = result.appraisals.map(emp => ({
                employee_id: emp.employee_id,
                name: emp.name,
                department: emp.department,
                evaluation_group: emp.evaluation_group,
                kpi_score: emp.kpi_score || emp.self_score || 0,
                competency_score: emp.competency_score || 0,
                total_score: emp.final_score || emp.total_score || 0,
                rating: emp.rating,
                rating_class: emp.rating_class,
            }));

            // Initialize filtered list
            this.state.filtered_performance_employees = [...this.state.performance_employees_list];
            this.state.performance_filter = 'all';

            console.log(`✅ Loaded ${result.appraisals.length} employees for performance table`);

            // Update summary with actual data
            if (result.summary) {
                this.state.selected_completed_cycle.total_employees = result.summary.total_employees;
                this.state.selected_completed_cycle.avg_score = result.summary.avg_score;
                this.state.selected_completed_cycle.completed_count = result.summary.completed_count;
            }
        } else {
            console.error("No appraisals in response:", result);
            this.state.completed_cycle_employees = [];
            this.state.completed_cycle_data = [];
            this.state.filtered_completed_cycle_data = [];
            this.state.performance_employees_list = [];
            this.state.filtered_performance_employees = [];
        }
    } catch (error) {
        console.error('Error loading completed cycle details:', error);
        this.state.completed_cycle_employees = [];
        this.state.completed_cycle_data = [];
        this.state.filtered_completed_cycle_data = [];
        this.state.performance_employees_list = [];
        this.state.filtered_performance_employees = [];
    }
}

// Method to set filter
setPerformanceFilter = (filterType) => {
    this.state.performance_filter = filterType;
    this.filterPerformanceEmployees();
}

onPerformanceFilterChange = () => {
    this.filterPerformanceEmployees();
}

// Method to filter employees based on score
filterPerformanceEmployees = () => {
    const employees = this.state.performance_employees_list || [];

    switch(this.state.performance_filter) {
        case 'high':
            this.state.filtered_performance_employees = employees.filter(emp =>
                (emp.total_score || emp.score || 0) >= 85
            );
            break;
        case 'low':
            this.state.filtered_performance_employees = employees.filter(emp =>
                (emp.total_score || emp.score || 0) < 70
            );
            break;
        default: // 'all'
            this.state.filtered_performance_employees = [...employees];
    }
}

// Filter function for completed cycle table
filterCompletedCycleData = () => {
    const search = this.state.completed_cycle_search?.toLowerCase() || '';
    if (!search) {
        this.state.filtered_completed_cycle_data = this.state.completed_cycle_data;
    } else {
        this.state.filtered_completed_cycle_data = this.state.completed_cycle_data.filter(emp =>
            emp.name?.toLowerCase().includes(search) ||
            emp.department?.toLowerCase().includes(search) ||
            emp.evaluation_group?.toLowerCase().includes(search)
        );
    }
}

// Close completed cycle detail modal
closeCompletedCycleDetail = () => {
    this.state.show_completed_cycle_detail = false;
    this.state.selected_completed_cycle = null;
    this.state.completed_cycle_employees = [];  // ← Clear this too
    this.state.completed_cycle_data = [];
    this.state.filtered_completed_cycle_data = [];
    this.state.completed_cycle_search = '';
}
// ============================================================
// HR MANAGER STAT CARD METHODS
// ============================================================

onClickEmployeesInActiveCycles = () => {
    // Get all employees who are in active cycles
    const activeCycleEmployeeIds = [];

    // Collect employee IDs from all active cycles
    if (this.state.active_cycles_list && this.state.active_cycles_list.length > 0) {
        for (const cycle of this.state.active_cycles_list) {
            // You'll need to get employees from cycle data
            // This depends on how your cycle data is structured
            if (cycle.employee_ids) {
                activeCycleEmployeeIds.push(...cycle.employee_ids);
            }
        }
    }

    // Remove duplicates
    const uniqueIds = [...new Set(activeCycleEmployeeIds)];

    if (uniqueIds.length === 0) {
        this.env.services.notification.add("No employees found in active cycles", { type: "warning" });
        return;
    }

    // Open employee list view
    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'hr.employee',
        views: [[false, 'list']],
        domain: [['id', 'in', uniqueIds]],
        target: 'current',
        name: 'Employees in Active Cycles',
    });
}

// Method to filter cycles by name
filterCompletedCyclesList = () => {
    const searchTerm = this.state.completed_cycles_search?.toLowerCase().trim() || '';
    if (!searchTerm) {
        this.state.filtered_completed_cycles_list = [...this.state.completed_cycles_list];
    } else {
        this.state.filtered_completed_cycles_list = this.state.completed_cycles_list.filter(cycle =>
            cycle.name?.toLowerCase().includes(searchTerm)
        );
    }
}

viewCompletedAppraisalDetail = (employeeId) => {
 console.log("Viewing completed appraisal detail for:", emp);
    const emp = this.state.performance_employees_list.find(e => e.employee_id === employeeId);
    if (!emp || !emp.employee_id) {
        console.warn('Employee not found:', employeeId);
        return;
    }
    this.state.selected_completed_appraisal = emp;
}

// Close individual appraisal detail modal
closeCompletedAppraisalDetail = () => {
    this.state.selected_completed_appraisal = null;
}

exportCompletedCycleData = () => {
    if (!this.state.completed_cycle_employees || this.state.completed_cycle_employees.length === 0) {
        this.env.services.notification.add("No data to export", { type: "warning" });
        return;
    }

    // Get cycle info
    const cycle = this.state.selected_completed_cycle;
    const employees = this.state.completed_cycle_employees;

    // Prepare CSV data with cycle summary
    const cycleInfo = [
        [`Cycle: ${cycle?.name || ''}`],
        [`Period: ${cycle?.start_date || ''} to ${cycle?.end_date || ''}`],
        [`Total Employees: ${employees.length}`],

        [], // Empty row
    ];

    // Headers
    const headers = [
        'Employee',
        'Department',
        'Evaluation Group',
        'Self Score',
        'Supervisor Score',
        'Secondary Score',
        'Reviewer Score',
        'Final Score',
        'Rating',
         'Bonus Eligibility %',  // ← ADD
    'Basic Pay',            // ← ADD
    'Bonus Amount',         // ← ADD
    ];

    // Data rows
    const rows = employees.map(emp => [
        emp.name || '',
        emp.department || '-',
        emp.evaluation_group || '-',
        emp.self_score || 0,
        emp.supervisor_score || 0,
        emp.secondary_score || '-',
        emp.reviewer_score || 0,
        emp.final_score || 0,
        emp.rating || '-',
         emp.eligibility_pct || 0,   // ← ADD
    emp.basic_pay || 0,         // ← ADD
    emp.bonus_amount || 0,
    ]);

    // Combine everything
    const csvLines = [];

    // Add cycle info
    cycleInfo.forEach(info => {
        csvLines.push(info.join(','));
    });

    // Add headers
    csvLines.push(headers.join(','));

    // Add data rows
    rows.forEach(row => {
        const escapedRow = row.map(cell => {
            if (typeof cell === 'string' && (cell.includes(',') || cell.includes('"'))) {
                return `"${cell.replace(/"/g, '""')}"`;
            }
            return cell;
        });
        csvLines.push(escapedRow.join(','));
    });

    const csvContent = csvLines.join('\n');
    const blob = new Blob(["\uFEFF" + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${cycle?.name || 'completed_cycle'}_appraisals.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.env.services.notification.add(`Exported ${employees.length} records successfully!`, { type: "success" });
}
exportCompletedCycleToPDF = async () => {


    const modalBody = document.querySelector('.pms_plan_modal_body');
    if (!modalBody) return;

    const cycle = this.state.selected_completed_cycle;

    // ── Clone and strip scroll constraints ───────────────────
    const element = modalBody.cloneNode(true);
    element.style.maxHeight = 'none';
    element.style.overflow  = 'visible';
    element.style.height    = 'auto';
    element.style.padding   = '16px';

    element.querySelectorAll('*').forEach(el => {
        el.style.overflow  = 'visible';
        el.style.maxHeight = 'none';
    });

    const opt = {
        margin: [0.4, 0.4, 0.4, 0.4],
        filename: `${cycle?.name || 'completed_cycle'}_appraisals.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: {
            scale: 2,
            useCORS: true,
            scrollX: 0,
            scrollY: 0,
            windowWidth: document.documentElement.scrollWidth,
        },
        jsPDF: {
            unit: 'in',
            format: 'a4',
            orientation: 'landscape'
        },
        pagebreak: {
            mode: ['avoid-all', 'css', 'legacy'],
            avoid: ['tr', 'td'],
        }
    };

    this.env.services.notification.add("Preparing PDF...", { type: "info" });

    html2pdf()
        .set(opt)
        .from(element)
        .toPdf()
        .get('pdf')
        .then(pdf => {
            // ── Page numbers ─────────────────────────────────
            const totalPages = pdf.internal.getNumberOfPages();
            for (let i = 1; i <= totalPages; i++) {
                pdf.setPage(i);
                pdf.setFontSize(8);
                pdf.setTextColor(150);
                pdf.text(
                    `${cycle?.name || ''} — Page ${i} of ${totalPages}`,
                    pdf.internal.pageSize.getWidth() / 2,
                    pdf.internal.pageSize.getHeight() - 0.2,
                    { align: 'center' }
                );
            }
        })
        .save()
        .then(() => {
            this.env.services.notification.add("PDF exported successfully!", { type: "success" });
        });
}

// Export Completed Cycle to Excel
exportCompletedCycleToExcel = () => {
    if (!this.state.selected_completed_cycle) {
        this.env.services.notification.add("No data to export", { type: "warning" });
        return;
    }

    const cycle = this.state.selected_completed_cycle;

    const escape = (val) => {
        const str = String(val ?? '-');
        return str.includes(',') || str.includes('"') || str.includes('\n')
            ? `"${str.replace(/"/g, '""')}"`
            : str;
    };

    const csvLines = [
        // Appraisal Information
        `Appraisal For:,${escape(cycle.employee_name)}`,
        `Cycle Name:,${escape(cycle.cycle_name)}`,
        `Department:,${escape(cycle.department)}`,
        `Status:,Completed`,
        `Primary Manager:,${escape(cycle.supervisor_name)}`,
        `Secondary Manager:,${escape(cycle.secondary_name || '-')}`,
        `Reviewer:,${escape(cycle.reviewer_name || '-')}`,
        `Total Weightage:,${escape(cycle.total_weightage || 0)}%`,
        ``,
        // KPI Scores
        `KPI SCORES,,,,,,`,
        `KPI,Weightage,Self Score,1st Manager,2nd Manager,Reviewer Score`,
    ];

    // Add KPI rows
    if (cycle.kpi_lines && cycle.kpi_lines.length > 0) {
        cycle.kpi_lines.forEach(line => {
            csvLines.push([
                escape(line.kpi_name),
                escape(line.weightage || 0),
                escape(line.self_score || '-'),
                escape(line.supervisor_score || '-'),
                escape(line.secondary_score || '-'),
                escape(line.reviewer_score || '-'),
            ].join(','));
        });
    } else {
        csvLines.push(`No KPI data found,,,,,`);
    }

    csvLines.push(``);
    csvLines.push(`COMPETENCY SCORES,,,,,,`);
    csvLines.push(`Competency,Self Score,1st Manager,2nd Manager,Reviewer Score`);

    // Add Competency rows
    if (cycle.competency_lines && cycle.competency_lines.length > 0) {
        cycle.competency_lines.forEach(line => {
            csvLines.push([
                escape(line.competency_name),
                escape(line.self_score || '-'),
                escape(line.supervisor_score || '-'),
                escape(line.secondary_score || '-'),
                escape(line.reviewer_score || '-'),
            ].join(','));
        });
    } else {
        csvLines.push(`No competency data found,,,,`);
    }

    csvLines.push(``);
    csvLines.push(`FINAL SCORE SUMMARY,,,,,,`);
    csvLines.push(`KPI Total:,${escape(cycle.kpi_total || 0)},,,,`);
    csvLines.push(`Competency Total:,${escape(cycle.competency_total || 0)},,,,`);
    csvLines.push(`Final Score:,${escape(cycle.final_score || 0)},,,,`);
    csvLines.push(`Rating:,${escape(cycle.rating || '-')},,,,`);

    const blob = new Blob(["\uFEFF" + csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${cycle.cycle_name}_appraisal_details.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.env.services.notification.add("Exported successfully!", { type: "success" });
}


// Open full appraisal in Odoo
openFullAppraisal = (appraisalId) => {
    if (appraisalId) {
        window.open(`/web#id=${appraisalId}&model=pms.appraisal&view=form`, '_blank');
    }
}

openFullAppraisalDetails = async (appraisal) => {
    console.log("Opening full appraisal details for:", appraisal);

    // Check if it's an event object
    if (!appraisal || appraisal.constructor?.name === 'PointerEvent') {
        console.error("Invalid appraisal object received");
        this.env.services.notification.add("Cannot open appraisal details: Invalid data", { type: "danger" });
        return;
    }

    const appraisalId = appraisal.id || appraisal.appraisal_id;

    if (!appraisalId) {
        console.error("Missing appraisal id", appraisal);
        this.env.services.notification.add("Cannot open appraisal details: Missing ID", { type: "danger" });
        return;
    }

    this.state.show_full_appraisal_details = true;
    this.state.selected_full_appraisal = null;

    try {
        const result = await rpc("/hr_pms_dashboard/get_appraisal_details", {
            appraisal_id: appraisalId,
        });

        console.log("Appraisal details response:", result);

        if (result && result.success) {
            this.state.selected_full_appraisal = result.data;
        } else {
            this.env.services.notification.add(result?.error || "Failed to load appraisal details", { type: "danger" });
        }
    } catch (error) {
        console.error("Error loading appraisal details:", error);
        this.env.services.notification.add("Error loading appraisal details", { type: "danger" });
    }
}

// Method to close the modal
closeFullAppraisalDetails = () => {
    this.state.show_full_appraisal_details = false;
    this.state.selected_full_appraisal = null;
}
closeCycleDetail = () => {
    this.state.current_view = this.state.role === 'hr_manager' ? 'hr_manager' : this.state.role;
    this.state.show_cycle_detail = false;
    this.state.selected_cycle = null;
    this.state.selected_cycle_id = null;
}
onApprovePlan = (plan) => {
    // Call server to approve plan
    rpc("/hr_pms_dashboard/approve_plan", {
        'plan_id': plan.plan_id || plan.id,
        'cycle_id': this.state.selected_cycle_id
    }).then(result => {
        if (result.success) {
            this.env.services.notification.add("Plan approved successfully!", { type: "success" });
            this._loadData(); // Refresh data
        } else {
            this.env.services.notification.add("Failed to approve plan", { type: "danger" });
        }
    }).catch(error => {
        this.env.services.notification.add("Error approving plan", { type: "danger" });
    });
}

onApproveAppraisal = (appraisal) => {
    rpc("/hr_pms_dashboard/approve_appraisal", {
        'appraisal_id': appraisal.appraisal_id || appraisal.id,
        'cycle_id': this.state.selected_cycle_id
    }).then(result => {
        if (result.success) {
            this.env.services.notification.add("Appraisal approved successfully!", { type: "success" });
            this._loadData();
        } else {
            this.env.services.notification.add("Failed to approve appraisal", { type: "danger" });
        }
    }).catch(error => {
        this.env.services.notification.add("Error approving appraisal", { type: "danger" });
    });
}

sendReminderToEmployee = (emp) => {
    rpc("/hr_pms_dashboard/send_reminder", {
        'employee_id': emp.id,
        'cycle_id': this.state.selected_cycle_id
    }).then(result => {
        if (result.success) {
            this.env.services.notification.add(`Reminder sent to ${emp.name}`, { type: "success" });
        } else {
            this.env.services.notification.add("Failed to send reminder", { type: "danger" });
        }
    }).catch(error => {
        this.env.services.notification.add("Error sending reminder", { type: "danger" });
    });
}
 loadCycleData = async (cycleId) => {
    try {
        const data = await rpc("/hr_pms_dashboard/cycle_data", {
            'cycle_id': cycleId
        });

        console.log("=== CYCLE DATA DEBUG ===");
        console.log("Full response:", data);

         await this.loadPerformanceData();

        // ============================================================
        // FOR HR MANAGER VIEW
        // ============================================================
        this.state.cycle_planning_data = data.planning_data || [];
        this.state.cycle_appraisal_data = data.appraisal_data || [];
        this.state.cycle_top_performers = data.top_performers || [];
        this.state.cycle_bottom_performers = data.bottom_performers || [];
this.state.filtered_cycle_appraisal_data = [...(data.appraisal_data || [])];

        const planningData = data.planning_data || [];

        this.state.cycle_pending_supervisor_list = planningData.filter(p => p.state_key === 'pending_supervisor');
        this.state.cycle_pending_secondary_list = planningData.filter(p => p.state_key === 'pending_secondary_supervisor');
        this.state.cycle_pending_reviewer_list = planningData.filter(p => p.state_key === 'pending_reviewer');

        this.state.cycle_pending_supervisor_count = this.state.cycle_pending_supervisor_list.length;
        this.state.cycle_pending_secondary_count = this.state.cycle_pending_secondary_list.length;
        this.state.cycle_pending_reviewer_count = this.state.cycle_pending_reviewer_list.length;

        this.state.cycle_reminder_employees = planningData.filter(p => {
            return p.state_key === 'draft' ||
                   p.state_key === 'pending_supervisor' ||
                   p.state_key === 'pending_secondary_supervisor' ||
                   p.state_key === 'pending_reviewer';
        }).map(p => ({ ...p, days_stuck: p.days_stuck || 0 }));

        this.state.filtered_cycle_planning_data = [...this.state.cycle_planning_data];


        // ============================================================
        // FOR SUPERVISOR AND REVIEWER VIEWS - Populate selected_cycle
        // ============================================================
        if (this.state.selected_cycle) {
            // Get current user's role to determine which pending plans to show
            const currentRole = this.state.role; // 'supervisor' or 'reviewer'
            const currentEmployeeId = this.state.employee_id;

            // Transform planning_data into team_plans format
            const teamPlans = (data.planning_data || []).map(plan => ({
                id: plan.plan_id || plan.id,        // ← ADD THIS LINE
                plan_id: plan.plan_id || plan.id,
                employee_id: plan.employee_id,
                name: plan.name,
                department: plan.department,
                selected_kpi: plan.selected_kpi || 0,
                total_kpi: plan.total_kpi || 0,
                state: plan.state,
                state_key: plan.state_key,
                progress: plan.progress || 0,
                submitted_date: plan.submitted_date,
                supervisor_name: plan.supervisor_name,
                secondary_name: plan.secondary_name,
                reviewer_name: plan.reviewer_name,
                supervisor_id: plan.supervisor_id,
                secondary_id: plan.secondary_id,
                reviewer_id: plan.reviewer_id,
                user_role: plan.user_role, // 'primary', 'secondary', or 'reviewer'
            }));

            // Transform appraisal_data into team_appraisals format
            const teamAppraisals = (data.appraisal_data || []).map(appraisal => ({
             id: appraisal.plan_id || appraisal.id,           // ← ADD THIS
    appraisal_id: appraisal.plan_id || appraisal.id, // ← ADD THIS
                employee_id: appraisal.employee_id,
                name: appraisal.name,
                department: appraisal.department,
                self_score: appraisal.self_score || 0,
                supervisor_score: appraisal.supervisor_score || 0,
                 secondary_score: appraisal.secondary_score || 0,
                 reviewer_score: appraisal.reviewer_score || 0,
                final_score: appraisal.final_score || 0,
                state: appraisal.state,
                state_key: appraisal.state_key,
                progress: appraisal.progress || 0,
                rating: appraisal.rating,
                supervisor_id: appraisal.supervisor_id,
                secondary_id: appraisal.secondary_id,
                reviewer_id: appraisal.reviewer_id,
                user_role: appraisal.user_role,
            }));
            const appraisalStartedCount = teamAppraisals.filter(a =>
    a.state_key !== 'appraisal_draft'
).length;

// Count completed appraisals (approved)
const appraisalApprovedCount = teamAppraisals.filter(a =>
    a.state_key === 'appraisal_approved'
).length;

 this.state.appraisal_started = appraisalStartedCount;
        this.state.appraisal_approved = appraisalApprovedCount;

            // Calculate counts
            const totalTeamMembers = teamPlans.length;

            // ============================================================
            // FIXED: For Supervisor - show plans pending THEIR approval
            // ============================================================
            let pendingPlans = 0;
            let pendingPlanList = [];


if (data.pending_plan_list && data.pending_plan_list.length > 0) {
    console.log("RAW pending_plan_list from backend:", data.pending_plan_list);
    console.log("Current role:", currentRole);

    // Filter based on current role
    let filteredList = data.pending_plan_list;

    if (currentRole === 'supervisor') {
        // Supervisor: only see pending_supervisor and pending_secondary_supervisor
        filteredList = data.pending_plan_list.filter(p =>
            p.state_key === 'pending_supervisor' || p.state_key === 'pending_secondary_supervisor'
        );
        console.log("Supervisor filtered pending plans:", filteredList);
    } else if (currentRole === 'reviewer') {
        // Reviewer: only see pending_reviewer
        filteredList = data.pending_plan_list.filter(p =>
            p.state_key === 'pending_reviewer'
        );
        console.log("Reviewer filtered pending plans:", filteredList);
    }

    pendingPlanList = filteredList;
    pendingPlans = pendingPlanList.length;
    console.log("Pending plans from BACKEND (filtered by role):", pendingPlanList);
    console.log("First pending plan has ID:", pendingPlanList[0]?.id);

} else {
    // FALLBACK: Only if backend doesn't send it
    console.log("Backend pending_plan_list missing, using fallback");

    if (currentRole === 'supervisor') {
        pendingPlanList = teamPlans.filter(p => {
            return (p.state_key === 'pending_supervisor' && p.user_role === 'primary') ||
                   (p.state_key === 'pending_secondary_supervisor' && p.user_role === 'secondary');
        }).map(p => ({ ...p, id: p.id, plan_id: p.id }));
        pendingPlans = pendingPlanList.length;

    } else if (currentRole === 'reviewer') {
        // Only show plans where current user is the reviewer
        pendingPlanList = teamPlans.filter(p =>
            p.state_key === 'pending_reviewer' &&
            p.reviewer_id === currentEmployeeId
        ).map(p => ({ ...p, id: p.id, plan_id: p.id }));
        pendingPlans = pendingPlanList.length;
        console.log("Reviewer fallback results (filtered by reviewer_id):", pendingPlanList);
    }
}
            const approvedPlans = teamPlans.filter(p => p.state_key === 'approved').length;
            const submittedPlans = teamPlans.filter(p => p.state_key !== 'draft').length;

            // ============================================================
            // FIXED: For Supervisor - show appraisals pending THEIR approval
            // ============================================================
            let pendingAppraisals = 0;
            let pendingAppraisalList = [];

            if (currentRole === 'supervisor') {
    // Supervisor: Show appraisals pending their rating
    pendingAppraisalList = teamAppraisals.filter(a => {
        return (a.state_key === 'appraisal_pending_supervisor' && a.user_role === 'primary') ||
               (a.state_key === 'appraisal_pending_secondary_supervisor' && a.user_role === 'secondary');
    }).map(a => ({
        id: a.id,
        appraisal_id: a.id,
        employee_id: a.employee_id,
        name: a.name,
        department: a.department,
        self_score: a.self_score,
        supervisor_score: a.supervisor_score,
        state_key: a.state_key,
    }));
    pendingAppraisals = pendingAppraisalList.length;
} else if (currentRole === 'reviewer') {
console.log("teamAppraisals sample:", teamAppraisals[0]);
    pendingAppraisalList = teamAppraisals.filter(a => a.state_key === 'appraisal_pending_reviewer').map(a => ({
        id: a.id,
        appraisal_id: a.id,
        employee_id: a.employee_id,
        name: a.name,
        department: a.department,
        self_score: a.self_score,
        supervisor_score: a.supervisor_score,
        state_key: a.state_key,
    }));
    pendingAppraisals = pendingAppraisalList.length;
}

            const completedAppraisals = teamAppraisals.filter(a => a.state_key === 'appraisal_approved').length;

            const avgScore = teamAppraisals.length > 0
                ? (teamAppraisals.reduce((sum, a) => sum + (a.final_score || 0), 0) / teamAppraisals.length).toFixed(1)
                : 0;

            // Employees without plan (draft state)
            const employeesWithoutPlan = teamPlans.filter(p => p.state_key === 'draft').map(p => ({
                id: p.employee_id,
                name: p.name,
                department: p.department,
            }));

            // Employees without appraisal (appraisal_draft state)
            const employeesWithoutAppraisal = teamAppraisals.filter(a => a.state_key === 'appraisal_draft').map(a => ({
                id: a.employee_id,
                name: a.name,
                department: a.department,
            }));

            // Top and bottom performers
            const sortedAppraisals = [...teamAppraisals].sort((a, b) => (b.final_score || 0) - (a.final_score || 0));
            const topPerformers = sortedAppraisals.slice(0, 5).map(a => ({
                name: a.name,
                department: a.department,
                score: a.final_score,
                rating: a.rating,
            }));
            const bottomPerformers = sortedAppraisals.slice(-5).reverse().map(a => ({
                name: a.name,
                department: a.department,
                score: a.final_score,
                rating: a.rating,
            }));

            // Calculate department distribution for chart
            const deptDistribution = {};
            teamPlans.forEach(plan => {
                const dept = plan.department || 'No Department';
                deptDistribution[dept] = (deptDistribution[dept] || 0) + 1;
            });

            // Update selected_cycle with all calculated data
            this.state.selected_cycle = {
                ...this.state.selected_cycle,
                // Planning data
                total_team_members: totalTeamMembers,
                pending_plan_count: pendingPlans,
                approved_plan_count: approvedPlans,
                submitted_plan_count: submittedPlans,
                employees_without_plan: employeesWithoutPlan,
                employees_without_plan_count: employeesWithoutPlan.length,
                team_plans: teamPlans,
                pending_plan_list: pendingPlanList,  // Now shows correct plans for supervisor
                all_plans: teamPlans,

                // Appraisal data
                pending_appraisal_count: pendingAppraisals,
                completed_appraisal_count: completedAppraisals,
                avg_score: avgScore,
                employees_without_appraisal: employeesWithoutAppraisal,
                employees_without_appraisal_count: employeesWithoutAppraisal.length,
                team_appraisals: teamAppraisals,
                pending_appraisal_list: pendingAppraisalList,  // Now shows correct appraisals for supervisor
                all_appraisals: teamAppraisals,
                top_performers: topPerformers,
                bottom_performers: bottomPerformers,

                // Department distribution for chart
                dept_distribution: deptDistribution,
            };
            this.state.selected_cycle.appraisal_started = appraisalStartedCount;
this.state.selected_cycle.appraisal_approved = appraisalApprovedCount;

// Also set root level values
this.state.appraisal_started = appraisalStartedCount;
this.state.appraisal_approved = appraisalApprovedCount;

            console.log("Selected cycle updated with data:", this.state.selected_cycle);
            console.log("Pending plan list length:", this.state.selected_cycle.pending_plan_list.length);
            console.log("Pending plan list:", this.state.selected_cycle.pending_plan_list);
        }

    } catch (error) {
        console.error("Error loading cycle data:", error);
        this.state.cycle_planning_data = [];
        this.state.cycle_appraisal_data = [];
        this.state.cycle_top_performers = [];
        this.state.cycle_bottom_performers = [];
        this.state.cycle_pending_supervisor_list = [];
        this.state.cycle_pending_secondary_list = [];
        this.state.cycle_pending_reviewer_list = [];
        this.state.cycle_reminder_employees = [];
        this.state.filtered_cycle_planning_data = [];
    }
}

// Helper method to calculate department distribution
_calculateDeptDistribution = (teamPlans) => {
    const deptMap = {};
    teamPlans.forEach(plan => {
        const dept = plan.department || 'No Department';
        deptMap[dept] = (deptMap[dept] || 0) + 1;
    });
    return deptMap;
}

    closeCycleDetail = () => {
        this.state.current_view = 'overview';
        this.state.show_cycle_detail = false;
        this.state.selected_cycle = null;
        this.state.selected_cycle_id = null;
        this.state.cycle_planning_data = [];
        this.state.cycle_appraisal_data = [];
        this.state.cycle_top_performers = [];
        this.state.cycle_bottom_performers = [];
    }

   setCycleTab = async (tab) => {
    console.log("setCycleTab called with:", tab);

    this.state.cycle_active_tab = tab;

    // Render charts based on the selected tab
    if (tab === 'planning') {
        await this._renderPlanningChartsByRole();
    } else if (tab === 'appraisal') {
        await this._renderAppraisalChartsByRole();
    }
}

// Helper methods for chart rendering
_renderPlanningChartsByRole = async () => {
    console.log("=== _renderPlanningChartsByRole called ===");
    console.log("Current role:", this.state.role);
    console.log("Selected cycle:", this.state.selected_cycle);
    console.log("Planning data available:", this.state.selected_cycle?.team_plans?.length);

    if (this.state.role === 'supervisor') {
        console.log("Calling _renderSupervisorPlanningCharts");
        await this._renderSupervisorPlanningCharts(this.state.selected_cycle);
    } else if (this.state.role === 'reviewer') {
        console.log("Calling _renderReviewerPlanningCharts");
        await this._renderReviewerPlanningCharts(this.state.selected_cycle);
    } else if (this.state.role === 'hr_manager') {
        console.log("Calling _renderCyclePlanningCharts");
        await this._renderCyclePlanningCharts();
    }
}

    // ============================================================
// VIEW ALL PLANS - HR MANAGER FUNCTIONALITY
// ============================================================

onViewAllPlans = async () => {
    this.state.all_plans_loading = true;

    try {
        const cycle = this.state.selected_cycle;
        const plans = this.state.cycle_planning_data || [];

        // Fetch KRA lines for every plan
        const enriched = await Promise.all(plans.map(p => this._enrichPlanWithKRAs(p)));

        // Generate PDF directly (no preview modal)
        this._generateAllPlansPDF(enriched, cycle);

    } catch (error) {
        console.error("Error generating plans:", error);
        this.env.services.notification.add("Error generating plans", { type: "danger" });
    } finally {
        this.state.all_plans_loading = false;
    }
}


// Call this from onViewAllPlans
_generateAllPlansPDF = (plans, cycle) => {
 console.log("=== GENERATE PDF ===");
    console.log("Plans count:", plans.length);
    console.log("First plan kra_lines:", plans[0]?.kra_lines?.length);
    const allHTML = plans.map((plan, i) => `
        <div style="page-break-after:${i < plans.length - 1 ? 'always' : 'avoid'};">
            ${this._buildPlanHTML(plan, cycle)}
        </div>
    `).join('');

    const win = window.open('', '_blank');
    win.document.write(`<!DOCTYPE html><html><head>
        <title>${cycle.name || 'Plans'} – All Employee Plans</title>
        <style>
            * {
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
            body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
            @media print { body { padding: 0; } @page { margin: 15mm; } }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #c5d5ea; padding: 8px 12px; text-align: left; }
            th { background: #2563a8; color: #fff; }
        </style>
    </head><body>
        <div style="text-align:center; margin-bottom:20px; display:flex; gap:10px; justify-content:center;">
            <button onclick="window.print();" style="padding:10px 20px; background:#1a3557; color:#fff; border:none; border-radius:5px; cursor:pointer;">
                📄 Save as PDF / Print
            </button>
            <button onclick="window.close();" style="padding:10px 20px; background:#6c757d; color:#fff; border:none; border-radius:5px; cursor:pointer;">
                ✖ Close Window
            </button>
        </div>
        ${allHTML}
    </body></html>`);
    win.document.close();
    win.focus();
}

_enrichPlanWithKRAs = async (plan) => {
    try {
    console.log("=== ENRICH PLAN ===");
        console.log("Plan ID:", plan.plan_id || plan.id);
        console.log("Plan name:", plan.name);
        const result = await rpc("/hr_pms_dashboard/get_plan_kra_details", {
            plan_id: plan.plan_id || plan.id
        });

        // Debug: Log the result to see what's coming from backend
        console.log("=== Company Name Debug ===");
        console.log("Plan ID:", plan.plan_id || plan.id);
        console.log("Employee Name:", plan.name);
        console.log("Result from backend:", result);
        console.log("Company name from backend:", result.company_name);

        console.log("Result from backend:", result);
        console.log("kra_lines count:", result.kra_lines?.length);
        console.log("First kra_line:", result.kra_lines?.[0]);

        return {
            ...plan,
            kra_lines: result.kra_lines || [],
            company_name: result.company_name || 'My Company'
        };
    } catch (error) {
        console.error("Error fetching KRA details:", error);
        return { ...plan, kra_lines: [], company_name: 'My Company' };
    }
}


_buildPlanHTML = (plan, cycle) => {
 const companyName = plan.company_name
    const kras = plan.kra_lines || [];
    const kraRows = kras.length > 0
    ? kras.map((k, i) => `
        <tr style="background:${k.is_selected === false ? '#fff5f5' : (i % 2 === 0 ? '#fff' : '#f5f8fd')};">
            <td style="padding:8px 6px;border:1px solid #c5d5ea;font-size:11px;">${k.kra || ''}</td>
            <td style="padding:8px 6px;border:1px solid #c5d5ea;font-size:11px;">${k.kpi || ''}</td>
            <td style="padding:8px 6px;border:1px solid #c5d5ea;font-size:11px;">${k.description || ''}</td>
            <td style="padding:8px 6px;border:1px solid #c5d5ea;font-size:11px;">${k.criteria || ''}</td>
            <td style="padding:8px 6px;border:1px solid #c5d5ea;font-size:11px;text-align:center;font-weight:bold;color:#1a3557;">
                ${k.is_selected === false ? '<span style="color:#9e9e9e;font-style:italic;">— N/A</span>' : (k.score || '')}
            </td>
            <td style="padding:8px 6px;border:1px solid #c5d5ea;font-size:11px;">
                ${k.is_selected === false
                    ? '<span style="background:#fdecea;color:#c62828;padding:2px 8px;border-radius:10px;font-size:10px;">✕ Deselected</span>'
                    : (k.target || '<span style="background:#fff8e1;color:#f57c00;padding:2px 8px;border-radius:10px;font-size:10px;">Pending</span>')}
            </td>
        </tr>`).join('')
    : `<tr><td colspan="6" style="text-align:center;padding:20px;color:#999;font-size:12px;">No KRA lines found.</td></tr>`;

    return `
    <div style="font-family:Arial,sans-serif;">
         <div style="background:#1a3557;color:#fff;padding:14px 20px;text-align:center;">
            <div style="font-size:17px;font-weight:bold;">${companyName}</div>
            <div style="font-size:10px;color:#aecde8;margin-top:3px;">Employee Performance Appraisal Plan</div>
        </div>
        <div style="background:#2563a8;color:#fff;display:flex;justify-content:space-around;padding:7px 20px;">
            <div style="text-align:center;">
                <div style="font-size:9px;color:#aecde8;">Appraisal Cycle</div>
                <div style="font-size:11px;font-weight:bold;">${cycle.name || '-'}</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:9px;color:#aecde8;">Start Date</div>
                <div style="font-size:11px;font-weight:bold;">${cycle.start_date || '-'}</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:9px;color:#aecde8;">End Date</div>
                <div style="font-size:11px;font-weight:bold;">${cycle.end_date || '-'}</div>
            </div>
        </div>
        <div style="background:#eaf1fb;display:grid;grid-template-columns:1fr 1fr;border:1px solid #2563a8;">
            <div style="padding:10px 14px;border-right:1px solid #c5d5ea;">
                <div style="font-size:9px;color:#2563a8;font-weight:bold;">EMPLOYEE NAME</div>
                <div style="font-size:13px;">${plan.name || '-'}</div>
            </div>
            <div style="padding:10px 14px;">
                <div style="font-size:9px;color:#2563a8;font-weight:bold;">DEPARTMENT</div>
                <div style="font-size:13px;">${plan.department || '-'}</div>
            </div>
            <div style="padding:10px 14px;border-top:1px solid #c5d5ea;border-right:1px solid #c5d5ea;">
                <div style="font-size:9px;color:#2563a8;font-weight:bold;">SUPERVISOR</div>
                <div style="font-size:13px;">${plan.supervisor_name || '-'}</div>
            </div>
            <div style="padding:10px 14px;border-top:1px solid #c5d5ea;">
                <div style="font-size:9px;color:#2563a8;font-weight:bold;">MANAGER / REVIEWER</div>
                <div style="font-size:13px;">${plan.reviewer_name || plan.secondary_name || '-'}</div>
            </div>
        </div>
        <div style="background:#1a3557;color:#fff;padding:7px 12px;font-size:11px;font-weight:bold;text-align:center;margin-top:14px;">
            PERFORMANCE PLANNING TEMPLATE – KRA / KPI DETAILS
        </div>
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#2563a8;color:#fff;">
                    <th style="padding:8px 6px;border:1px solid #1a3557;font-size:10px;width:14%;">KRA / Goal</th>
                    <th style="padding:8px 6px;border:1px solid #1a3557;font-size:10px;width:14%;">KPI / Metric</th>
                    <th style="padding:8px 6px;border:1px solid #1a3557;font-size:10px;width:26%;">Description</th>
                    <th style="padding:8px 6px;border:1px solid #1a3557;font-size:10px;width:26%;">Criteria</th>
                    <th style="padding:8px 6px;border:1px solid #1a3557;font-size:10px;width:8%;">Score</th>
                    <th style="padding:8px 6px;border:1px solid #1a3557;font-size:10px;width:12%;">Target</th>
                 </tr>
            </thead>
            <tbody>${kraRows}</tbody>
        </table>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;border:1px solid #c5d5ea;margin-top:18px;background:#f5f8fd;">
            <div style="padding:12px;text-align:center;border-right:1px solid #c5d5ea;">
                <div style="font-size:10px;color:#666;">Employee Signature</div>
                <div style="margin-top:28px;border-top:1px solid #bbb;padding-top:4px;font-size:9px;color:#999;">${plan.name || ''}</div>
            </div>
            <div style="padding:12px;text-align:center;border-right:1px solid #c5d5ea;">
                <div style="font-size:10px;color:#666;">Supervisor Signature</div>
                <div style="margin-top:28px;border-top:1px solid #bbb;padding-top:4px;font-size:9px;color:#999;">${plan.supervisor_name || ''}</div>
            </div>
            <div style="padding:12px;text-align:center;">
                <div style="font-size:10px;color:#666;">Manager Signature</div>
                <div style="margin-top:28px;border-top:1px solid #bbb;padding-top:4px;font-size:9px;color:#999;">${plan.reviewer_name || plan.secondary_name || ''}</div>
            </div>
        </div>
    </div>`;
}



    // ============================================================
    // PLANNING EVENT HANDLERS
    // ============================================================
    onClickEmployeePlan = (item) => {
        console.log("onClickEmployeePlan called with:", item);
        this.state.selected_plan = item;
        console.log("selected_plan set to:", this.state.selected_plan);
    }

    onClosePlanModal = () => {
        this.state.selected_plan = null;
    }


// ============================================================
// VIEW ALL APPRAISALS - HR MANAGER FUNCTIONALITY
// ============================================================

// ============================================================
// VIEW ALL APPRAISALS - HR MANAGER FUNCTIONALITY
// ============================================================
viewAllEmployeeAppraisals = async () => {
    console.log("=== viewAllEmployeeAppraisals called ===");

    this.state.all_appraisals_loading = true;

    try {
        const cycle = this.state.selected_cycle;

        if (!cycle || !cycle.id) {
            this.env.services.notification.add("No cycle selected", { type: "warning" });
            this.state.all_appraisals_loading = false;
            return;
        }

        const result = await rpc("/hr_pms_dashboard/get_cycle_all_appraisals", {
            cycle_id: cycle.id,
        });

        console.log("Fetched appraisals:", result);

        if (result && !result.error && result.appraisals && result.appraisals.length > 0) {
            const appraisals = result.appraisals;

            this.state.all_appraisals_data = appraisals;
            this.state.all_appraisals_summary = result.summary;

            const cycleData = {
                name: cycle.name,
                start_date: cycle.start_date,
                end_date: cycle.end_date,
                company_name: this.state.all_appraisals_summary?.company_name || cycle.company_id?.name || 'My Company'
            };

            this._generateAllAppraisalsPDF(appraisals, cycleData);
        } else {
            this.env.services.notification.add(result?.error || "No appraisal data found for this cycle", { type: "warning" });
        }

    } catch (error) {
        console.error("Error generating appraisals:", error);
        this.env.services.notification.add("Error generating appraisals", { type: "danger" });
    } finally {
        this.state.all_appraisals_loading = false;
    }
}


// Generate PDF for all appraisals
_generateAllAppraisalsPDF = (appraisals, cycle) => {
    const companyName = this.state.all_appraisals_summary?.company_name || 'Company';

    const allHTML = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>${cycle.name || 'Appraisals'} – Employee Appraisal Report</title>
            <style>
                * {
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                }
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    font-size: 12px;
                }
                @media print {
                    body { padding: 0; }
                    @page { margin: 15mm; }
                    .no-print { display: none; }
                }
                .report-header {
                    background: #1a3557;
                    color: #fff;
                    padding: 20px;
                    text-align: center;
                }
                .report-header h1 {
                    margin: 0;
                    font-size: 20px;
                }
                .report-header p {
                    margin: 5px 0 0;
                    font-size: 12px;
                    color: #aecde8;
                }
                .cycle-info {
                    background: #2563a8;
                    color: #fff;
                    display: flex;
                    justify-content: space-between;
                    padding: 12px 20px;
                }
                .cycle-info div {
                    text-align: center;
                    flex: 1;
                }
                .cycle-info .label {
                    font-size: 9px;
                    color: #aecde8;
                }
                .cycle-info .value {
                    font-size: 12px;
                    font-weight: bold;
                }
                .summary-stats {
                    background: #eaf1fb;
                    display: flex;
                    justify-content: space-around;
                    padding: 15px;
                    border: 1px solid #2563a8;
                }
                .summary-stats div {
                    text-align: center;
                }
                .summary-stats .stat-value {
                    font-size: 22px;
                    font-weight: bold;
                    color: #1a3557;
                }
                .summary-stats .stat-label {
                    font-size: 11px;
                    color: #2563a8;
                    font-weight: bold;
                }
                .table-title {
                    background: #1a3557;
                    color: #fff;
                    padding: 10px;
                    font-size: 13px;
                    font-weight: bold;
                    text-align: center;
                    margin-top: 20px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 11px;
                }
                th {
                    background: #1a3557;
                    color: #fff;
                    padding: 10px 6px;
                    border: 1px solid #1a3557;
                    text-align: center;
                }
                td {
                    padding: 8px 6px;
                    border: 1px solid #c5d5ea;
                }
                .text-center { text-align: center; }
                .text-right  { text-align: right;  }
                .text-left   { text-align: left;   }
                .font-bold   { font-weight: bold;  }
                .footer {
                    text-align: center;
                    font-size: 8px;
                    color: #999;
                    margin-top: 20px;
                    padding-top: 10px;
                    border-top: 1px solid #eee;
                }
                .no-print {
                    text-align: center;
                    margin-bottom: 20px;
                }
                button {
                    padding: 10px 20px;
                    margin: 10px;
                    background: #1a3557;
                    color: #fff;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                }
                button:hover { opacity: 0.9; }
            </style>
        </head>
        <body>
            <div class="no-print">
                <button onclick="window.print();">📄 Save as PDF / Print</button>
                <button onclick="window.close();">✖ Close Window</button>
            </div>

            <!-- Header -->
            <div class="report-header">
                <h1>${this._escapeHtml(companyName)}</h1>
                <p>Employee Performance Appraisal Report</p>
            </div>

            <!-- Cycle Info -->
            <div class="cycle-info">
                <div>
                    <div class="label">Appraisal Cycle</div>
                    <div class="value">${this._escapeHtml(cycle.name || '-')}</div>
                </div>
                <div>
                    <div class="label">Start Date</div>
                    <div class="value">${cycle.start_date || '-'}</div>
                </div>
                <div>
                    <div class="label">End Date</div>
                    <div class="value">${cycle.end_date || '-'}</div>
                </div>
            </div>

            <!-- Summary Stats -->
            <div class="summary-stats">
                <div>
                    <div class="stat-value">${appraisals.length}</div>
                    <div class="stat-label">TOTAL EMPLOYEES</div>
                </div>
                <div>
                    <div class="stat-value">${appraisals.filter(a => a.final_score > 0).length}</div>
                    <div class="stat-label">COMPLETED</div>
                </div>
            </div>

            <!-- Appraisals Table -->
            <div class="table-title">EMPLOYEE APPRAISAL DETAILS</div>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Emp ID</th>
                        <th>Employee Name</th>
                        <th>Designation</th>
                        <th>Self</th>
                        <th>1st Mgr</th>
                        <th>2nd Mgr</th>
                        <th>Reviewer</th>
                        <th>Final</th>
                        <th>Rating</th>
                        <th>Bonus Eligibility %</th>
                        <th>Basic Pay</th>
                        <th>Bonus Amount</th>
                    </tr>
                </thead>
                <tbody>
                    ${appraisals.map((emp, idx) => {
                        const finalScore = emp.final_score || 0;
                        return `
                            <tr>
                                <td class="text-center">${idx + 1}</td>
                                <td class="text-center">${emp.employee_id || '-'}</td>
                                <td class="text-left font-bold">${this._escapeHtml(emp.name || '-')}</td>
                                <td class="text-left">${this._escapeHtml(emp.designation || '-')}</td>
                                <td class="text-center">${emp.self_score || 0}</td>
                                <td class="text-center">${emp.supervisor_score || 0}</td>
                                <td class="text-center">${emp.secondary_score || '-'}</td>
                                <td class="text-center">${emp.reviewer_score || 0}</td>
                                <td class="text-center font-bold">${finalScore}</td>
                                <td class="text-center">${emp.rating || '-'}</td>
                                <td class="text-center">${emp.eligibility_pct || 0}%</td>
                                <td class="text-right">${this._formatCurrency(emp.basic_pay || 0)}</td>
                                <td class="text-right font-bold">${this._formatCurrency(emp.bonus_amount || 0)}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>

            <!-- Footer -->
            <div class="footer">
                Generated on: ${new Date().toLocaleString()}
            </div>
        </body>
        </html>
    `;

    const win = window.open('', '_blank');
    win.document.write(allHTML);
    win.document.close();
    win.focus();
}

// Escape HTML special characters to prevent XSS in generated report
_escapeHtml = (text) => {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Format a number as a 2-decimal currency string
_formatCurrency = (amount) => {
    if (!amount) return '0.00';
    return amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
// Close modal
closeAllAppraisalsModal = () => {
    this.state.show_all_appraisals_modal = false;
    this.state.all_appraisals_data = [];
    this.state.all_appraisals_summary = null;
}

// Export to Excel
exportAllAppraisalsToExcel = () => {
    if (!this.state.all_appraisals_data || this.state.all_appraisals_data.length === 0) {
        this.env.services.notification.add("No data to export", { type: "warning" });
        return;
    }

    const cycle = this.state.selected_cycle;
    const employees = this.state.all_appraisals_data;

    const headers = [
        'Sl No', 'Emp ID', 'Employee Name', 'Designation', 'DOJ',
        'Self Rating', '1st Manager Score', '2nd Manager Score', 'Reviewer Score',
        'Final Score', 'Rating', 'Bonus Eligibility %', 'Basic Pay', 'Bonus Amount'  // ← updated
    ];

    const rows = employees.map((emp, idx) => [
        idx + 1,
        emp.employee_id,
        emp.name,
        emp.designation || '-',
        emp.doj || '-',
        emp.self_score || 0,
        emp.supervisor_score || 0,
        emp.secondary_score || '-',
        emp.reviewer_score || 0,
        emp.final_score || 0,
        emp.rating || '-',           // ← added rating (was missing before)
        emp.eligibility_pct || 0,    // ← was bvvp_percent
        emp.basic_pay || 0,
        emp.bonus_amount || 0,       // ← was bvvp_payable
    ]);

    const csvLines = [];
    csvLines.push(`Cycle: ${cycle?.name || ''}`);
    csvLines.push(`Generated: ${new Date().toLocaleString()}`);
    csvLines.push('');
    csvLines.push(headers.join(','));

    rows.forEach(row => {
        const escapedRow = row.map(cell => {
            if (typeof cell === 'string' && (cell.includes(',') || cell.includes('"'))) {
                return `"${cell.replace(/"/g, '""')}"`;
        }
            return cell;
        });
        csvLines.push(escapedRow.join(','));
    });

    const blob = new Blob(["\uFEFF" + csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${cycle?.name || 'cycle'}_appraisals.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.env.services.notification.add("Exported successfully!", { type: "success" });
}

    onClickNotStarted = () => {
        const ids = this.state.employees_without_plan.map(function(e) { return e.id; });
        if (ids.length) {
            let url = '/web#model=hr.employee&view=list&domain=' + encodeURIComponent(JSON.stringify([["id", "in", ids]]));
            window.open(url, '_blank');
        }
    }

    onClickCreatePlan = () => {
    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'pms.appraisal',
        views: [[false, 'form']],
        target: 'current',
        context: {
            'default_employee_id': this.state.employee_id
        }
    });
}

onOpenPastCycle = (history) => {
    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'pms.cycle',
        res_id: history.id,
        views: [[false, 'form']],
        target: 'current',
    });
}

onDoAction = (action) => {
    if (action.action_type === 'complete_plan') {
        this.onOpenPlanRecord({ id: action.plan_id, plan_id: action.plan_id, state_key: 'draft' });
    } else if (action.action_type === 'start_appraisal') {
        this.onOpenAppraisalRecord({ id: action.appraisal_id });
    } else if (action.action_type === 'view_plan') {
        this.onOpenPlanRecord({ id: action.plan_id });
    } else if (action.action_type === 'view_appraisal') {
        this.onOpenAppraisalRecord({ id: action.appraisal_id });
    } else {
        if (action.plan_id) {
            this.onOpenPlanRecord({ id: action.plan_id });
        } else if (action.appraisal_id) {
            this.onOpenAppraisalRecord({ id: action.appraisal_id });
        }
    }
}

onOpenPlanRecord = (plan) => {
 console.log('onOpenPlanRecord called with:', JSON.stringify(plan));
    const planId = plan.plan_id || plan.id;

    if (!planId) {
        console.warn('onOpenPlanRecord: missing plan id');
        this.env.services.notification.add("Cannot open plan: Invalid data", { type: "warning" });
        return;
    }

    const isDraft = plan.state_key === 'draft';
    const isPendingApproval = plan.state_key === 'pending_supervisor' ||
                              plan.state_key === 'pending_secondary_supervisor' ||
                              plan.state_key === 'pending_reviewer';

    const formViewRef = isPendingApproval
        ? 'hr_employee_evaluation.view_employee_plans_supervisor_form'
        : 'hr_employee_evaluation.view_employee_performance_planning_form';

    const title = isPendingApproval ? 'Review Performance Plan'
                : isDraft ? 'Edit My Performance Plan'
                : 'My Performance Plan';

    this.action.doAction({
        type: 'ir.actions.act_window',
        name: title,
        res_model: 'pms.appraisal',
        res_id: planId,
        views: [[false, 'form']],
        target: 'current',
        context: {
            'create': false,
            'delete': false,
            'form_view_ref': formViewRef,
        },
    });
}
onOpenAppraisalRecord = (appraisal) => {
    // Check if it's an event object
    if (appraisal && appraisal.constructor && appraisal.constructor.name === 'PointerEvent') {
        console.error("Wrong parameter passed to onOpenAppraisalRecord");
        return;
    }

    const appraisalId = appraisal.id || appraisal.appraisal_id;

    if (!appraisalId) {
        console.error("onOpenAppraisalRecord: missing appraisal id", appraisal);
        this.env.services.notification.add("Cannot open appraisal: Invalid data", { type: "danger" });
        return;
    }

    console.log("Opening appraisal record ID:", appraisalId);
    console.log("User role:", this.state.role);

    // This opens the actual Odoo form
    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'pms.appraisal',
        res_id: appraisalId,
        views: [[false, 'form']],
        target: 'current',
        context: {
            'form_view_ref': 'hr_employee_evaluation.view_pms_appraisal_form',
            'default_phase': this.state.role === 'reviewer' ? 'appraisal' : 'planning',
        },
    });
}
// Method to open full plan details modal
openFullPlanDetails = (plan) => {
    console.log("Opening full plan details for:", plan);

    // Add additional fields to the plan object
    this.state.selected_full_plan = {
        ...plan,
        cycle_id: plan.cycle_id || plan.id,
        evaluation_group: plan.evaluation_group || '-',
        supervisor_name: plan.supervisor_name || '-',
        secondary_name: plan.secondary_name || null,
        reviewer_name: plan.reviewer_name || null,
        phase: 'Planning',
    };
    this.state.show_full_plan_details = true;
}

// Method to close full plan details modal
closeFullPlanDetails = () => {
    this.state.show_full_plan_details = false;
    this.state.selected_full_plan = null;
}

exportPlanToExcel = () => {
    if (!this.state.selected_full_plan || !this.state.selected_full_plan.kpis) {
        this.env.services.notification.add('No data to export', { type: 'warning' });
        return;
    }

    const plan = this.state.selected_full_plan;
    const kpis = plan.kpis;

    // ── Clean: strips newlines + collapses spaces + truncates ────
    const clean = (val, maxLen = 100) => {
        if (!val) return '-';
        return String(val)
            .replace(/\r\n/g, ' ')
            .replace(/\n/g, ' ')
            .replace(/\r/g, ' ')
            .replace(/\s+/g, ' ')
            .trim()
            .substring(0, maxLen);
    };

    const escape = (val) => {
        const str = clean(val);
        return str.includes(',') || str.includes('"')
            ? `"${str.replace(/"/g, '""')}"`
            : str;
    };

    const csvLines = [
        `Plan For:,${escape(plan.name || plan.employee_name || '')}`,
        `Cycle Name:,${escape(plan.cycle || '')}`,
        `Cycle ID:,${escape(plan.cycle_id || '-')}`,
        `Department:,${escape(plan.department || '-')}`,
        `Evaluation Group:,${escape(plan.evaluation_group || '-')}`,
        `Planning Phase:,${escape(plan.phase || 'Planning')}`,
        `Primary Manager:,${escape(plan.supervisor_name || '-')}`,
        `Secondary Manager:,${escape(plan.secondary_name || '-')}`,
        `Reviewer:,${escape(plan.reviewer_name || '-')}`,
        `Status:,${escape(plan.state || '-')}`,
        `Total Weightage:,${escape(plan.total_weightage || 0)}%`,
        ``,
        `KRA / GOAL,KPI / METRIC,DESCRIPTION,CRITERIA,SCORE (WEIGHTAGE),TARGET`,
    ];

    const grouped = {};
    kpis.forEach(kpi => {
        const kra = kpi.kra_name || 'No KRA';
        if (!grouped[kra]) grouped[kra] = [];
        grouped[kra].push(kpi);
    });

    Object.entries(grouped).forEach(([kraName, kraKpis]) => {
        kraKpis.forEach((kpi, index) => {
            const row = [
                index === 0 ? kraName : '',
                kpi.kpi_name || '-',
                clean(kpi.description, 100),  // ← newlines stripped
                clean(kpi.criteria, 100),      // ← newlines stripped
                `${kpi.weightage || 0}%`,
                kpi.target || 'Not Set',
            ];
            csvLines.push(row.map(escape).join(','));
        });
    });

    csvLines.push(`Total KPIs Selected:,${escape(plan.selected_kpi_count || 0)},,,,,`);
    csvLines.push(`Total KPIs Available:,${escape(plan.total_kpi_count || 0)},,,,,`);
    csvLines.push(`Plan Progress:,${escape(plan.progress || 0)}%,,,,,`);

    const blob = new Blob(["\uFEFF" + csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${plan.cycle || 'plan'}_${plan.name || 'details'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.env.services.notification.add("Exported successfully!", { type: "success" });
}

// Export to PDF
exportPlanToPDF = async () => {


    const modalBody = document.querySelector('.pms_plan_modal_body');
    if (!modalBody) return;

    // Clone and fix the element for PDF rendering
    const element = modalBody.cloneNode(true);

    // ── Force all content visible (remove scroll constraints) ──
    element.style.maxHeight = 'none';
    element.style.overflow = 'visible';
    element.style.height = 'auto';

    // Also fix any inner scrollable divs (tables, etc.)
    element.querySelectorAll('*').forEach(el => {
        el.style.overflow = 'visible';
        el.style.maxHeight = 'none';
    });

    const opt = {
        margin: [0.4, 0.4, 0.4, 0.4],
        filename: `${this.state.selected_full_plan.cycle || 'plan'}_details.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: {
            scale: 2,
            letterRendering: true,
            useCORS: true,
            scrollX: 0,
            scrollY: 0,
            windowWidth: document.documentElement.scrollWidth,
        },
        jsPDF: {
            unit: 'in',
            format: 'a4',
            orientation: 'landscape'
        },
        pagebreak: {
            mode: ['avoid-all', 'css', 'legacy'],  // ← key fix for multi-page
            before: '.pdf-page-break-before',
            after:  '.pdf-page-break-after',
            avoid:  ['tr', 'td', '.pms_breakdown_item'],  // don't break inside rows
        }
    };

    this.env.services.notification.add("Exporting to PDF...", { type: "info" });

    html2pdf()
        .set(opt)
        .from(element)
        .toPdf()
        .get('pdf')
        .then(pdf => {
            // ── Add page numbers at the bottom ──────────────────
            const totalPages = pdf.internal.getNumberOfPages();
            for (let i = 1; i <= totalPages; i++) {
                pdf.setPage(i);
                pdf.setFontSize(8);
                pdf.setTextColor(150);
                pdf.text(
                    `Page ${i} of ${totalPages}`,
                    pdf.internal.pageSize.getWidth() / 2,
                    pdf.internal.pageSize.getHeight() - 0.2,
                    { align: 'center' }
                );
            }
        })
        .save();
}

// Export Appraisal to Excel
exportAppraisalToExcel = () => {
    if (!this.state.selected_full_appraisal) {
        this.env.services.notification.add("No data to export", { type: "warning" });
        return;
    }

    const appraisal = this.state.selected_full_appraisal;

    const escape = (val) => {
        const str = String(val ?? '-');
        return str.includes(',') || str.includes('"') || str.includes('\n')
            ? `"${str.replace(/"/g, '""')}"`
            : str;
    };

    const csvLines = [
        // Header Information
        `Appraisal For:,${escape(appraisal.name)}`,
        `Cycle Name:,${escape(appraisal.cycle)}`,
        `Department:,${escape(appraisal.department)}`,
        `Status:,${escape(appraisal.state)}`,
        `Primary Manager:,${escape(appraisal.supervisor_name)}`,
        `Secondary Manager:,${escape(appraisal.secondary_name || '-')}`,
        `Reviewer:,${escape(appraisal.reviewer_name || '-')}`,
        `Total Weightage:,${escape(appraisal.total_weightage || 0)}%`,
        ``,
        // KPI Scores Section
        `KPI SCORES,,,,,,`,
        `KPI,Weightage,Emp Score,1st Manager,2nd Manager,Reviewer Score`,
    ];

    // Add KPI rows
    if (appraisal.kpi_lines && appraisal.kpi_lines.length > 0) {
        appraisal.kpi_lines.forEach(line => {
            csvLines.push([
                escape(line.kpi_name),
                escape(line.weightage || 0),
                escape(line.self_score || '-'),
                escape(line.supervisor_score || '-'),
                escape(line.secondary_score || '-'),
                escape(line.reviewer_score || '-'),
            ].join(','));
        });
    } else {
        csvLines.push(`No KPI data found,,,,,`);
    }

    csvLines.push(``);
    csvLines.push(`COMPETENCY SCORES,,,,,,`);
    csvLines.push(`Competency,Weightage,Emp Score,1st Manager,2nd Manager,Reviewer Score`);

    // Add Competency rows
    if (appraisal.competency_lines && appraisal.competency_lines.length > 0) {
        appraisal.competency_lines.forEach(line => {
            csvLines.push([
                escape(line.competency_name),
                escape(line.weightage || 0),
                escape(line.self_score || '-'),
                escape(line.supervisor_score || '-'),
                escape(line.secondary_score || '-'),
                escape(line.reviewer_score || '-'),
            ].join(','));
        });
    } else {
        csvLines.push(`No competency data found,,,,,`);
    }

    csvLines.push(``);
    csvLines.push(`FINAL SCORE SUMMARY,,,,,,`);
    csvLines.push(`KPI Total:,${escape(appraisal.kpi_total || 0)},,,,`);
    csvLines.push(`Competency Total:,${escape(appraisal.competency_total || 0)},,,,`);
    csvLines.push(`Final Score:,${escape(appraisal.final_score || 0)},,,,`);
    csvLines.push(`Rating:,${escape(appraisal.rating || '-')},,,,`);

    csvLines.push(`Rating:,${escape(appraisal.rating || '-')},,,,`);

    // ── Bonus Summary ─────────────────────────────────────────
    csvLines.push(``);
    csvLines.push(`BONUS SUMMARY,,,,,,`);
    csvLines.push(`Rating Tier:,${escape(appraisal.rating || '-')},,,,`);
    csvLines.push(`Basic Pay:,${escape(appraisal.basic_pay_display || appraisal.basic_pay || 0)},,,,`);
    csvLines.push(`Bonus Eligibility %:,${escape(appraisal.eligibility_pct || 0)}%,,,,`);
    csvLines.push(`Bonus Amount:,${escape(appraisal.bonus_amount_display || appraisal.bonus_amount || 0)},,,,`);
    // ─────────────────────────────────────────────────────────

    const blob = new Blob(["\uFEFF" + csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${appraisal.cycle || 'appraisal'}_${appraisal.name || 'details'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.env.services.notification.add("Exported successfully!", { type: "success" });
}

exportAppraisalToPDF = async () => {
    const appraisal = this.state.selected_full_appraisal;
    if (!appraisal) return;

    this.env.services.notification.add("Preparing PDF...", { type: "info" });

    const bonusSection = (appraisal.bonus_amount || appraisal.eligibility_pct) ? `
        <div style="margin-top:18px;background:#eaf1fb;border:1px solid #2563a8;border-radius:6px;padding:14px;">
            <div style="font-weight:bold;color:#1a3557;font-size:12px;margin-bottom:10px;">BONUS SUMMARY</div>
            <table style="width:100%;border-collapse:collapse;font-size:11px;">
                <tr>
                    <td style="padding:6px 10px;border:1px solid #c5d5ea;font-weight:bold;">Rating Tier</td>
                    <td style="padding:6px 10px;border:1px solid #c5d5ea;">${appraisal.rating || '-'}</td>
                    <td style="padding:6px 10px;border:1px solid #c5d5ea;font-weight:bold;">Basic Pay</td>
                    <td style="padding:6px 10px;border:1px solid #c5d5ea;">${appraisal.basic_pay_display || appraisal.basic_pay || '-'}</td>
                </tr>
                <tr>
                    <td style="padding:6px 10px;border:1px solid #c5d5ea;font-weight:bold;">Eligibility %</td>
                    <td style="padding:6px 10px;border:1px solid #c5d5ea;">${appraisal.eligibility_pct || 0}%</td>
                    <td style="padding:6px 10px;border:1px solid #c5d5ea;font-weight:bold;color:#198754;">Bonus Amount</td>
                    <td style="padding:6px 10px;border:1px solid #c5d5ea;font-weight:bold;color:#198754;">${appraisal.bonus_amount_display || appraisal.bonus_amount || '-'}</td>
                </tr>
            </table>
        </div>` : '';

    const kpiRows = (appraisal.kpi_lines || []).map(l => `
        <tr>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;">${l.kpi_name || '-'}</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.weightage || 0}%</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.self_score || 0}</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.supervisor_score || 0}</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.secondary_score || '-'}</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.reviewer_score || 0}</td>
        </tr>`).join('');

    const compRows = (appraisal.competency_lines || []).map(l => `
        <tr>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;">${l.competency_name || '-'}</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.self_score || 0}</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.supervisor_score || 0}</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.secondary_score || '-'}</td>
            <td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.reviewer_score || 0}</td>
        </tr>`).join('');

    const html = `
        <div style="font-family:Arial,sans-serif;padding:16px;">
            <div style="background:#1a3557;color:#fff;padding:14px;text-align:center;font-size:16px;font-weight:bold;">
                Performance Appraisal — ${appraisal.name || ''}
            </div>
            <div style="background:#2563a8;color:#fff;display:flex;justify-content:space-around;padding:8px;">
                <div><span style="font-size:9px;color:#aecde8;">Cycle</span><br/><b>${appraisal.cycle || '-'}</b></div>
                <div><span style="font-size:9px;color:#aecde8;">Department</span><br/><b>${appraisal.department || '-'}</b></div>
                <div><span style="font-size:9px;color:#aecde8;">Status</span><br/><b>${appraisal.state || '-'}</b></div>
                <div><span style="font-size:9px;color:#aecde8;">Final Score</span><br/><b>${appraisal.final_score || 0}</b></div>
                <div><span style="font-size:9px;color:#aecde8;">Rating</span><br/><b>${appraisal.rating || '-'}</b></div>
            </div>

            ${kpiRows ? `
            <div style="margin-top:14px;">
                <div style="background:#1a3557;color:#fff;padding:7px;font-size:11px;font-weight:bold;">KPI SCORES</div>
                <table style="width:100%;border-collapse:collapse;font-size:11px;">
                    <thead><tr style="background:#2563a8;color:#fff;">
                        <th style="padding:7px;border:1px solid #1a3557;">KPI</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:8%;">Weight</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:10%;">Self</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:10%;">1st Mgr</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:10%;">2nd Mgr</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:10%;">Reviewer</th>
                    </tr></thead>
                    <tbody>${kpiRows}</tbody>
                </table>
            </div>` : ''}

            ${compRows ? `
            <div style="margin-top:14px;">
                <div style="background:#1a3557;color:#fff;padding:7px;font-size:11px;font-weight:bold;">COMPETENCY SCORES</div>
                <table style="width:100%;border-collapse:collapse;font-size:11px;">
                    <thead><tr style="background:#2563a8;color:#fff;">
                        <th style="padding:7px;border:1px solid #1a3557;">Competency</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:10%;">Self</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:10%;">1st Mgr</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:10%;">2nd Mgr</th>
                        <th style="padding:7px;border:1px solid #1a3557;width:10%;">Reviewer</th>
                    </tr></thead>
                    <tbody>${compRows}</tbody>
                </table>
            </div>` : ''}

            <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center;background:#f5f8fd;border:1px solid #c5d5ea;padding:10px;">
                <div><div style="font-size:10px;color:#666;">KPI Total</div><div style="font-size:16px;font-weight:bold;color:#1a3557;">${appraisal.kpi_total || 0}</div></div>
                <div><div style="font-size:10px;color:#666;">Competency Total</div><div style="font-size:16px;font-weight:bold;color:#1a3557;">${appraisal.competency_total || 0}</div></div>
                <div><div style="font-size:10px;color:#666;">Final Score</div><div style="font-size:16px;font-weight:bold;color:#198754;">${appraisal.final_score || 0}</div></div>
            </div>

            ${bonusSection}
        </div>`;

    const element = document.createElement('div');
    element.innerHTML = html;
    document.body.appendChild(element);

    const opt = {
        margin: [0.4, 0.4, 0.4, 0.4],
        filename: `${appraisal.cycle || 'appraisal'}_${appraisal.name || 'details'}.pdf`.replace(/\s+/g, '_'),
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, scrollX: 0, scrollY: 0 },
        jsPDF: { unit: 'in', format: 'a4', orientation: 'landscape' },
        pagebreak: { mode: ['avoid-all', 'css', 'legacy'], avoid: ['tr', 'td'] },
    };

    try {
        await html2pdf().set(opt).from(element).save();
        this.env.services.notification.add("PDF exported!", { type: "success" });
    } catch (e) {
        this.env.services.notification.add("PDF export failed", { type: "danger" });
    } finally {
        document.body.removeChild(element);
    }
}

filterCycleAppraisalData = () => {
    const search = this.state.cycle_appraisal_search?.toLowerCase() || '';
    if (!search) {
        this.state.filtered_cycle_appraisal_data = [...(this.state.cycle_appraisal_data || [])];
    } else {
        this.state.filtered_cycle_appraisal_data = (this.state.cycle_appraisal_data || []).filter(appraisal =>
            appraisal.name?.toLowerCase().includes(search) ||
            appraisal.department?.toLowerCase().includes(search) ||
            appraisal.evaluation_group?.toLowerCase().includes(search)
        );
    }
}

// Filter completed cycles based on search
filterCompletedCycles = () => {
    const searchTerm = this.state.completed_cycle_search?.toLowerCase().trim() || '';
    if (!searchTerm) {
        this.state.filtered_past_cycles = [...(this.state.employee?.past_cycles || [])];
    } else {
        this.state.filtered_past_cycles = (this.state.employee?.past_cycles || []).filter(cycle =>
            cycle.cycle_name?.toLowerCase().includes(searchTerm)
        );
    }
}
// Replace your existing onOpenCompletedCycleDetail with this:
onOpenCompletedCycleDetail = async (cycle) => {
    console.log("Opening completed cycle:", cycle);

    this.state.selected_completed_cycle = null;

    try {
        const result = await rpc("/hr_pms_dashboard/get_employee_completed_cycle_detail", {
            cycle_id: cycle.id,
            employee_id: this.state.employee_id,
        });

        console.log("API result:", result);

        // Debug bonus data
        console.log("=== BONUS DATA DEBUG ===");
        console.log("eligibility_pct:", result.eligibility_pct);
        console.log("bonus_amount:", result.bonus_amount);
        console.log("bonus_amount_display:", result.bonus_amount_display);
        console.log("basic_pay_display:", result.basic_pay_display);

        // Check if bonus data exists but condition is failing
        if (result.eligibility_pct > 0 || result.bonus_amount > 0) {
            console.log("✅ Bonus data exists!");
        } else {
            console.log("❌ No bonus data found for this employee/cycle");
        }

        this.state.selected_completed_cycle = {
            id: cycle.id,
            cycle_name: cycle.cycle_name || '-',
            completed_date: cycle.completed_date || '-',
            start_date: cycle.start_date || '-',
            end_date: cycle.end_date || '-',
            final_score: cycle.final_score || 0,
            rating: cycle.rating || '—',
            rating_class: cycle.rating_class || 'bg-secondary',
            plan_progress: cycle.plan_progress || 0,
            appraisal_progress: cycle.appraisal_progress || 0,
            employee_name: result.employee_name || '-',
            department: result.department || '-',
            supervisor_name: result.supervisor_name || '-',
            secondary_name: result.secondary_name || null,
            reviewer_name: result.reviewer_name || null,
            total_weightage: result.total_weightage || 0,
            kpi_total: result.kpi_total || 0,
            competency_total: result.competency_total || 0,
            kpi_lines: Array.isArray(result.kpi_lines) ? result.kpi_lines : [],
            competency_lines: Array.isArray(result.competency_lines) ? result.competency_lines : [],
              eligibility_pct: result.eligibility_pct || 0,
            bonus_amount: result.bonus_amount || 0,
            basic_pay: result.basic_pay || 0,
            bonus_amount_display: result.bonus_amount_display,
            basic_pay_display: result.basic_pay_display,
             calculation_method: result.calculation_method || '—',
        };

    } catch (error) {
        console.error('Failed to load completed cycle details:', error);
        this.state.selected_completed_cycle = {
            id: cycle.id,
            cycle_name: cycle.cycle_name || '-',
            completed_date: cycle.completed_date || '-',
            start_date: cycle.start_date || '-',
            end_date: cycle.end_date || '-',
            final_score: cycle.final_score || 0,
            rating: cycle.rating || '—',
            rating_class: cycle.rating_class || 'bg-secondary',
            plan_progress: cycle.plan_progress || 0,
            appraisal_progress: cycle.appraisal_progress || 0,
            employee_name: '-',
            department: '-',
            supervisor_name: '-',
            secondary_name: null,
            reviewer_name: null,
            total_weightage: 0,
            kpi_total: 0,
            competency_total: 0,
            kpi_lines: [],
            competency_lines: [],
        };
    }
}

openCompletedCycleDetailModal = async (cycleId) => {
    const cycle = this.state.filtered_completed_cycles_list.find(c => c.id === cycleId)
                  || this.state.completed_cycles_list.find(c => c.id === cycleId);

    if (!cycle) {
        console.warn('Cycle not found:', cycleId);
        return;
    }

    this.state.selected_completed_cycle = cycle;
    this.state.completed_cycle_employees = [];
    this.state.show_completed_cycle_modal = true;

    try {
        const result = await rpc(          // ✅ not this.rpc
            "/hr_pms_dashboard/get_completed_cycle_appraisals",
            { cycle_id: cycle.id }
        );

        if (result && result.appraisals) {
            this.state.completed_cycle_employees = result.appraisals;
        }
    } catch (error) {
        console.error('Failed to load completed cycle appraisals:', error);
        this.state.completed_cycle_employees = [];
    }
}

closeCompletedCycleModal = () => {
    this.state.show_completed_cycle_modal = false;
    this.state.selected_completed_cycle = null;
    this.state.completed_cycle_employees = [];
}

clearCompletedCyclesSearch = () => {
    this.state.completed_cycle_search = '';
    this.filterCompletedCyclesList();
}

    onPlanningSearch = (ev) => {
        const q = (this.state.planningSearch || "").toLowerCase().trim();
        if (!q) {
            this.state.planning_employee_list_filtered = null;
        } else {
            this.state.planning_employee_list_filtered = this.state.planning_employee_list.filter(function(p) {
                return p.name.toLowerCase().includes(q) || (p.department || "").toLowerCase().includes(q);
            });
        }
    }

    filterNoPlanEmployees = () => {
        const search = this.state.no_plan_search.toLowerCase();
        if (!search) {
            this.state.filtered_no_plan_employees = [...this.state.employees_no_plan];
        } else {
            this.state.filtered_no_plan_employees = this.state.employees_no_plan.filter(function(emp) {
                return emp.name.toLowerCase().includes(search) || emp.department.toLowerCase().includes(search);
            });
        }
    }

    filterCyclePlanningData = () => {
        const search = this.state.cycle_planning_search.toLowerCase();
        if (!search) {
            this.state.filtered_cycle_planning_data = [...this.state.cycle_planning_data];
        } else {
            this.state.filtered_cycle_planning_data = this.state.cycle_planning_data.filter(function(plan) {
            // After setting filtered_cycle_planning_data, add:

                return plan.name.toLowerCase().includes(search) || plan.department.toLowerCase().includes(search);
            });
        }
    }
    sendReminder = (emp) => {
        rpc("/hr_pms_dashboard/send_reminder", {
            'employee_id': emp.employee_id,
            'cycle_id': this.state.selected_cycle_id
        }).then(function(result) {
            if (result.success) {
                this.env.services.notification.add("Reminder sent successfully!", { type: "success" });
            }
        }.bind(this)).catch(function(error) {
            this.env.services.notification.add("Failed to send reminder", { type: "danger" });
        }.bind(this));
    }

    filterNoAppraisalEmployees = () => {
        const search = this.state.no_appraisal_search.toLowerCase();
        if (!search) {
            this.state.filtered_no_appraisal_employees = [...this.state.employees_no_appraisal];
        } else {
            this.state.filtered_no_appraisal_employees = this.state.employees_no_appraisal.filter(function(emp) {
                return emp.name.toLowerCase().includes(search) || emp.department.toLowerCase().includes(search);
            });
        }
    }

    filterHierarchy = () => {
        let filtered = [...this.state.hierarchy_employees];

        if (this.state.hierarchy_dept_filter) {
            filtered = filtered.filter(function(emp) { return emp.department === this.state.hierarchy_dept_filter; }.bind(this));
        }
        if (this.state.hierarchy_group_filter) {
            filtered = filtered.filter(function(emp) { return emp.evaluation_group === this.state.hierarchy_group_filter; }.bind(this));
        }
        if (this.state.hierarchy_search) {
            const search = this.state.hierarchy_search.toLowerCase();
            filtered = filtered.filter(function(emp) {
                return emp.name.toLowerCase().includes(search) || emp.department.toLowerCase().includes(search);
            });
        }

        this.state.filtered_hierarchy_employees = filtered;
    }

    filterAppraisalEmployees = () => {
        const search = this.state.appraisal_search.toLowerCase();
        if (!search) {
            this.state.filtered_appraisal_employees = [...this.state.appraisal_employees];
        } else {
            this.state.filtered_appraisal_employees = this.state.appraisal_employees.filter(function(emp) {
                return emp.name.toLowerCase().includes(search) || emp.department.toLowerCase().includes(search);
            });
        }
    }

    filterAppraisalNotStarted = () => {
        const search = this.state.appraisal_not_started_search.toLowerCase();
        if (!search) {
            this.state.filtered_appraisal_not_started = [...this.state.appraisal_not_started_list];
        } else {
            this.state.filtered_appraisal_not_started = this.state.appraisal_not_started_list.filter(function(emp) {
                return emp.name.toLowerCase().includes(search) || emp.department.toLowerCase().includes(search);
            });
        }
    }

    filterAppraisalNoRecord = () => {
        const search = this.state.appraisal_no_record_search.toLowerCase();
        if (!search) {
            this.state.filtered_appraisal_no_record = [...this.state.appraisal_no_record_list];
        } else {
            this.state.filtered_appraisal_no_record = this.state.appraisal_no_record_list.filter(function(emp) {
                return emp.name.toLowerCase().includes(search) || emp.department.toLowerCase().includes(search);
            });
        }
    }

    filterAppraisalDraft = () => {
        const search = this.state.appraisal_draft_search.toLowerCase();
        if (!search) {
            this.state.filtered_appraisal_draft = [...this.state.appraisal_draft_list];
        } else {
            this.state.filtered_appraisal_draft = this.state.appraisal_draft_list.filter(function(emp) {
                return emp.name.toLowerCase().includes(search) || emp.department.toLowerCase().includes(search);
            });
        }
    }

    onClickNotStartedAppraisal = () => {
        const ids = this.state.appraisal_not_started_list.map(function(e) { return e.id; });
        if (ids.length) {
            let url = '/web#model=hr.employee&view=list&domain=' + encodeURIComponent(JSON.stringify([["id", "in", ids]]));
            window.open(url, '_blank');
        }
    }

  onClickEmployeeAppraisal = (appraisal) => {
    console.log("Opening appraisal for:", appraisal);

    // Get the appraisal ID
    const appraisalId = appraisal.id || appraisal.appraisal_id || appraisal.plan_id;

    if (!appraisalId) {
        console.error("Missing appraisal id", appraisal);
        this.env.services.notification.add("Cannot open appraisal: Missing ID", { type: "danger" });
        return;
    }

    // Call the existing function that opens the Odoo form
    this.onOpenAppraisalRecord({ id: appraisalId });
}

async _loadData() {
    try {
        const data = await rpc("/hr_pms_dashboard/data", {requested_role: this.state.requestedRole,});
        if (data.error) {
            this.state.error = data.error + (data.traceback ? '\n' + data.traceback : '');
            this.state.loading = false;
            return;
        }

        // Store all data in cache
        this._dataCache = data;

        // ============================================================
        // HANDLE BASED ON REQUESTED ROLE FROM MENU
        // ============================================================

        // HR MANAGER VIEW - Full analytics dashboard
        if (this.state.requestedRole === 'hr_manager' && data.role === 'hr_manager') {
            this.state.current_view = 'hr_manager';
            this.state.role = 'hr_manager';
            this.state.loading = false;

            // Load HR specific data
            this.state.stats = data.stats || {};
            this.state.stats.employees_in_active_cycles = data.employees_in_active_cycles || 0;
            this.state.all_cycles = data.all_cycles || [];
            this.state.active_cycles_list = data.active_cycles_list || [];
            this.state.completed_cycles_list = data.completed_cycles_list || [];
            this.state.all_cycles_count = data.all_cycles ? data.all_cycles.length : 0;
            this.state.active_cycles_count = data.active_cycles_count || (data.stats && data.stats.active_cycles_count ? data.stats.active_cycles_count : 0) || 0;
            this.state.completed_cycles_count = (data.completed_cycles_list ? data.completed_cycles_list.length : 0);
            this.state.overview_stats = data.overview_stats || {};
            this.state.score_engine = data.score_engine || null;
            this.state.appraisal_breakdown = data.appraisal_breakdown || [];
            this.state.planning_dates = data.planning_dates || null;
            this.state.appraisal_dates = data.appraisal_dates || null;
            this.state.participation = data.participation || null;
            this.state.top_performers = data.top_performers || [];
            this.state.bottom_performers = data.bottom_performers || [];
            this.state.active_cycles = data.active_cycles || [];

            // Employee lists for HR
            this.state.employees_no_plan = data.employees_no_plan || [];
            this.state.employees_no_appraisal = data.employees_no_appraisal || [];
            this.state.hierarchy_employees = data.hierarchy_employees || [];
            this.state.department_list = data.department_list || [];
            this.state.evaluation_group_list = data.evaluation_group_list || [];
            this.state.employees_no_plan_count = data.employees_no_plan_count || 0;
            this.state.employees_no_appraisal_count = data.employees_no_appraisal_count || 0;
            this.state.employees_with_plan = data.employees_with_plan || [];

            this.state.filtered_no_plan_employees = [...this.state.employees_no_plan];
            this.state.filtered_no_appraisal_employees = [...this.state.employees_no_appraisal];
            this.state.filtered_hierarchy_employees = [...this.state.hierarchy_employees];

            this.state.completed_cycles_list = data.completed_cycles_list || [];
            this.state.filtered_completed_cycles_list = [...(data.completed_cycles_list || [])];  // ADD THIS
            this.state.completed_cycles_search = '';  // ADD THIS

            await this.loadPlanningTabData();
            await this._ensureChartJS();
            await this._waitForDOM(200);
            await this._renderChartsForTab(this.state.activeTab, data);
            return;
        }

        // EMPLOYEE ONLY VIEW - My Performance
        if (this.state.requestedRole === 'employee' && data.employee) {
            this.state.current_view = 'employee';
            this.state.role = 'employee';  // ← ADD THIS
            this.state.employee = data.employee;
            if (this.state.employee && this.state.employee.past_cycles) {
            this.state.filtered_past_cycles = [...this.state.employee.past_cycles];
}
            this.state.employee_id = data.employee_id || 0;
            this.state.employee_name = data.employee_name || "";
            this.state.loading = false;

            await this._ensureChartJS();
            await this._waitForDOM(200);
            this._destroyAllCharts();
            await this._renderEmployeeDashboardCharts(data);
            return;
        }

        // SUPERVISOR VIEW - My Team
        if (this.state.requestedRole === 'supervisor' && data.supervisor) {
            this.state.current_view = 'supervisor';
            this.state.role = 'supervisor';  // ← ADD THIS
            this.state.supervisor = data.supervisor;
            this.state.employee_id = data.employee_id || 0;
            this.state.employee_name = data.employee_name || "";
            this.state.loading = false;

            // Render supervisor charts if needed
            await this._ensureChartJS();
            await this._renderSupervisorCharts(data);
            return;
        }

        // REVIEWER VIEW - My Reviews
        if (this.state.requestedRole === 'reviewer' && data.reviewer) {
            this.state.current_view = 'reviewer';
            this.state.role = 'reviewer';  // ← ADD THIS
            this.state.reviewer = data.reviewer;
            this.state.employee_id = data.employee_id || 0;
            this.state.employee_name = data.employee_name || "";
            this.state.loading = false;

            // Render reviewer charts if needed
            await this._ensureChartJS();
            await this._renderReviewerCharts(data);
            return;
        }

        // ============================================================
        // FALLBACK: COMBINED VIEW (Multiple roles - Tabbed interface)
        // ============================================================
        this.state.current_view = 'combined';
        this.state.role = data.role;
        this.state.roles = data.roles || [];
        this.state.employee_id = data.employee_id || 0;
        this.state.employee_name = data.employee_name || "";

        // Load all role data
        this.state.employee = data.employee || null;
        this.state.supervisor = data.supervisor || null;
        this.state.secondary = data.secondary || null;
        this.state.reviewer = data.reviewer || null;
        this.state.score_engine = data.score_engine || null;

        // HR data (if user has HR access in combined view)
        if (data.stats) {
            this.state.stats = data.stats || {};
            this.state.stats.employees_in_active_cycles = data.employees_in_active_cycles || 0;
            this.state.all_cycles = data.all_cycles || [];
            this.state.active_cycles_list = data.active_cycles_list || [];
            this.state.completed_cycles_list = data.completed_cycles_list || [];
            this.state.overview_stats = data.overview_stats || {};
            this.state.participation = data.participation || null;
            this.state.top_performers = data.top_performers || [];
            this.state.bottom_performers = data.bottom_performers || [];
        }

        // Appraisal data
        this.state.appraisal_no_record_list = data.appraisal_no_record_list || [];
        this.state.filtered_appraisal_no_record = [...this.state.appraisal_no_record_list];
        this.state.appraisal_draft_list = data.appraisal_draft_list || [];
        this.state.filtered_appraisal_draft = [...this.state.appraisal_draft_list];
        this.state.appraisal_employees = data.appraisal_employees || [];
        this.state.filtered_appraisal_employees = [...this.state.appraisal_employees];
        this.state.appraisal_not_started_list = data.appraisal_not_started_list || [];
        this.state.filtered_appraisal_not_started = [...this.state.appraisal_not_started_list];

        // Employee lists
        this.state.employees_with_plan = data.employees_with_plan || [];
        this.state.employees_no_appraisal = data.employees_no_appraisal || [];
        this.state.employees_no_plan = data.employees_no_plan || [];
        this.state.hierarchy_employees = data.hierarchy_employees || [];
        this.state.department_list = data.department_list || [];
        this.state.evaluation_group_list = data.evaluation_group_list || [];
        this.state.employees_no_plan_count = data.employees_no_plan_count || 0;
        this.state.employees_no_appraisal_count = data.employees_no_appraisal_count || 0;

        this.state.filtered_no_plan_employees = [...this.state.employees_no_plan];
        this.state.filtered_no_appraisal_employees = [...this.state.employees_no_appraisal];
        this.state.filtered_hierarchy_employees = [...this.state.hierarchy_employees];

        // Pending lists
        this.state.pending_manager_list = data.pending_manager_list || [];
        this.state.pending_secondary_list = data.pending_secondary_list || [];
        this.state.pending_reviewer_list = data.pending_reviewer_list || [];
        this.state.pending_appraisal_manager_list = data.pending_appraisal_manager_list || [];
        this.state.pending_appraisal_secondary_list = data.pending_appraisal_secondary_list || [];
        this.state.pending_appraisal_reviewer_list = data.pending_appraisal_reviewer_list || [];

        this.state.loading = false;

        // Load planning tab data and render charts based on active tab
        await this.loadPlanningTabData();

        // Determine which tab to show first (prefer employee if available)
        if (this.state.roles.includes('employee') && this.state.activeTab === 'overview') {
            this.state.activeTab = 'employee';
        }

        if (this.state.activeTab === 'employee' && this.state.employee) {
            await this._ensureChartJS();
            await this._waitForDOM(200);
            await this._renderEmployeeDashboardCharts(data);
        } else if (this.state.activeTab !== 'employee' && this._dataCache && this.state.role === "hr_manager") {
            await this._ensureChartJS();
            await this._waitForDOM(200);
            await this._renderChartsForTab(this.state.activeTab, data);
        }

        console.log("Appraisal employees loaded:", this.state.appraisal_employees.length);
        console.log("First appraisal employee:", this.state.appraisal_employees[0]);

    } catch (e) {
        console.error("Dashboard load error:", e);
        this.state.error = "Failed to load dashboard data. Please refresh.";
        this.state.loading = false;
    }
}

    async setTab(tab) {
        if (this.state.activeTab === tab) return;
        this._destroyAllCharts();
        this.state.activeTab = tab;
        this.state.current_view = 'main';

        if (tab === 'planning') {
            await this.loadPlanningTabData();
        }
        if (this._dataCache && this.state.role === "hr_manager") {
            await this._ensureChartJS();
            await this._waitForDOM(200);
            await this._renderChartsForTab(tab, this._dataCache);
        }
    }

    async _ensureChartJS() {
    await new Promise(function(resolve) {
        var check = function() {
            if (window.Chart) {
                resolve();
            } else {
                setTimeout(check, 100);
            }
        };
        check();
    });
}
    async _waitForDOM(ms) {
        await new Promise(function(resolve) { setTimeout(resolve, ms); });
    }

    _destroyAllCharts() {
    // Destroy all chart instances from our tracking array
    if (this.chartInstances && this.chartInstances.length) {
        this.chartInstances.forEach(chart => {
            try {
                if (chart && typeof chart.destroy === 'function') {
                    chart.destroy();
                }
            } catch (e) {
                console.warn("Error destroying chart:", e);
            }
        });
        this.chartInstances = [];
    }

    // Also destroy any charts attached directly to canvas elements
    const canvasRefs = [
        'empPlanningStatusChartRef',
        'empAppraisalStatusChartRef',
        'cyclePlansDeptChartRef',
        'cyclePlansGroupChartRef',
        'cyclePlanStatusChartRef',
        'supervisorDeptChartRef',
        'supervisorScoreChartRef',
        'reviewerDeptChartRef',
        'reviewerScoreChartRef',
        'stateChartRef',
        'phaseChartRef',
        'evalGroupChartRef',
        'deptGroupChartRef',
        'participationChartRef',
        'scoreDeptChartRef',
        'scoreGroupChartRef',
        'scoreDistChartRef',
        'appraisalStatusChartRef',
        'appraisalEvalGroupChartRef',
        'empDeptChartRef',
        'empEvalGroupChartRef',
        'empGenderChartRef'
    ];

    canvasRefs.forEach(refName => {
        const ref = this[refName];
        if (ref && ref.el) {
            try {
                const existingChart = window.Chart?.getChart(ref.el);
                if (existingChart) {
                    existingChart.destroy();
                }
            } catch (e) {
                // Ignore errors
            }
        }
    });
}

  async _renderEmployeeDashboardCharts(data) {
    if (!data.employee) return;
     console.log("=== CHART DEBUG ===");
    console.log("current_cycle:", data.employee.current_cycle);
    console.log("current_cycle.phase:", data.employee.current_cycle?.phase);
    console.log("current_plan:", data.employee.current_plan);
    console.log("current_plan exists:", !!data.employee.current_plan);
    console.log("empPlanningStatusChartRef:", this.empPlanningStatusChartRef);
    console.log("empPlanningStatusChartRef.el:", this.empPlanningStatusChartRef?.el);
    console.log("Canvas width:", this.empPlanningStatusChartRef?.el?.clientWidth);
    console.log("Canvas height:", this.empPlanningStatusChartRef?.el?.clientHeight);

    // ============================================================
    // DESTROY EXISTING CHARTS BEFORE CREATING NEW ONES
    // ============================================================
    if (this.empPlanningStatusChartRef && this.empPlanningStatusChartRef.el) {
        const existingChart = window.Chart?.getChart(this.empPlanningStatusChartRef.el);
        if (existingChart) {
            existingChart.destroy();
        }
        // Clear the canvas
        const ctx = this.empPlanningStatusChartRef.el.getContext("2d");
        ctx.clearRect(0, 0, this.empPlanningStatusChartRef.el.width, this.empPlanningStatusChartRef.el.height);
    }

    if (this.empAppraisalStatusChartRef && this.empAppraisalStatusChartRef.el) {
        const existingChart = window.Chart?.getChart(this.empAppraisalStatusChartRef.el);
        if (existingChart) {
            existingChart.destroy();
        }
        const ctx = this.empAppraisalStatusChartRef.el.getContext("2d");
        ctx.clearRect(0, 0, this.empAppraisalStatusChartRef.el.width, this.empAppraisalStatusChartRef.el.height);
    }

    const Chart = window.Chart;
    if (!Chart) return;

    const base = { responsive: true, maintainAspectRatio: false, layout: { padding: 4 } };
    const legendSm = { labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 6 } };

    // ============================================================
    // PLANNING PHASE CHART
    // ============================================================
    if (this.empPlanningStatusChartRef && this.empPlanningStatusChartRef.el && data.employee.current_plan) {
        const plan = data.employee.current_plan;
        const stateKey = plan.state_key;

        console.log("Planning State Key:", stateKey);  // Debug log

        // Define colors based on status
        let completedColor, statusText;

        switch(stateKey) {
            case 'draft':
                completedColor = "#6c757d";  // Grey for Draft
                statusText = "Draft - Not Started";
                break;
            case 'pending_supervisor':
                completedColor = "#0d6efd";  // Blue for 1st Approver
                statusText = "Pending 1st Approval";
                break;
            case 'pending_secondary_supervisor':
                completedColor = "#ffc107";  // Yellow for 2nd Approver
                statusText = "Pending 2nd Approval";
                break;
            case 'pending_reviewer':
                completedColor = "#6f42c1";  // Purple for Final Review
                statusText = "Pending Final Review";
                break;
            case 'approved':
                completedColor = "#198754";  // Green for Approved
                statusText = "Approved";
                break;
            default:
                completedColor = "#6c757d";
                statusText = stateKey || "Unknown Status";
        }

        const progress = plan.progress || 0;
        const remaining = 100 - progress;

        this.chartInstances.push(new Chart(this.empPlanningStatusChartRef.el, {
            type: "doughnut",
            data: {
                labels: [`${statusText} (${progress}%)`, `Remaining (${remaining}%)`],
                datasets: [{
                    data: [progress, remaining],
                    backgroundColor: [completedColor, "#e9ecef"],
                    borderWidth: 1,
                    borderColor: "#fff"
                }]
            },
            options: {
                ...base,
                cutout: "60%",
                plugins: {
                    legend: { position: "right", ...legendSm },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.dataIndex === 0) {
                                    return `Status: ${statusText} - ${context.parsed}% complete`;
                                } else {
                                    return `Remaining: ${context.parsed}% to complete`;
                                }
                            }
                        }
                    }
                }
            }
        }));
    } else if (this.empPlanningStatusChartRef && this.empPlanningStatusChartRef.el && !data.employee.current_plan) {
        const ctx = this.empPlanningStatusChartRef.el.getContext("2d");
        ctx.font = "13px sans-serif";
        ctx.fillStyle = "#adb5bd";
        ctx.textAlign = "center";
        ctx.fillText("No active plan", this.empPlanningStatusChartRef.el.width / 2, 90);
    }

    // ============================================================
    // APPRAISAL PHASE CHART
    // ============================================================
    if (this.empAppraisalStatusChartRef && this.empAppraisalStatusChartRef.el && data.employee.current_appraisal) {
        const appraisal = data.employee.current_appraisal;
        const stateKey = appraisal.state_key;

        console.log("Appraisal State Key:", stateKey);  // Debug log

        // Define colors based on status
        let completedColor, statusText;

        switch(stateKey) {
            case 'appraisal_draft':
                completedColor = "#6c757d";  // Grey for Draft/Self Rating not started
                statusText = "Self Rating Pending";
                break;
            case 'appraisal_pending_supervisor':
                completedColor = "#0d6efd";  // Blue for 1st Rating
                statusText = "Pending 1st Rating";
                break;
            case 'appraisal_pending_secondary_supervisor':
                completedColor = "#ffc107";  // Yellow for 2nd Rating
                statusText = "Pending 2nd Rating";
                break;
            case 'appraisal_pending_reviewer':
                completedColor = "#6f42c1";  // Purple for Final Review
                statusText = "Pending Final Rating";
                break;
            case 'appraisal_approved':
                completedColor = "#198754";  // Green for Completed
                statusText = "Appraisal Completed";
                break;
            default:
                completedColor = "#6c757d";
                statusText = stateKey || "Unknown Status";
        }

        const progress = appraisal.progress || 0;
        const remaining = 100 - progress;

        this.chartInstances.push(new Chart(this.empAppraisalStatusChartRef.el, {
            type: "doughnut",
            data: {
                labels: [`${statusText} (${progress}%)`, `Remaining (${remaining}%)`],
                datasets: [{
                    data: [progress, remaining],
                    backgroundColor: [completedColor, "#e9ecef"],
                    borderWidth: 1,
                    borderColor: "#fff"
                }]
            },
            options: {
                ...base,
                cutout: "60%",
                plugins: {
                    legend: { position: "right", ...legendSm },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.dataIndex === 0) {
                                    return `Status: ${statusText} - ${context.parsed}% complete`;
                                } else {
                                    return `Remaining: ${context.parsed}% to complete`;
                                }
                            }
                        }
                    }
                }
            }
        }));
    } else if (this.empAppraisalStatusChartRef && this.empAppraisalStatusChartRef.el && !data.employee.current_appraisal) {
        const ctx = this.empAppraisalStatusChartRef.el.getContext("2d");
        ctx.font = "13px sans-serif";
        ctx.fillStyle = "#adb5bd";
        ctx.textAlign = "center";
        ctx.fillText("No active appraisal", this.empAppraisalStatusChartRef.el.width / 2, 90);
    }
}

    async _renderCycleScoreCharts(cycleData) {
        const Chart = window.Chart;
        if (!Chart) return;

        const base = { responsive: true, maintainAspectRatio: false, layout: { padding: 4 } };
        const axisH = {
            x: { beginAtZero: true, max: 100, ticks: { font: { size: 10 }, color: "#6c757d" }, grid: { color: "rgba(0,0,0,0.04)" } },
            y: { grid: { display: false }, ticks: { font: { size: 10 }, color: "#6c757d" } }
        };

        // Score by department chart
        // FIX: replaced optional chaining ?.
        if (this.cycleScoreDeptChartRef.el && cycleData.score_by_dept_chart && cycleData.score_by_dept_chart.labels && cycleData.score_by_dept_chart.labels.length) {
            this.chartInstances.push(new Chart(this.cycleScoreDeptChartRef.el, {
                type: "bar",
                data: {
                    labels: cycleData.score_by_dept_chart.labels,
                    datasets: [{
                        label: "Avg Score",
                        data: cycleData.score_by_dept_chart.data,
                        backgroundColor: "#20c997",
                        borderRadius: 4,
                        barPercentage: 0.55
                    }]
                },
                options: { ...base, indexAxis: "y", plugins: { legend: { display: false } }, scales: axisH }
            }));
        }

        // Score by group chart
        // FIX: replaced optional chaining ?.
        if (this.cycleScoreGroupChartRef.el && cycleData.score_by_group_chart && cycleData.score_by_group_chart.labels && cycleData.score_by_group_chart.labels.length) {
            this.chartInstances.push(new Chart(this.cycleScoreGroupChartRef.el, {
                type: "bar",
                data: {
                    labels: cycleData.score_by_group_chart.labels,
                    datasets: [{
                        label: "Avg Score",
                        data: cycleData.score_by_group_chart.data,
                        backgroundColor: "#6f42c1",
                        borderRadius: 4,
                        barPercentage: 0.55
                    }]
                },
                options: { ...base, indexAxis: "y", plugins: { legend: { display: false } }, scales: axisH }
            }));
        }

        // Score distribution chart
        // FIX: replaced optional chaining ?.
        if (this.cycleScoreDistChartRef.el && cycleData.score_dist_chart && cycleData.score_dist_chart.labels && cycleData.score_dist_chart.labels.length) {
            const scores = cycleData.score_dist_chart.data;
            const bgColors = scores.map(function(s) {
                return s >= 90 ? "#198754" : s >= 75 ? "#0d6efd" : s >= 60 ? "#ffc107" : s >= 40 ? "#fd7e14" : "#dc3545";
            });
            this.chartInstances.push(new Chart(this.cycleScoreDistChartRef.el, {
                type: "bar",
                data: {
                    labels: cycleData.score_dist_chart.labels,
                    datasets: [{
                        label: "Final Score",
                        data: scores,
                        backgroundColor: bgColors,
                        borderRadius: 4,
                        barPercentage: 0.7
                    }]
                },
                options: {
                    ...base,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: { font: { size: 9 }, color: "#6c757d", maxRotation: 45 } },
                        y: { beginAtZero: true, max: 100, ticks: { font: { size: 10 }, color: "#6c757d" }, grid: { color: "rgba(0,0,0,0.04)" } }
                    }
                }
            }));
        }
    }

    async _renderChartsForTab(tab, data) {
        this._destroyAllCharts();
        await this._waitForDOM(50);

        const Chart = window.Chart;
        if (!Chart) {
            console.error("Chart.js not loaded");
            return;
        }

        console.log("Rendering charts for tab:", tab);

        const COLORS = ["#0d6efd", "#e83e8c", "#20c997", "#fd7e14", "#6f42c1", "#198754", "#ffc107", "#0dcaf0", "#dc3545", "#6c757d"];
        const axisSm = {
            x: { grid: { display: false }, ticks: { font: { size: 10 }, color: "#6c757d" } },
            y: { beginAtZero: true, ticks: { font: { size: 10 }, color: "#6c757d" }, grid: { color: "rgba(0,0,0,0.04)" } }
        };
        const legendSm = { labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 6 } };
        const base = { responsive: true, maintainAspectRatio: false, layout: { padding: 4 } };

        if (tab === "overview") {
            const legendSmOv = { labels: { boxWidth: 9, boxHeight: 9, font: { size: 11 }, padding: 8 } };
            const axisH = {
                x: { beginAtZero: true, max: 100, ticks: { font: { size: 10 }, color: "#6c757d" }, grid: { color: "rgba(0,0,0,0.04)" } },
                y: { grid: { display: false }, ticks: { font: { size: 10 }, color: "#6c757d" } }
            };

            const isPlanningActive = data.planning_dates && data.planning_dates.days_left !== null && data.planning_dates.days_left >= 0;
            const isAppraisalActive = data.appraisal_dates && data.appraisal_dates.days_left !== null && data.appraisal_dates.days_left >= 0;

            if (this.overviewPlanningParticipationChartRef.el && data.participation) {
                const p = data.participation;
                let withCount, withoutCount, labelPrefix;

                if (isPlanningActive) {
                    withCount = (data.stats && data.stats.planning_count) ? data.stats.planning_count : p.participated;
                    withoutCount = Math.max(0, p.total - withCount);
                    labelPrefix = "In planning";
                } else if (isAppraisalActive) {
                    withCount = (data.stats && data.stats.appraisal_count) ? data.stats.appraisal_count : 0;
                    withoutCount = Math.max(0, p.total - withCount);
                    labelPrefix = "In appraisal";
                } else {
                    withCount = (data.stats && data.stats.planning_count) ? data.stats.planning_count : p.participated;
                    withoutCount = Math.max(0, p.total - withCount);
                    labelPrefix = "With Plan";
                }

                this.chartInstances.push(new Chart(this.overviewPlanningParticipationChartRef.el, {
                    type: "doughnut",
                    data: {
                        labels: [labelPrefix + ' (' + withCount + ')', 'Not started (' + withoutCount + ')'],
                        datasets: [{
                            data: [withCount, withoutCount],
                            backgroundColor: ["#0d6efd", "#e9ecef"],
                            borderWidth: 2,
                            borderColor: "#fff"
                        }]
                    },
                    options: {
                        ...base,
                        cutout: "65%",
                        plugins: {
                            legend: { position: "bottom", ...legendSmOv },
                            tooltip: {
                                callbacks: {
                                    label: function(ctx) {
                                        const pct = Math.round(ctx.parsed / p.total * 100);
                                        return ' ' + ctx.label + ' — ' + pct + '%';
                                    }
                                }
                            }
                        }
                    }
                }));
            }

            if (isPlanningActive && this.overviewPlanningStatusChartRef.el && data.state_chart) {
                const planningLabels = data.state_chart.labels.slice(0, 5);
                const planningData = data.state_chart.data.slice(0, 5);
                const planColors = ["#6c757d", "#0d6efd", "#ffc107", "#6f42c1", "#198754"];
                const hasData = planningData.some(function(v) { return v > 0; });

                if (hasData) {
                    this.chartInstances.push(new Chart(this.overviewPlanningStatusChartRef.el, {
                        type: "doughnut",
                        data: {
                            labels: planningLabels,
                            datasets: [{ data: planningData, backgroundColor: planColors, borderWidth: 2, borderColor: "#fff" }]
                        },
                        options: { ...base, cutout: "60%", plugins: { legend: { position: "right", ...legendSmOv } } }
                    }));
                } else {
                    const ctx = this.overviewPlanningStatusChartRef.el.getContext("2d");
                    ctx.font = "13px sans-serif";
                    ctx.fillStyle = "#adb5bd";
                    ctx.textAlign = "center";
                    ctx.fillText("No plans created yet", this.overviewPlanningStatusChartRef.el.width / 2, 90);
                }
            } else if (isAppraisalActive && this.overviewAppraisalStatusChartRef.el && data.state_chart) {
                const appraisalLabels = data.state_chart.labels.slice(5, 10);
                const appraisalData = data.state_chart.data.slice(5, 10);
                const apprColors = ["#adb5bd", "#0dcaf0", "#fd7e14", "#e83e8c", "#20c997"];
                const hasData = appraisalData.some(function(v) { return v > 0; });

                if (hasData) {
                    this.chartInstances.push(new Chart(this.overviewAppraisalStatusChartRef.el, {
                        type: "doughnut",
                        data: {
                            labels: appraisalLabels,
                            datasets: [{ data: appraisalData, backgroundColor: apprColors, borderWidth: 2, borderColor: "#fff" }]
                        },
                        options: { ...base, cutout: "60%", plugins: { legend: { position: "right", ...legendSmOv } } }
                    }));
                } else {
                    const ctx = this.overviewAppraisalStatusChartRef.el.getContext("2d");
                    ctx.font = "13px sans-serif";
                    ctx.fillStyle = "#adb5bd";
                    ctx.textAlign = "center";
                    ctx.fillText("No appraisals started yet", this.overviewAppraisalStatusChartRef.el.width / 2, 90);
                }
            } else if (this.overviewPlanningStatusChartRef && this.overviewPlanningStatusChartRef.el) {
                const ctx = this.overviewPlanningStatusChartRef.el.getContext("2d");
                ctx.font = "13px sans-serif";
                ctx.fillStyle = "#adb5bd";
                ctx.textAlign = "center";
                ctx.fillText("No active phase", this.overviewPlanningStatusChartRef.el.width / 2, 90);
            }

            // FIX: replaced optional chaining ?.
            if (this.overviewScoreDeptChartRef.el && data.score_by_dept_chart && data.score_by_dept_chart.labels && data.score_by_dept_chart.labels.length) {
                this.chartInstances.push(new Chart(this.overviewScoreDeptChartRef.el, {
                    type: "bar",
                    data: {
                        labels: data.score_by_dept_chart.labels,
                        datasets: [{
                            label: "Avg score",
                            data: data.score_by_dept_chart.data,
                            backgroundColor: "#20c997",
                            borderRadius: 4,
                            barPercentage: 0.55
                        }]
                    },
                    options: { ...base, indexAxis: "y", plugins: { legend: { display: false } }, scales: axisH }
                }));
            } else if (this.overviewScoreDeptChartRef.el) {
                const ctx = this.overviewScoreDeptChartRef.el.getContext("2d");
                ctx.font = "13px sans-serif";
                ctx.fillStyle = "#adb5bd";
                ctx.textAlign = "center";
                ctx.fillText("No completed appraisals yet", this.overviewScoreDeptChartRef.el.width / 2, 90);
            }
        }

        if (tab === "planning") {
            console.log("Rendering PLANNING charts");

            if (this.participationChartRef.el && data.participation) {
                const withPlan = data.participation.participated || 0;
                const withoutPlan = data.participation.not_participated || 0;

                this.chartInstances.push(new Chart(this.participationChartRef.el, {
                    type: "doughnut",
                    data: {
                        labels: ['With Plan (' + withPlan + ')', 'Without Plan (' + withoutPlan + ')'],
                        datasets: [{ data: [withPlan, withoutPlan], backgroundColor: ["#0d6efd", "#e9ecef"], borderWidth: 1, borderColor: "#fff" }]
                    },
                    options: { ...base, cutout: "62%", plugins: { legend: { position: "bottom", ...legendSm } } }
                }));
            }

            if (this.stateChartRef.el && data.state_chart) {
                const planningLabels = data.state_chart.labels.slice(0, 5);
                const planningData = data.state_chart.data.slice(0, 5);
                const planningColors = ["#6c757d", "#0d6efd", "#ffc107", "#6f42c1", "#198754"];
                const planningStateKeys = ['draft', 'pending_supervisor', 'pending_secondary_supervisor', 'pending_reviewer', 'approved'];
                const self = this;

                this.chartInstances.push(new Chart(this.stateChartRef.el, {
                    type: "doughnut",
                    data: {
                        labels: planningLabels,
                        datasets: [{ data: planningData, backgroundColor: planningColors, borderWidth: 1, borderColor: "#fff" }]
                    },
                    options: {
                        ...base, cutout: "60%",
                        plugins: { legend: { position: "right", ...legendSm } },
                        onClick: function(e, els) {
                            if (els.length) self.navigateTo("pms.appraisal", [["state", "=", planningStateKeys[els[0].index]]], planningLabels[els[0].index]);
                        }
                    }
                }));
            }

            if (this.evalGroupChartRef.el && data.eval_group_chart) {
                const labels = data.eval_group_chart.labels;
                const self = this;
                this.chartInstances.push(new Chart(this.evalGroupChartRef.el, {
                    type: "bar",
                    data: {
                        labels: labels,
                        datasets: [{
                            label: "Plans",
                            data: data.eval_group_chart.planning,
                            backgroundColor: "#0d6efd",
                            borderRadius: 4,
                            barPercentage: 0.65
                        }]
                    },
                    options: {
                        ...base,
                        plugins: { legend: { display: false } },
                        scales: axisSm,
                        onClick: function(e, els) {
                            if (els.length) self.navigateTo("pms.appraisal", [["employee_id.evaluation_group_id.name", "=", labels[els[0].index]]], labels[els[0].index]);
                        }
                    }
                }));
            }
        }

        if (tab === "appraisal") {
            console.log("Rendering APPRAISAL charts");
            if (this.appraisalDeptChartRef && this.appraisalDeptChartRef.el && data.appraisal_dept_chart) {
                const chartData = data.appraisal_dept_chart;
                if (chartData.labels && chartData.labels.length > 0) {
                    this.chartInstances.push(new Chart(this.appraisalDeptChartRef.el, {
                        type: "bar",
                        data: {
                            labels: chartData.labels,
                            datasets: [
                                {
                                    label: "In Progress",
                                    data: chartData.in_progress,
                                    backgroundColor: "#fd7e14",
                                    borderRadius: 4,
                                    barPercentage: 0.65,
                                },
                                {
                                    label: "Completed",
                                    data: chartData.completed,
                                    backgroundColor: "#198754",
                                    borderRadius: 4,
                                    barPercentage: 0.65,
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: "top", labels: { boxWidth: 10, font: { size: 11 } } },
                                tooltip: {
                                    callbacks: {
                                        label: function(ctx) {
                                            return ctx.dataset.label + ': ' + ctx.parsed.y;
                                        }
                                    }
                                }
                            },
                            scales: {
                                x: {
                                    ticks: { font: { size: 10 }, maxRotation: 45, autoSkip: true },
                                    grid: { display: false }
                                },
                                y: {
                                    beginAtZero: true,
                                    ticks: { stepSize: 1, font: { size: 10 } },
                                    grid: { color: "rgba(0,0,0,0.04)" }
                                }
                            }
                        }
                    }));
                } else {
                    const ctx = this.appraisalDeptChartRef.el.getContext("2d");
                    ctx.font = "13px sans-serif";
                    ctx.fillStyle = "#adb5bd";
                    ctx.textAlign = "center";
                    ctx.fillText("No appraisal data available", this.appraisalDeptChartRef.el.width / 2, 90);
                }
            }

            if (this.appraisalStatusChartRef.el && data.appraisal_status_chart) {
                const statusColors = ["#6c757d", "#0d6efd", "#ffc107", "#6f42c1", "#198754"];
                this.chartInstances.push(new Chart(this.appraisalStatusChartRef.el, {
                    type: "doughnut",
                    data: {
                        labels: data.appraisal_status_chart.labels,
                        datasets: [{ data: data.appraisal_status_chart.data, backgroundColor: statusColors, borderWidth: 1, borderColor: "#fff" }]
                    },
                    options: { ...base, cutout: "60%", plugins: { legend: { position: "right", ...legendSm } } }
                }));
            }

            if (this.appraisalEvalGroupChartRef.el && data.appraisal_eval_group_chart) {
                const chartData = data.appraisal_eval_group_chart;
                this.chartInstances.push(new Chart(this.appraisalEvalGroupChartRef.el, {
                    type: "bar",
                    data: {
                        labels: chartData.labels,
                        datasets: [{
                            label: "Appraisals",
                            data: chartData.data,
                            backgroundColor: "#6f42c1",
                            borderRadius: 4,
                            barPercentage: 0.65
                        }]
                    },
                    options: { ...base, plugins: { legend: { display: false } }, scales: axisSm }
                }));
            }
        }

        if (tab === "scores") {
            console.log("Rendering SCORES charts");
            const axisH = {
                x: { beginAtZero: true, max: 100, ticks: { font: { size: 10 }, color: "#6c757d" }, grid: { color: "rgba(0,0,0,0.04)" } },
                y: { grid: { display: false }, ticks: { font: { size: 10 }, color: "#6c757d" } }
            };

            // FIX: replaced optional chaining ?.
            if (this.scoreDeptChartRef.el && data.score_by_dept_chart && data.score_by_dept_chart.labels && data.score_by_dept_chart.labels.length) {
                this.chartInstances.push(new Chart(this.scoreDeptChartRef.el, {
                    type: "bar",
                    data: { labels: data.score_by_dept_chart.labels, datasets: [{ label: "Avg Score", data: data.score_by_dept_chart.data, backgroundColor: "#20c997", borderRadius: 4, barPercentage: 0.55 }] },
                    options: { ...base, indexAxis: "y", plugins: { legend: { display: false } }, scales: axisH }
                }));
            }

            // FIX: replaced optional chaining ?.
            if (this.scoreGroupChartRef.el && data.score_by_group_chart && data.score_by_group_chart.labels && data.score_by_group_chart.labels.length) {
                this.chartInstances.push(new Chart(this.scoreGroupChartRef.el, {
                    type: "bar",
                    data: { labels: data.score_by_group_chart.labels, datasets: [{ label: "Avg Score", data: data.score_by_group_chart.data, backgroundColor: "#6f42c1", borderRadius: 4, barPercentage: 0.55 }] },
                    options: { ...base, indexAxis: "y", plugins: { legend: { display: false } }, scales: axisH }
                }));
            }

            // FIX: replaced optional chaining ?.
            if (this.scoreDistChartRef.el && data.score_dist_chart && data.score_dist_chart.labels && data.score_dist_chart.labels.length) {
                const scores = data.score_dist_chart.data;
                const bgColors = scores.map(function(s) {
                    return s >= 90 ? "#198754" : s >= 75 ? "#0d6efd" : s >= 60 ? "#ffc107" : s >= 40 ? "#fd7e14" : "#dc3545";
                });
                this.chartInstances.push(new Chart(this.scoreDistChartRef.el, {
                    type: "bar",
                    data: { labels: data.score_dist_chart.labels, datasets: [{ label: "Final Score", data: scores, backgroundColor: bgColors, borderRadius: 4, barPercentage: 0.7 }] },
                    options: {
                        ...base,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    afterLabel: function(ctx) { return 'Dept: ' + data.score_dist_chart.depts[ctx.dataIndex]; }
                                }
                            }
                        },
                        scales: {
                            x: { grid: { display: false }, ticks: { font: { size: 9 }, color: "#6c757d", maxRotation: 45 } },
                            y: { beginAtZero: true, max: 100, ticks: { font: { size: 10 }, color: "#6c757d" }, grid: { color: "rgba(0,0,0,0.04)" } }
                        }
                    }
                }));
            }
        }

        if (tab === "employee") {
            console.log("Rendering EMPLOYEE charts");
            console.log("employee_dept_chart:", data.employee_dept_chart);

            if (this.empDeptChartRef.el && data.employee_dept_chart && data.employee_dept_chart.data && data.employee_dept_chart.data.length > 0) {
                this.chartInstances.push(new Chart(this.empDeptChartRef.el, {
                    type: "doughnut",
                    data: {
                        labels: data.employee_dept_chart.labels,
                        datasets: [{
                            data: data.employee_dept_chart.data,
                            backgroundColor: ["#0d6efd", "#20c997", "#6f42c1", "#fd7e14", "#e83e8c", "#ffc107", "#198754", "#dc3545"],
                            borderWidth: 1,
                            borderColor: "#fff"
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "right", labels: { boxWidth: 10, font: { size: 10 } } } } }
                }));
            } else {
                console.warn("Cannot create department chart - missing data or canvas");
            }

            if (this.empEvalGroupChartRef.el && data.employee_eval_group_chart && data.employee_eval_group_chart.data && data.employee_eval_group_chart.data.length > 0) {
                this.chartInstances.push(new Chart(this.empEvalGroupChartRef.el, {
                    type: "bar",
                    data: {
                        labels: data.employee_eval_group_chart.labels,
                        datasets: [{
                            label: "Employees",
                            data: data.employee_eval_group_chart.data,
                            backgroundColor: "#6f42c1",
                            borderRadius: 4,
                            barPercentage: 0.65
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
                }));
            }

            if (this.empGenderChartRef.el && data.employee_gender_chart && data.employee_gender_chart.data) {
                this.chartInstances.push(new Chart(this.empGenderChartRef.el, {
                    type: "pie",
                    data: {
                        labels: data.employee_gender_chart.labels,
                        datasets: [{
                            data: data.employee_gender_chart.data,
                            backgroundColor: ["#0d6efd", "#e83e8c", "#6c757d"],
                            borderWidth: 1,
                            borderColor: "#fff"
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } } } }
                }));
            }

            if (this.deptGroupChartRef.el && data.dept_group_chart) {
                this.chartInstances.push(new Chart(this.deptGroupChartRef.el, {
                    type: "bar",
                    data: {
                        labels: data.dept_group_chart.departments,
                        datasets: data.dept_group_chart.datasets.map(function(ds, i) {
                            return {
                                label: ds.label,
                                data: ds.data,
                                backgroundColor: COLORS[i % COLORS.length],
                                borderRadius: 4,
                                barPercentage: 0.7,
                            };
                        })
                    },
                    options: { ...base, plugins: { legend: { position: "top", ...legendSm } }, scales: axisSm }
                }));
            }
        }
    }

    async _renderSupervisorCharts(data) {
    if (!data.supervisor || !data.supervisor.active_cycles) return;

    const Chart = window.Chart;
    if (!Chart) return;

    // For each active cycle, render department distribution chart
    for (const cycle of data.supervisor.active_cycles) {
        if (cycle.state === 'planning' && this.supervisorDeptChartRef.el && cycle.dept_distribution) {
            const labels = Object.keys(cycle.dept_distribution);
            const values = Object.values(cycle.dept_distribution);

            if (labels.length > 0) {
                this.chartInstances.push(new Chart(this.supervisorDeptChartRef.el, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Number of Plans',
                            data: values,
                            backgroundColor: '#0d6efd',
                            borderRadius: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top' } },
                        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                    }
                }));
            }
        }

        if (cycle.state === 'appraisal' && this.supervisorScoreChartRef.el && cycle.team_appraisals) {
            // Create score distribution chart
            const scores = cycle.team_appraisals.map(a => a.final_score || 0);
            const names = cycle.team_appraisals.map(a => a.name);

            const bgColors = scores.map(s =>
                s >= 90 ? '#198754' : s >= 75 ? '#0d6efd' : s >= 60 ? '#ffc107' : s >= 40 ? '#fd7e14' : '#dc3545'
            );

            this.chartInstances.push(new Chart(this.supervisorScoreChartRef.el, {
                type: 'bar',
                data: {
                    labels: names,
                    datasets: [{
                        label: 'Final Score',
                        data: scores,
                        backgroundColor: bgColors,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { font: { size: 9 }, maxRotation: 45 } },
                        y: { beginAtZero: true, max: 100 }
                    }
                }
            }));
        }
    }
}
async _renderReviewerCharts(data) {
    if (!data.reviewer || !data.reviewer.active_cycles) return;

    const Chart = window.Chart;
    if (!Chart) return;

    for (const cycle of data.reviewer.active_cycles) {
        if (cycle.state === 'planning' && this.reviewerDeptChartRef.el && cycle.dept_distribution) {
            const labels = Object.keys(cycle.dept_distribution);
            const values = Object.values(cycle.dept_distribution);

            if (labels.length > 0) {
                this.chartInstances.push(new Chart(this.reviewerDeptChartRef.el, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Plans Pending Review',
                            data: values,
                            backgroundColor: '#fd7e14',
                            borderRadius: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top' } },
                        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                    }
                }));
            }
        }

        if (cycle.state === 'appraisal' && this.reviewerScoreChartRef.el && cycle.all_appraisals) {
            const scores = cycle.all_appraisals.map(a => a.final_score || 0);
            const names = cycle.all_appraisals.map(a => a.name);

            const bgColors = scores.map(s =>
                s >= 90 ? '#198754' : s >= 75 ? '#0d6efd' : s >= 60 ? '#ffc107' : s >= 40 ? '#fd7e14' : '#dc3545'
            );

            this.chartInstances.push(new Chart(this.reviewerScoreChartRef.el, {
                type: 'bar',
                data: {
                    labels: names,
                    datasets: [{
                        label: 'Final Score',
                        data: scores,
                        backgroundColor: bgColors,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { font: { size: 9 }, maxRotation: 45 } },
                        y: { beginAtZero: true, max: 100 }
                    }
                }
            }));
        }
    }
}
// ============================================================
// SUPERVISOR CYCLE CHARTS
// ============================================================

async _renderSupervisorPlanningCharts(cycle) {
    await this._ensureChartJS();
    await this._waitForDOM(200);

    const Chart = window.Chart;
    if (!Chart) return;

    // Chart 1: Plans by Department for this cycle
    if (this.supervisorDeptChartRef.el && cycle.dept_distribution) {
        const labels = Object.keys(cycle.dept_distribution);
        const values = Object.values(cycle.dept_distribution);

        if (labels.length > 0) {
            this.chartInstances.push(new Chart(this.supervisorDeptChartRef.el, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Number of Plans',
                        data: values,
                        backgroundColor: '#0d6efd',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Plans: ${context.parsed.y}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { stepSize: 1 },
                            title: { display: true, text: 'Number of Plans' }
                        },
                        x: {
                            ticks: { font: { size: 10 }, maxRotation: 45 }
                        }
                    }
                }
            }));
        }
    }

    // Chart 2: Plan Status Breakdown
    if (this.cyclePlanStatusChartRef.el && cycle.team_plans) {
        const statusMap = {
            'draft': 0,
            'pending_supervisor': 0,
            'pending_secondary_supervisor': 0,
            'pending_reviewer': 0,
            'approved': 0
        };

        cycle.team_plans.forEach(plan => {
            if (statusMap.hasOwnProperty(plan.state_key)) {
                statusMap[plan.state_key]++;
            }
        });

        const statusLabels = ['Draft', 'Pending 1st', 'Pending 2nd', 'Pending Final', 'Approved'];
        const statusValues = [
            statusMap['draft'],
            statusMap['pending_supervisor'],
            statusMap['pending_secondary_supervisor'],
            statusMap['pending_reviewer'],
            statusMap['approved']
        ];
        const statusColors = ['#6c757d', '#0d6efd', '#ffc107', '#6f42c1', '#198754'];

        if (statusValues.some(v => v > 0)) {
            this.chartInstances.push(new Chart(this.cyclePlanStatusChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: statusLabels,
                    datasets: [{
                        data: statusValues,
                        backgroundColor: statusColors,
                        borderWidth: 1,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: {
                        legend: { position: 'right', labels: { font: { size: 10 } } },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const total = statusValues.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((context.parsed / total) * 100);
                                    return `${context.label}: ${context.parsed} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            }));
        }
    }
}

async _renderSupervisorAppraisalCharts(cycle) {
    await this._ensureChartJS();
    await this._waitForDOM(200);

    const Chart = window.Chart;
    if (!Chart) return;

    // Chart 1: Score Distribution by Employee
    if (this.supervisorScoreChartRef.el && cycle.team_appraisals && cycle.team_appraisals.length > 0) {
        const scores = cycle.team_appraisals.map(a => a.final_score || 0);
        const names = cycle.team_appraisals.map(a => a.name);

        const bgColors = scores.map(s =>
            s >= 90 ? '#198754' : s >= 75 ? '#0d6efd' : s >= 60 ? '#ffc107' : s >= 40 ? '#fd7e14' : '#dc3545'
        );

        this.chartInstances.push(new Chart(this.supervisorScoreChartRef.el, {
            type: 'bar',
            data: {
                labels: names,
                datasets: [{
                    label: 'Final Score',
                    data: scores,
                    backgroundColor: bgColors,
                    borderRadius: 4,
                    barPercentage: 0.7
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Score: ${context.parsed.y}`;
                            },
                            afterLabel: function(context) {
                                const rating = cycle.team_appraisals[context.dataIndex]?.rating || '';
                                return rating ? `Rating: ${rating}` : '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { font: { size: 9 }, maxRotation: 45, autoSkip: true },
                        title: { display: true, text: 'Employee', font: { size: 10 } }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Score', font: { size: 10 } },
                        ticks: { stepSize: 20 }
                    }
                }
            }
        }));
    }

    // Chart 2: Appraisal Status Breakdown
    if (this.appraisalStatusChartRef.el && cycle.team_appraisals) {
        const statusMap = {
            'appraisal_draft': 0,
            'appraisal_pending_supervisor': 0,
            'appraisal_pending_secondary_supervisor': 0,
            'appraisal_pending_reviewer': 0,
            'appraisal_approved': 0
        };

        cycle.team_appraisals.forEach(appraisal => {
            if (statusMap.hasOwnProperty(appraisal.state_key)) {
                statusMap[appraisal.state_key]++;
            }
        });

        const statusLabels = ['Draft', '1st Rating', '2nd Rating', 'Final Rating', 'Completed'];
        const statusValues = [
            statusMap['appraisal_draft'],
            statusMap['appraisal_pending_supervisor'],
            statusMap['appraisal_pending_secondary_supervisor'],
            statusMap['appraisal_pending_reviewer'],
            statusMap['appraisal_approved']
        ];
        const statusColors = ['#6c757d', '#0d6efd', '#ffc107', '#6f42c1', '#198754'];

        if (statusValues.some(v => v > 0)) {
            this.chartInstances.push(new Chart(this.appraisalStatusChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: statusLabels,
                    datasets: [{
                        data: statusValues,
                        backgroundColor: statusColors,
                        borderWidth: 1,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: {
                        legend: { position: 'right', labels: { font: { size: 10 } } },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const total = statusValues.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((context.parsed / total) * 100);
                                    return `${context.label}: ${context.parsed} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            }));
        }
    }
}

// ============================================================
// REVIEWER CYCLE CHARTS
// ============================================================

async _renderReviewerPlanningCharts(cycle) {
    await this._ensureChartJS();
    await this._waitForDOM(200);

    const Chart = window.Chart;
    if (!Chart) return;

    // Chart 1: Plans by Department pending review
    if (this.reviewerDeptChartRef.el && cycle.dept_distribution) {
        const labels = Object.keys(cycle.dept_distribution);
        const values = Object.values(cycle.dept_distribution);

        if (labels.length > 0) {
            this.chartInstances.push(new Chart(this.reviewerDeptChartRef.el, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Plans Pending Review',
                        data: values,
                        backgroundColor: '#fd7e14',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Pending Plans: ${context.parsed.y}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { stepSize: 1 },
                            title: { display: true, text: 'Number of Plans' }
                        },
                        x: {
                            ticks: { font: { size: 10 }, maxRotation: 45 }
                        }
                    }
                }
            }));
        }
    }

    // Chart 2: Plan Status Breakdown (Focus on Pending Reviewer)
    if (this.cyclePlanStatusChartRef.el && cycle.all_plans) {
        const statusMap = {
            'draft': 0,
            'pending_supervisor': 0,
            'pending_secondary_supervisor': 0,
            'pending_reviewer': 0,
            'approved': 0
        };

        cycle.all_plans.forEach(plan => {
            if (statusMap.hasOwnProperty(plan.state_key)) {
                statusMap[plan.state_key]++;
            }
        });

        const statusLabels = ['Draft', '1st Approval', '2nd Approval', 'Final Review', 'Approved'];
        const statusValues = [
            statusMap['draft'],
            statusMap['pending_supervisor'],
            statusMap['pending_secondary_supervisor'],
            statusMap['pending_reviewer'],
            statusMap['approved']
        ];
        const statusColors = ['#6c757d', '#0d6efd', '#ffc107', '#fd7e14', '#198754'];

        if (statusValues.some(v => v > 0)) {
            this.chartInstances.push(new Chart(this.cyclePlanStatusChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: statusLabels,
                    datasets: [{
                        data: statusValues,
                        backgroundColor: statusColors,
                        borderWidth: 1,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: {
                        legend: { position: 'right', labels: { font: { size: 10 } } },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const total = statusValues.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((context.parsed / total) * 100);
                                    return `${context.label}: ${context.parsed} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            }));
        }
    }
}

async _renderReviewerAppraisalCharts(cycle) {
    await this._ensureChartJS();
    await this._waitForDOM(200);

    const Chart = window.Chart;
    if (!Chart) return;

    // Chart 1: Score Distribution by Employee
    if (this.reviewerScoreChartRef.el && cycle.all_appraisals && cycle.all_appraisals.length > 0) {
        const scores = cycle.all_appraisals.map(a => a.final_score || 0);
        const names = cycle.all_appraisals.map(a => a.name);

        const bgColors = scores.map(s =>
            s >= 90 ? '#198754' : s >= 75 ? '#0d6efd' : s >= 60 ? '#ffc107' : s >= 40 ? '#fd7e14' : '#dc3545'
        );

        this.chartInstances.push(new Chart(this.reviewerScoreChartRef.el, {
            type: 'bar',
            data: {
                labels: names,
                datasets: [{
                    label: 'Final Score',
                    data: scores,
                    backgroundColor: bgColors,
                    borderRadius: 4,
                    barPercentage: 0.7
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Score: ${context.parsed.y}`;
                            },
                            afterLabel: function(context) {
                                const rating = cycle.all_appraisals[context.dataIndex]?.rating || '';
                                return rating ? `Rating: ${rating}` : '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { font: { size: 9 }, maxRotation: 45, autoSkip: true },
                        title: { display: true, text: 'Employee', font: { size: 10 } }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Score', font: { size: 10 } },
                        ticks: { stepSize: 20 }
                    }
                }
            }
        }));
    }

    // Chart 2: Appraisal Status Breakdown (Focus on Pending Reviewer)
    if (this.appraisalStatusChartRef.el && cycle.all_appraisals) {
        const statusMap = {
            'appraisal_draft': 0,
            'appraisal_pending_supervisor': 0,
            'appraisal_pending_secondary_supervisor': 0,
            'appraisal_pending_reviewer': 0,
            'appraisal_approved': 0
        };

        cycle.all_appraisals.forEach(appraisal => {
            if (statusMap.hasOwnProperty(appraisal.state_key)) {
                statusMap[appraisal.state_key]++;
            }
        });

        const statusLabels = ['Draft', '1st Rating', '2nd Rating', 'Final Review', 'Approved'];
        const statusValues = [
            statusMap['appraisal_draft'],
            statusMap['appraisal_pending_supervisor'],
            statusMap['appraisal_pending_secondary_supervisor'],
            statusMap['appraisal_pending_reviewer'],
            statusMap['appraisal_approved']
        ];
        const statusColors = ['#6c757d', '#0d6efd', '#ffc107', '#fd7e14', '#198754'];

        if (statusValues.some(v => v > 0)) {
            this.chartInstances.push(new Chart(this.appraisalStatusChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: statusLabels,
                    datasets: [{
                        data: statusValues,
                        backgroundColor: statusColors,
                        borderWidth: 1,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: {
                        legend: { position: 'right', labels: { font: { size: 10 } } },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const total = statusValues.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((context.parsed / total) * 100);
                                    return `${context.label}: ${context.parsed} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            }));
        }
    }
}

    _renderEmployeeAppraisalChart(chartData) {
        const Chart = window.Chart;
        if (!Chart || !this.empAppraisalChartRef.el) return;
        const COLORS = ["#6c757d", "#0d6efd", "#ffc107", "#6f42c1", "#198754"];
        this.chartInstances.push(new Chart(this.empAppraisalChartRef.el, {
            type: "doughnut",
            data: { labels: chartData.labels, datasets: [{ data: chartData.data, backgroundColor: COLORS, borderWidth: 1, borderColor: "#fff" }] },
            options: {
                responsive: true, maintainAspectRatio: false, layout: { padding: 4 }, cutout: "60%",
                plugins: { legend: { position: "right", labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 }, padding: 6 } } }
            }
        }));
    }

    _renderCyclePlanningCharts = async () => {
        await this._ensureChartJS();
        await this._waitForDOM(200);

                const Chart = window.Chart;
        if (!Chart) return;

        // ── Destroy existing charts first ──
    [
        this.cyclePlansDeptChartRef,
        this.cyclePlansGroupChartRef,
        this.cyclePlanStatusChartRef,
    ].forEach(ref => {
        if (ref && ref.el) {
            const existing = Chart.getChart(ref.el);
            if (existing) existing.destroy();
        }
    });



        const planningData = this.state.cycle_planning_data;

        // Chart 1: Plans by Department
        const deptMap = {};
        planningData.forEach(function(plan) {
            const dept = plan.department || 'No Department';
            deptMap[dept] = (deptMap[dept] || 0) + 1;
        });

        if (this.cyclePlansDeptChartRef.el && Object.keys(deptMap).length > 0) {
            this.chartInstances.push(new Chart(this.cyclePlansDeptChartRef.el, {
                type: 'bar',
                data: {
                    labels: Object.keys(deptMap),
                    datasets: [{
                        label: 'Number of Plans',
                        data: Object.values(deptMap),
                        backgroundColor: '#0d6efd',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'top' } },
                    scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                }
            }));
        }

        // Chart 2: Plans by Evaluation Group
        const groupMap = {};
        planningData.forEach(function(plan) {
            const group = plan.evaluation_group || 'No Group';
            groupMap[group] = (groupMap[group] || 0) + 1;
        });

        if (this.cyclePlansGroupChartRef.el && Object.keys(groupMap).length > 0) {
            this.chartInstances.push(new Chart(this.cyclePlansGroupChartRef.el, {
                type: 'bar',
                data: {
                    labels: Object.keys(groupMap),
                    datasets: [{
                        label: 'Number of Plans',
                        data: Object.values(groupMap),
                        backgroundColor: '#6f42c1',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'top' } },
                    scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                }
            }));
        }

        // Chart 3: Plan Status Breakdown
        const statusMap = {
            'draft': 0,
            'pending_supervisor': 0,
            'pending_secondary_supervisor': 0,
            'pending_reviewer': 0,
            'approved': 0
        };
        planningData.forEach(function(plan) {
            if (statusMap.hasOwnProperty(plan.state_key)) {
                statusMap[plan.state_key]++;
            }
        });

        const statusLabels = ['Draft', 'Pending 1st', 'Pending 2nd', 'Pending Final', 'Approved'];
        const statusValues = [
            statusMap['draft'],
            statusMap['pending_supervisor'],
            statusMap['pending_secondary_supervisor'],
            statusMap['pending_reviewer'],
            statusMap['approved']
        ];
        const statusColors = ['#6c757d', '#0d6efd', '#ffc107', '#6f42c1', '#198754'];

        if (this.cyclePlanStatusChartRef.el && statusValues.some(function(v) { return v > 0; })) {
            this.chartInstances.push(new Chart(this.cyclePlanStatusChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: statusLabels,
                    datasets: [{
                        data: statusValues,
                        backgroundColor: statusColors,
                        borderWidth: 1,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: { legend: { position: 'right', labels: { font: { size: 10 } } } }
                }
            }));
        }
    }



    // ============================================================
    // COMBINED DASHBOARD METHODS
    // ============================================================

    onClickMyPlans = () => {
        this.navigateTo("pms.appraisal", [["employee_id", "=", this.state.employee_id]], "My Plan");
    }

    onClickTeamPlans = () => {
        this.navigateTo("pms.appraisal", [["supervisor_id", "=", this.state.employee_id], ["employee_id", "!=", this.state.employee_id]], "Team Plans");
    }

    onClickPendingMyReview = () => {
        this.navigateTo("pms.appraisal", [["supervisor_id", "=", this.state.employee_id], ["employee_id", "!=", this.state.employee_id], ["state", "in", ["pending_supervisor"]]], "Pending Planning Approval");
    }

    onClickPendingAppraisalAsSuper = () => {
        this.navigateTo("pms.appraisal", [["supervisor_id", "=", this.state.employee_id], ["employee_id", "!=", this.state.employee_id], ["state", "in", ["appraisal_pending_supervisor"]]], "Pending Appraisal Rating");
    }

    onClickReviewerPlans = () => {
        this.navigateTo("pms.appraisal", [["reviewer_id", "=", this.state.employee_id], ["employee_id", "!=", this.state.employee_id]], "Plans For My Review");
    }

    onClickPendingFinalReview = () => {
        this.navigateTo("pms.appraisal", [["reviewer_id", "=", this.state.employee_id], ["employee_id", "!=", this.state.employee_id], ["state", "in", ["pending_reviewer"]]], "Pending Final Planning Approval");
    }

    onClickPendingAppraisalAsReviewer = () => {
        this.navigateTo("pms.appraisal", [["reviewer_id", "=", this.state.employee_id], ["employee_id", "!=", this.state.employee_id], ["state", "in", ["appraisal_pending_reviewer"]]], "Pending Final Appraisal");
    }

    // ============================================================
    // HR MANAGER STAT CARD METHODS
    // ============================================================

    onClickTotalEmployees = () => {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            views: [[false, 'list']],
            domain: [['active', '=', true]],
            target: 'current',
            name: 'All Active Employees',
        });
    }

    onClickTotalPlans = () => {
        const employeeIds = this.state.employees_with_plan || [];
        if (employeeIds.length === 0) {
            this.env.services.notification.add("No employees with plans found.", { type: 'warning' });
            return;
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            views: [[false, 'list']],
            domain: [['id', 'in', employeeIds]],
            target: 'current',
            name: 'Employees With Plan',
        });
    }

    onClickWithoutPlan = async () => {
        const withoutPlanCount = (this.state.participation && this.state.participation.not_participated) ? this.state.participation.not_participated : 0;
        if (withoutPlanCount === 0) {
            this.env.services.notification.add("All employees have plans!", { type: 'success' });
            return;
        }
        const allEmployeeIds = await this._getAllEmployeeIds();
        const withPlanIds = this.state.employees_with_plan || [];
        const withoutPlanIds = allEmployeeIds.filter(function(id) { return !withPlanIds.includes(id); });

        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            views: [[false, 'list']],
            domain: [['id', 'in', withoutPlanIds]],
            target: 'current',
            name: 'Employees Without Plan',
        });
    }

    onClickActiveCycles = () => {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'pms.cycle',
            views: [[false, 'list']],
            domain: [['state', 'in', ['planning', 'appraisal']]],
            target: 'current',
            name: 'Active Cycles',
        });
    }

    onClickPendingReviews = () => {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'pms.appraisal',
            views: [[false, 'list']],
            domain: [['state', 'in', [
                'pending_supervisor',
                'pending_secondary_supervisor',
                'pending_reviewer',
                'appraisal_pending_supervisor',
                'appraisal_pending_secondary_supervisor',
                'appraisal_pending_reviewer'
            ]]],
            target: 'current',
            name: 'Pending Approvals',
        });
    }

    onClickCompleted = () => {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'pms.appraisal',
            views: [[false, 'list']],
            domain: [['state', '=', 'appraisal_approved']],
            target: 'current',
            name: 'Completed Appraisals',
        });
    }

    onClickInAppraisal = () => {
        this.navigateTo("pms.appraisal", [["state", "in", ["appraisal_draft", "appraisal_pending_supervisor", "appraisal_pending_secondary_supervisor", "appraisal_pending_reviewer"]]], "In Appraisal");
    }

    onClickActiveEmployees = () => {
        this.navigateTo("hr.employee", [["active", "=", true]], "Active Employees");
    }

    // ============================================================
    // HELPER METHODS
    // ============================================================

    _getAllEmployeeIds = async () => {
        try {
            const result = await rpc("/hr_pms_dashboard/get_all_employee_ids", {});
            return result.employee_ids || [];
        } catch (error) {
            console.error("Error getting employee IDs:", error);
            return [];
        }
    }

    navigateTo = (model, domain, name) => {
        domain = domain || [];
        name = name || "Records";
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            views: [[false, 'list']],
            domain: domain,
            target: 'current',
            name: name,
        });
    }

    navigateToCycle = (cycleId) => {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'pms.cycle',
            res_id: cycleId,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

registry.category("actions").add("pms_dashboard", PMSDashboard);