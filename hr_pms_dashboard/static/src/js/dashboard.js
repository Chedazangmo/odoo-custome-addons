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

    setup() {
        this.action = this.env.services.action;
        const actionParams = this.props.action?.params || {};
        const requestedRole = actionParams.role || 'overview';

        this.state = useState({
            // Core
            loading: true,
            error: null,
            role: null,
            employee_id: 0,
            employee_name: "",
            requestedRole: requestedRole,



            // HR Manager data
            stats: {},
            active_cycles_list: [],
            completed_cycles_list: [],
            top_performers: [],
            bottom_performers: [],
            overview_stats: {},

            // Employee data
            employee: null,
            filtered_past_cycles: [],
            completed_cycle_search: '',

            // Cycle detail
            selected_cycle: null,
            selected_cycle_id: null,
            show_cycle_detail: false,
            is_monitoring_cycle: false,
            cycle_planning_data: [],
            cycle_appraisal_data: [],
            cycle_active_tab: 'planning',
            filtered_cycle_planning_data: [],
            cycle_planning_search: '',
            cycle_appraisal_search: '',
            filtered_cycle_appraisal_data: [],
            appraisal_started: 0,
            appraisal_approved: 0,
            appraisal_table_view: 'total',

            // Performance filters
            performance_employees_list: [],
            filtered_performance_employees: [],
            performance_filter: 'all',

            // Modals
            selected_plan: null,
            show_full_plan_details: false,
            selected_full_plan: null,
            show_full_appraisal_details: false,
            selected_full_appraisal: null,
            show_all_appraisals_modal: false,
            all_appraisals_data: [],
            all_appraisals_summary: null,
            show_completed_cycle_modal: false,
            selected_completed_cycle: null,
            completed_cycle_employees: [],

            // Filters
            filtered_completed_cycles_list: [],
            completed_cycles_search: '',

            // Supervisor/Reviewer
            supervisor: null,
            reviewer: null,

            // Employees lists (HR)
            employees_no_plan: [],
            employees_no_appraisal: [],
            employees_with_plan: [],
            employees_no_plan_count: 0,
            employees_no_appraisal_count: 0,
        });

        this.cyclePlansDeptChartRef = useRef("cyclePlansDeptChart");
        this.cyclePlansGroupChartRef = useRef("cyclePlansGroupChart");
        this.cyclePlanStatusChartRef = useRef("cyclePlanStatusChart");

        this.chartInstances = [];
        this._dataCache = null;
        this._refreshInterval = null;

        onMounted(async () => {
            await this._loadData();
            this._refreshInterval = setInterval(async () => {
                try {
                    await this._loadData();
                    if (this.state.show_cycle_detail && this.state.selected_cycle_id) {
                        await this.loadCycleData(this.state.selected_cycle_id);
                        this.state.selected_cycle = this._safeCycle(this.state.selected_cycle);
                    }
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

    // ============================================================
    // CYCLE DETAIL
    // ============================================================

    openCycleDetail = async (cycle) => {
        this.state.cycle_planning_search = '';
        this.state.cycle_appraisal_search = '';
        this.filterCyclePlanningData();

        if (cycle.state === 'completed') {
            await this.loadCompletedCycleDetails(cycle);
            return;
        }

        this.state.show_cycle_detail = true;
        this.state.selected_cycle_id = cycle.id;
        this.state.cycle_active_tab = cycle.state === 'appraisal' ? 'appraisal' : 'planning';
        this.state.selected_cycle = this._safeCycle(cycle);

        await this.loadCycleData(cycle.id);
        this.state.selected_cycle = this._safeCycle(this.state.selected_cycle);

        if (this.state.cycle_active_tab === 'planning') {
            await this._renderPlanningChartsByRole();
        }
    }

    _safeCycle(cycle) {
        return {
            ...cycle,
            pending_plan_list: Array.isArray(cycle.pending_plan_list) ? cycle.pending_plan_list : [],
            team_plans: Array.isArray(cycle.team_plans) ? cycle.team_plans : [],
            employees_without_plan: Array.isArray(cycle.employees_without_plan) ? cycle.employees_without_plan : [],
            pending_approval_plans: Array.isArray(cycle.pending_approval_plans) ? cycle.pending_approval_plans : [],
            all_plans: Array.isArray(cycle.all_plans) ? cycle.all_plans : [],
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
            top_performers: Array.isArray(cycle.top_performers) ? cycle.top_performers : [],
            bottom_performers: Array.isArray(cycle.bottom_performers) ? cycle.bottom_performers : [],
            rating_distribution: Array.isArray(cycle.rating_distribution) ? cycle.rating_distribution : [],
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
        this.state.cycle_planning_data = [];
        this.state.cycle_appraisal_data = [];
    }

    setCycleTab = async (tab) => {
        this.state.cycle_active_tab = tab;
        if (tab === 'planning' && this.state.role === 'hr_manager') {
            await this._renderCyclePlanningCharts();
        }
    }

    // ============================================================
    // LOAD CYCLE DATA
    // ============================================================

    loadCycleData = async (cycleId) => {
        try {
            const data = await rpc("/hr_pms_dashboard/cycle_data", { cycle_id: cycleId });

            await this.loadPerformanceData();

            this.state.cycle_planning_data = data.planning_data || [];
            this.state.cycle_appraisal_data = data.appraisal_data || [];
            this.state.filtered_cycle_appraisal_data = [...(data.appraisal_data || [])];
            this.state.filtered_cycle_planning_data = [...(data.planning_data || [])];

            if (this.state.selected_cycle) {
            if (data.cycle_info) {
                this.state.selected_cycle = {
                    ...this.state.selected_cycle,
                    // Planning dates
                    planning_start_date: data.cycle_info.planning_start_date || this.state.selected_cycle.start_date || '-',
                    planning_end_date: data.cycle_info.planning_end_date || '-',
                    planning_duration: data.cycle_info.planning_duration || '-',
                    planning_days_left: data.cycle_info.planning_days_left,
                    // Appraisal dates
                    appraisal_start_date: data.cycle_info.appraisal_start_date || '-',
                    appraisal_end_date: data.cycle_info.appraisal_end_date || '-',
                    appraisal_duration_days: data.cycle_info.appraisal_duration_days,
                    appraisal_days_left: data.cycle_info.appraisal_days_left,
                    // Keep existing cycle data
                    start_date: this.state.selected_cycle.start_date,
                    end_date: this.state.selected_cycle.end_date,
                    state: this.state.selected_cycle.state,
                    name: this.state.selected_cycle.name,
                };
                console.log('Updated selected_cycle with dates:', this.state.selected_cycle);
            }

                const currentRole = this.state.role;
                const currentEmployeeId = this.state.employee_id;

                const teamPlans = (data.planning_data || []).map(plan => ({
                    id: plan.plan_id || plan.id,
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
                    user_role: plan.user_role,
                }));

                const teamAppraisals = (data.appraisal_data || []).map(appraisal => ({
                    id: appraisal.plan_id || appraisal.id,
                    appraisal_id: appraisal.plan_id || appraisal.id,
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
                     supervisor_name: appraisal.supervisor_name || '',
    secondary_name: appraisal.secondary_name || '',
    reviewer_name: appraisal.reviewer_name || '',
                }));

                const appraisalStartedCount = teamAppraisals.filter(a => a.state_key !== 'appraisal_draft').length;
                const appraisalApprovedCount = teamAppraisals.filter(a => a.state_key === 'appraisal_approved').length;

                this.state.appraisal_started = appraisalStartedCount;
                this.state.appraisal_approved = appraisalApprovedCount;

                // Pending plans by role
                let pendingPlanList = [];
                if (data.pending_plan_list && data.pending_plan_list.length > 0) {
                    let filteredList = data.pending_plan_list;
                    if (currentRole === 'supervisor') {
                        filteredList = data.pending_plan_list.filter(p =>
                            p.state_key === 'pending_supervisor' || p.state_key === 'pending_secondary_supervisor'
                        );
                    } else if (currentRole === 'reviewer') {
                        filteredList = data.pending_plan_list.filter(p => p.state_key === 'pending_reviewer');
                    }
                    pendingPlanList = filteredList;
                } else {
                    if (currentRole === 'supervisor') {
                        pendingPlanList = teamPlans.filter(p =>
                            (p.state_key === 'pending_supervisor' && p.user_role === 'primary') ||
                            (p.state_key === 'pending_secondary_supervisor' && p.user_role === 'secondary')
                        ).map(p => ({ ...p, id: p.id, plan_id: p.id }));
                    } else if (currentRole === 'reviewer') {
                        pendingPlanList = teamPlans.filter(p =>
                            p.state_key === 'pending_reviewer' && p.reviewer_id === currentEmployeeId
                        ).map(p => ({ ...p, id: p.id, plan_id: p.id }));
                    }
                }

                const approvedPlans = teamPlans.filter(p => p.state_key === 'approved').length;
                const totalTeamMembers = teamPlans.length;

                // Pending appraisals by role
                let pendingAppraisalList = [];
                if (currentRole === 'supervisor') {
                    pendingAppraisalList = teamAppraisals.filter(a =>
                        (a.state_key === 'appraisal_pending_supervisor' && a.user_role === 'primary') ||
                        (a.state_key === 'appraisal_pending_secondary_supervisor' && a.user_role === 'secondary')
                    ).map(a => ({
                        id: a.id, appraisal_id: a.id,
                        employee_id: a.employee_id, name: a.name,
                        department: a.department, self_score: a.self_score,
                        supervisor_score: a.supervisor_score, state_key: a.state_key,
                    }));
                } else if (currentRole === 'reviewer') {
                    pendingAppraisalList = teamAppraisals.filter(a =>
                        a.state_key === 'appraisal_pending_reviewer'
                    ).map(a => ({
                        id: a.id, appraisal_id: a.id,
                        employee_id: a.employee_id, name: a.name,
                        department: a.department, self_score: a.self_score,
                        supervisor_score: a.supervisor_score, state_key: a.state_key,
                    }));
                }

                const completedAppraisals = teamAppraisals.filter(a => a.state_key === 'appraisal_approved').length;
                const employeesWithoutPlan = teamPlans.filter(p => p.state_key === 'draft').map(p => ({
                    id: p.employee_id, name: p.name, department: p.department,
                }));
                const employeesWithoutAppraisal = teamAppraisals.filter(a => a.state_key === 'appraisal_draft').map(a => ({
                    id: a.employee_id, name: a.name, department: a.department,
                }));

                this.state.selected_cycle = {
                    ...this.state.selected_cycle,
                    total_team_members: totalTeamMembers,
                    pending_plan_count: pendingPlanList.length,
                    approved_plan_count: approvedPlans,
                    employees_without_plan: employeesWithoutPlan,
                    employees_without_plan_count: employeesWithoutPlan.length,
                    pending_plan_list: pendingPlanList,
                    all_plans: teamPlans,
                    pending_appraisal_count: pendingAppraisalList.length,
                    completed_appraisal_count: completedAppraisals,
                    employees_without_appraisal: employeesWithoutAppraisal,
                    employees_without_appraisal_count: employeesWithoutAppraisal.length,
                    pending_appraisal_list: pendingAppraisalList,
                    all_appraisals: teamAppraisals,
                    appraisal_started: appraisalStartedCount,
                    appraisal_approved: appraisalApprovedCount,
                    team_plans: (currentRole === 'supervisor' || currentRole === 'reviewer')
                        ? teamPlans.filter(p =>
                            p.supervisor_id === currentEmployeeId ||
                            p.secondary_id === currentEmployeeId ||
                            p.reviewer_id === currentEmployeeId)
                        : teamPlans,
                    team_appraisals: (currentRole === 'supervisor' || currentRole === 'reviewer')
                        ? teamAppraisals.filter(a =>
                            a.supervisor_id === currentEmployeeId ||
                            a.secondary_id === currentEmployeeId ||
                            a.reviewer_id === currentEmployeeId)
                        : teamAppraisals,
                    pending_appraisal_supervisor_list: currentRole === 'supervisor'
                        ? pendingAppraisalList.filter(a => a.state_key === 'appraisal_pending_supervisor')
                        : [],
                    pending_appraisal_secondary_list: currentRole === 'supervisor'
                        ? pendingAppraisalList.filter(a => a.state_key === 'appraisal_pending_secondary_supervisor')
                        : [],
                };
            }
        } catch (error) {
            console.error("Error loading cycle data:", error);
            this.state.cycle_planning_data = [];
            this.state.cycle_appraisal_data = [];
            this.state.filtered_cycle_planning_data = [];
            this.state.filtered_cycle_appraisal_data = [];
        }
    }

    // ============================================================
    // PERFORMANCE DATA
    // ============================================================

    loadPerformanceData = async () => {
        try {
            const cycle = this.state.selected_cycle;
            if (!cycle || !cycle.id) return;
            const result = await rpc("/hr_pms_dashboard/get_cycle_performance_data", { cycle_id: cycle.id });
            if (result && result.employees && result.employees.length > 0) {
                this.state.performance_employees_list = result.employees;
                this.state.filtered_performance_employees = [...result.employees];
                this.state.performance_filter = 'all';
            } else {
                this.state.performance_employees_list = [];
                this.state.filtered_performance_employees = [];
            }
        } catch (error) {
            console.error("Error loading performance data:", error);
            this.state.performance_employees_list = [];
            this.state.filtered_performance_employees = [];
        }
    }

    setPerformanceFilter = (filterType) => {
        this.state.performance_filter = filterType;
        this.filterPerformanceEmployees();
    }

    filterPerformanceEmployees = () => {
        const employees = this.state.performance_employees_list || [];
        switch (this.state.performance_filter) {
            case 'high':
                this.state.filtered_performance_employees = employees.filter(emp => (emp.total_score || emp.score || 0) >= 85);
                break;
            case 'low':
                this.state.filtered_performance_employees = employees.filter(emp => (emp.total_score || emp.score || 0) < 70);
                break;
            default:
                this.state.filtered_performance_employees = [...employees];
        }
    }

    // ============================================================
    // COMPLETED CYCLE (HR MANAGER)
    // ============================================================

    loadCompletedCycleDetails = async (cycle) => {
        this.state.selected_completed_cycle = {
            ...cycle,
            total_employees: cycle.total_employees || 0,
            avg_score: cycle.avg_score || 0,
        };
        this.state.completed_cycle_employees = [];

        try {
            const response = await fetch('/hr_pms_dashboard/get_completed_cycle_appraisals', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Odoo-CSRF-Token': odoo.csrf_token,
                },
                body: JSON.stringify({ cycle_id: cycle.id }),
            });
            const data = await response.json();
            const result = data.result;

            if (result && result.appraisals) {
                this.state.completed_cycle_employees = result.appraisals;
                this.state.performance_employees_list = result.appraisals.map(emp => ({
                    employee_id: emp.employee_id,
                    name: emp.name,
                    department: emp.department,
                    evaluation_group: emp.evaluation_group,
                    total_score: emp.final_score || emp.total_score || 0,
                    rating: emp.rating,
                    rating_class: emp.rating_class,
                }));
                this.state.filtered_performance_employees = [...this.state.performance_employees_list];
                this.state.performance_filter = 'all';
                if (result.summary) {
                    this.state.selected_completed_cycle.total_employees = result.summary.total_employees;
                    this.state.selected_completed_cycle.avg_score = result.summary.avg_score;
                }
            } else {
                this.state.completed_cycle_employees = [];
                this.state.performance_employees_list = [];
                this.state.filtered_performance_employees = [];
            }
        } catch (error) {
            console.error('Error loading completed cycle details:', error);
            this.state.completed_cycle_employees = [];
            this.state.performance_employees_list = [];
            this.state.filtered_performance_employees = [];
        }
    }

    openCompletedCycleDetailModal = async (cycleId) => {
        const cycle = this.state.filtered_completed_cycles_list.find(c => c.id === cycleId)
            || this.state.completed_cycles_list.find(c => c.id === cycleId);
        if (!cycle) return;

        this.state.selected_completed_cycle = cycle;
        this.state.completed_cycle_employees = [];
        this.state.show_completed_cycle_modal = true;

        try {
            const result = await rpc("/hr_pms_dashboard/get_completed_cycle_appraisals", { cycle_id: cycle.id });
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

    clearCompletedCyclesSearch = () => {
        this.state.completed_cycles_search = '';
        this.filterCompletedCyclesList();
    }

    exportCompletedCycleData = () => {
        if (!this.state.completed_cycle_employees || this.state.completed_cycle_employees.length === 0) {
            this.env.services.notification.add("No data to export", { type: "warning" });
            return;
        }
        const cycle = this.state.selected_completed_cycle;
        const employees = this.state.completed_cycle_employees;
        const headers = ['Employee', 'Department', 'Evaluation Group', 'Self Score', 'Supervisor Score',
            'Secondary Score', 'Reviewer Score', 'Final Score', 'Rating', 'Bonus Eligibility %', 'Basic Pay', 'Bonus Amount'];
        const rows = employees.map(emp => [
            emp.name || '', emp.department || '-', emp.evaluation_group || '-',
            emp.self_score || 0, emp.supervisor_score || 0, emp.secondary_score || '-',
            emp.reviewer_score || 0, emp.final_score || 0, emp.rating || '-',
            emp.eligibility_pct || 0, emp.basic_pay || 0, emp.bonus_amount || 0,
        ]);
        const csvLines = [
            `Cycle: ${cycle?.name || ''}`,
            `Period: ${cycle?.start_date || ''} to ${cycle?.end_date || ''}`,
            `Total Employees: ${employees.length}`,
            '',
            headers.join(','),
        ];
        rows.forEach(row => {
            csvLines.push(row.map(cell => {
                if (typeof cell === 'string' && (cell.includes(',') || cell.includes('"'))) {
                    return `"${cell.replace(/"/g, '""')}"`;
                }
                return cell;
            }).join(','));
        });
        this._downloadCSV(csvLines.join('\n'), `${cycle?.name || 'completed_cycle'}_appraisals.csv`);
        this.env.services.notification.add(`Exported ${employees.length} records successfully!`, { type: "success" });
    }



    // ============================================================
    // COMPLETED CYCLE DETAIL (EMPLOYEE VIEW)
    // ============================================================

    onOpenCompletedCycleDetail = async (cycle) => {
        this.state.selected_completed_cycle = null;
        try {
            const result = await rpc("/hr_pms_dashboard/get_employee_completed_cycle_detail", {
                cycle_id: cycle.id,
                employee_id: this.state.employee_id,
            });
            this.state.selected_completed_cycle = {
                id: cycle.id,
                cycle_name: cycle.cycle_name || '-',
                completed_date: cycle.completed_date || '-',
                start_date: cycle.start_date || '-',
                end_date: cycle.end_date || '-',
                final_score: cycle.final_score || 0,
                rating: cycle.rating || '—',
                rating_class: cycle.rating_class || 'bg-secondary',
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
                final_score: cycle.final_score || 0,
                rating: cycle.rating || '—',
                rating_class: cycle.rating_class || 'bg-secondary',
                kpi_lines: [],
                competency_lines: [],
            };
        }
    }

    onCloseCompletedCycleModal = () => {
        this.state.selected_completed_cycle = null;
    }

    // ============================================================
    // VIEW ALL PLANS - HR MANAGER
    // ============================================================

    onViewAllPlans = async () => {
        this.state.all_plans_loading = true;
        try {
            const cycle = this.state.selected_cycle;
            const plans = this.state.cycle_planning_data || [];
            const enriched = await Promise.all(plans.map(p => this._enrichPlanWithKRAs(p)));
            this._generateAllPlansPDF(enriched, cycle);
        } catch (error) {
            console.error("Error generating plans:", error);
            this.env.services.notification.add("Error generating plans", { type: "danger" });
        } finally {
            this.state.all_plans_loading = false;
        }
    }

    _generateAllPlansPDF = (plans, cycle) => {
        const allHTML = plans.map((plan, i) => `
            <div style="page-break-after:${i < plans.length - 1 ? 'always' : 'avoid'};">
                ${this._buildPlanHTML(plan, cycle)}
            </div>`).join('');
        const win = window.open('', '_blank');
        win.document.write(`<!DOCTYPE html><html><head>
            <title>${cycle.name || 'Plans'} – All Employee Plans</title>
            <style>
                * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
                @media print { body { padding: 0; } @page { margin: 15mm; } }
                table { width: 100%; border-collapse: collapse; }
                th, td { border: 1px solid #c5d5ea; padding: 8px 12px; text-align: left; }
                th { background: #2563a8; color: #fff; }
            </style>
        </head><body>
            <div style="text-align:center;margin-bottom:20px;display:flex;gap:10px;justify-content:center;">
                <button onclick="window.print();" style="padding:10px 20px;background:#1a3557;color:#fff;border:none;border-radius:5px;cursor:pointer;">📄 Save as PDF / Print</button>
                <button onclick="window.close();" style="padding:10px 20px;background:#6c757d;color:#fff;border:none;border-radius:5px;cursor:pointer;">✖ Close Window</button>
            </div>
            ${allHTML}
        </body></html>`);
        win.document.close();
        win.focus();
    }

    _enrichPlanWithKRAs = async (plan) => {
        try {
            const result = await rpc("/hr_pms_dashboard/get_plan_kra_details", {
                plan_id: plan.plan_id || plan.id
            });
            return { ...plan, kra_lines: result.kra_lines || [], company_name: result.company_name || 'My Company' };
        } catch (error) {
            return { ...plan, kra_lines: [], company_name: 'My Company' };
        }
    }

    _buildPlanHTML = (plan, cycle) => {
        const companyName = plan.company_name;
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
                <div style="text-align:center;"><div style="font-size:9px;color:#aecde8;">Appraisal Cycle</div><div style="font-size:11px;font-weight:bold;">${cycle.name || '-'}</div></div>
                <div style="text-align:center;"><div style="font-size:9px;color:#aecde8;">Start Date</div><div style="font-size:11px;font-weight:bold;">${cycle.start_date || '-'}</div></div>
                <div style="text-align:center;"><div style="font-size:9px;color:#aecde8;">End Date</div><div style="font-size:11px;font-weight:bold;">${cycle.end_date || '-'}</div></div>
            </div>
            <div style="background:#eaf1fb;display:grid;grid-template-columns:1fr 1fr;border:1px solid #2563a8;">
                <div style="padding:10px 14px;border-right:1px solid #c5d5ea;"><div style="font-size:9px;color:#2563a8;font-weight:bold;">EMPLOYEE NAME</div><div style="font-size:13px;">${plan.name || '-'}</div></div>
                <div style="padding:10px 14px;"><div style="font-size:9px;color:#2563a8;font-weight:bold;">DEPARTMENT</div><div style="font-size:13px;">${plan.department || '-'}</div></div>
                <div style="padding:10px 14px;border-top:1px solid #c5d5ea;border-right:1px solid #c5d5ea;"><div style="font-size:9px;color:#2563a8;font-weight:bold;">SUPERVISOR</div><div style="font-size:13px;">${plan.supervisor_name || '-'}</div></div>
                <div style="padding:10px 14px;border-top:1px solid #c5d5ea;"><div style="font-size:9px;color:#2563a8;font-weight:bold;">MANAGER / REVIEWER</div><div style="font-size:13px;">${plan.reviewer_name || plan.secondary_name || '-'}</div></div>
            </div>
            <div style="background:#1a3557;color:#fff;padding:7px 12px;font-size:11px;font-weight:bold;text-align:center;margin-top:14px;">PERFORMANCE PLANNING TEMPLATE – KRA / KPI DETAILS</div>
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
                <div style="padding:12px;text-align:center;border-right:1px solid #c5d5ea;"><div style="font-size:10px;color:#666;">Employee Signature</div><div style="margin-top:28px;border-top:1px solid #bbb;padding-top:4px;font-size:9px;color:#999;">${plan.name || ''}</div></div>
                <div style="padding:12px;text-align:center;border-right:1px solid #c5d5ea;"><div style="font-size:10px;color:#666;">Supervisor Signature</div><div style="margin-top:28px;border-top:1px solid #bbb;padding-top:4px;font-size:9px;color:#999;">${plan.supervisor_name || ''}</div></div>
                <div style="padding:12px;text-align:center;"><div style="font-size:10px;color:#666;">Manager Signature</div><div style="margin-top:28px;border-top:1px solid #bbb;padding-top:4px;font-size:9px;color:#999;">${plan.reviewer_name || plan.secondary_name || ''}</div></div>
            </div>
        </div>`;
    }

    // ============================================================
    // VIEW ALL APPRAISALS - HR MANAGER
    // ============================================================

    viewAllEmployeeAppraisals = async () => {
        this.state.all_appraisals_loading = true;
        try {
            const cycle = this.state.selected_cycle;
            if (!cycle || !cycle.id) {
                this.env.services.notification.add("No cycle selected", { type: "warning" });
                return;
            }
            const result = await rpc("/hr_pms_dashboard/get_cycle_all_appraisals", { cycle_id: cycle.id });
            if (result && !result.error && result.appraisals && result.appraisals.length > 0) {
                this.state.all_appraisals_data = result.appraisals;
                this.state.all_appraisals_summary = result.summary;
                this._generateAllAppraisalsPDF(result.appraisals, {
                    name: cycle.name,
                    start_date: cycle.start_date,
                    end_date: cycle.end_date,
                });
            } else {
                this.env.services.notification.add(result?.error || "No appraisal data found", { type: "warning" });
            }
        } catch (error) {
            console.error("Error generating appraisals:", error);
            this.env.services.notification.add("Error generating appraisals", { type: "danger" });
        } finally {
            this.state.all_appraisals_loading = false;
        }
    }

    closeAllAppraisalsModal = () => {
        this.state.show_all_appraisals_modal = false;
        this.state.all_appraisals_data = [];
        this.state.all_appraisals_summary = null;
    }

    exportAllAppraisalsToExcel = () => {
        if (!this.state.all_appraisals_data || this.state.all_appraisals_data.length === 0) {
            this.env.services.notification.add("No data to export", { type: "warning" });
            return;
        }
        const cycle = this.state.selected_cycle;
        const employees = this.state.all_appraisals_data;
        const headers = ['Sl No', 'Emp ID', 'Employee Name', 'Designation', 'DOJ',
            'Self Rating', '1st Manager Score', '2nd Manager Score', 'Reviewer Score',
            'Final Score', 'Rating', 'Bonus Eligibility %', 'Basic Pay', 'Bonus Amount'];
        const csvLines = [`Cycle: ${cycle?.name || ''}`, `Generated: ${new Date().toLocaleString()}`, '', headers.join(',')];
        employees.forEach((emp, idx) => {
            csvLines.push([
                idx + 1, emp.employee_id, emp.name, emp.designation || '-', emp.doj || '-',
                emp.self_score || 0, emp.supervisor_score || 0, emp.secondary_score || '-',
                emp.reviewer_score || 0, emp.final_score || 0, emp.rating || '-',
                emp.eligibility_pct || 0, emp.basic_pay || 0, emp.bonus_amount || 0,
            ].map(cell => {
                if (typeof cell === 'string' && (cell.includes(',') || cell.includes('"'))) {
                    return `"${cell.replace(/"/g, '""')}"`;
                }
                return cell;
            }).join(','));
        });
        this._downloadCSV(csvLines.join('\n'), `${cycle?.name || 'cycle'}_appraisals.csv`);
        this.env.services.notification.add("Exported successfully!", { type: "success" });
    }

    exportAllAppraisalsToPDF = () => {
        this._generateAllAppraisalsPDF(this.state.all_appraisals_data, this.state.selected_cycle);
    }

    _generateAllAppraisalsPDF = (appraisals, cycle) => {
        const companyName = this.state.all_appraisals_summary?.company_name || 'Company';
        const rows = appraisals.map((emp, idx) => `
            <tr>
                <td class="text-center">${idx + 1}</td>
                <td class="text-center">${emp.employee_id || '-'}</td>
                <td class="text-left font-bold">${this._escapeHtml(emp.name || '-')}</td>
                <td class="text-left">${this._escapeHtml(emp.designation || '-')}</td>
                <td class="text-center">${emp.self_score || 0}</td>
                <td class="text-center">${emp.supervisor_score || 0}</td>
                <td class="text-center">${emp.secondary_score || '-'}</td>
                <td class="text-center">${emp.reviewer_score || 0}</td>
                <td class="text-center font-bold">${emp.final_score || 0}</td>
                <td class="text-center">${emp.rating || '-'}</td>
                <td class="text-center">${emp.eligibility_pct || 0}%</td>
                <td class="text-right">${this._formatCurrency(emp.basic_pay || 0)}</td>
                <td class="text-right font-bold">${this._formatCurrency(emp.bonus_amount || 0)}</td>
            </tr>`).join('');

        const html = `<!DOCTYPE html><html><head>
            <title>${cycle.name || 'Appraisals'} – Employee Appraisal Report</title>
            <style>
                * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; font-size: 12px; }
                @media print { body { padding: 0; } @page { margin: 15mm; } .no-print { display: none; } }
                table { width: 100%; border-collapse: collapse; font-size: 11px; }
                th { background: #1a3557; color: #fff; padding: 10px 6px; border: 1px solid #1a3557; text-align: center; }
                td { padding: 8px 6px; border: 1px solid #c5d5ea; }
                .text-center { text-align: center; } .text-right { text-align: right; }
                .text-left { text-align: left; } .font-bold { font-weight: bold; }
                .no-print { text-align: center; margin-bottom: 20px; }
                button { padding: 10px 20px; margin: 10px; background: #1a3557; color: #fff; border: none; border-radius: 5px; cursor: pointer; }
            </style>
        </head><body>
            <div class="no-print">
                <button onclick="window.print();">📄 Save as PDF / Print</button>
                <button onclick="window.close();">✖ Close Window</button>
            </div>
            <div style="background:#1a3557;color:#fff;padding:20px;text-align:center;">
                <h1 style="margin:0;font-size:20px;">${this._escapeHtml(companyName)}</h1>
                <p style="margin:5px 0 0;font-size:12px;color:#aecde8;">Employee Performance Appraisal Report</p>
            </div>
            <div style="background:#2563a8;color:#fff;display:flex;justify-content:space-between;padding:12px 20px;">
                <div style="text-align:center;flex:1;"><div style="font-size:9px;color:#aecde8;">Appraisal Cycle</div><div style="font-size:12px;font-weight:bold;">${this._escapeHtml(cycle.name || '-')}</div></div>
                <div style="text-align:center;flex:1;"><div style="font-size:9px;color:#aecde8;">Start Date</div><div style="font-size:12px;font-weight:bold;">${cycle.start_date || '-'}</div></div>
                <div style="text-align:center;flex:1;"><div style="font-size:9px;color:#aecde8;">End Date</div><div style="font-size:12px;font-weight:bold;">${cycle.end_date || '-'}</div></div>
            </div>
            <table style="margin-top:20px;">
                <thead><tr>
                    <th>#</th><th>Emp ID</th><th>Employee Name</th><th>Designation</th>
                    <th>Self</th><th>1st Mgr</th><th>2nd Mgr</th><th>Reviewer</th>
                    <th>Final</th><th>Rating</th><th>Bonus %</th><th>Basic Pay</th><th>Bonus Amount</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
            <div style="text-align:center;font-size:8px;color:#999;margin-top:20px;padding-top:10px;border-top:1px solid #eee;">
                Generated on: ${new Date().toLocaleString()}
            </div>
        </body></html>`;

        const win = window.open('', '_blank');
        win.document.write(html);
        win.document.close();
        win.focus();
    }

    // ============================================================
    // PLAN CLICK HANDLERS
    // ============================================================

    onClickEmployeePlan = (item) => {
        this.state.selected_plan = item;
    }

    onClosePlanModal = () => {
        this.state.selected_plan = null;
    }
    onClickTotalCycles = () => {
    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'pms.cycle',
        views: [[false, 'list']],
        target: 'current',
        name: 'All Cycles',
    });
}

onClickProbationActiveCycles = () => {
    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'pms.cycle',
        views: [[false, 'list']],
        domain: [['state', 'in', ['planning', 'monitoring', 'appraisal']], ['cycle_type', '=', 'probation']],
        target: 'current',
        name: 'Probation Active Cycles',
    });
}

onClickTotalActiveEmployees = () => {
    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'hr.employee',
        views: [[false, 'list']],
        domain: [['active', '=', true]],
        target: 'current',
        name: 'Total Active Employees',
    });
}

    sendReminder = (emp) => {
        rpc("/hr_pms_dashboard/send_reminder", {
            employee_id: emp.employee_id,
            cycle_id: this.state.selected_cycle_id,
        }).then(result => {
            if (result.success) {
                this.env.services.notification.add("Reminder sent successfully!", { type: "success" });
            }
        }).catch(() => {
            this.env.services.notification.add("Failed to send reminder", { type: "danger" });
        });
    }

    sendReminderFromModal = (plan) => {
        this.sendReminder(plan);
    }

    sendAppraisalReminder = (appraisal) => {
        rpc("/hr_pms_dashboard/send_reminder", {
            employee_id: appraisal.employee_id,
            cycle_id: this.state.selected_cycle_id,
        }).then(result => {
            if (result.success) {
                this.env.services.notification.add("Reminder sent successfully!", { type: "success" });
            }
        }).catch(() => {
            this.env.services.notification.add("Failed to send reminder", { type: "danger" });
        });
    }

    // ============================================================
    // PLAN RECORD NAVIGATION
    // ============================================================

    onOpenPlanRecord = (plan) => {
        const planId = plan.plan_id || plan.id;
        if (!planId) {
            this.env.services.notification.add("Cannot open plan: Invalid data", { type: "warning" });
            return;
        }
        const isPendingApproval = plan.state_key === 'pending_supervisor' ||
            plan.state_key === 'pending_secondary_supervisor' ||
            plan.state_key === 'pending_reviewer';
        const formViewRef = isPendingApproval
            ? 'hr_employee_evaluation.view_employee_plans_supervisor_form'
            : 'hr_employee_evaluation.view_employee_performance_planning_form';
        const title = isPendingApproval ? 'Review Performance Plan'
            : plan.state_key === 'draft' ? 'Edit My Performance Plan'
            : 'My Performance Plan';
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: title,
            res_model: 'pms.appraisal',
            res_id: planId,
            views: [[false, 'form']],
            target: 'current',
            context: { create: false, delete: false, form_view_ref: formViewRef },
        });
    }

    onOpenAppraisalRecord = (appraisal) => {
        if (appraisal && appraisal.constructor && appraisal.constructor.name === 'PointerEvent') {
            console.error("Wrong parameter passed to onOpenAppraisalRecord");
            return;
        }
        const appraisalId = appraisal.id || appraisal.appraisal_id;
        if (!appraisalId) {
            this.env.services.notification.add("Cannot open appraisal: Invalid data", { type: "danger" });
            return;
        }
        const isSupervisorOrReviewer = this.state.role === 'supervisor' ||
            this.state.role === 'secondary_supervisor' || this.state.role === 'reviewer';
        const formViewRef = isSupervisorOrReviewer
            ? 'hr_employee_evaluation.view_employee_appraisals_supervisor_form'
            : 'hr_employee_evaluation.view_pms_appraisal_form';
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'pms.appraisal',
            res_id: appraisalId,
            views: [[false, 'form']],
            target: 'current',
            context: { form_view_ref: formViewRef, no_breadcrumbs: false },
        });
    }

    onClickEmployeeAppraisal = (appraisal) => {
        const appraisalId = appraisal.id || appraisal.appraisal_id || appraisal.plan_id;
        if (!appraisalId) {
            this.env.services.notification.add("Cannot open appraisal: Missing ID", { type: "danger" });
            return;
        }
        this.onOpenAppraisalRecord({ id: appraisalId });
    }

    onDoAction = (action) => {
        if (action.action_type === 'complete_plan' || action.action_type === 'view_plan') {
            this.onOpenPlanRecord({ id: action.plan_id, plan_id: action.plan_id, state_key: action.action_type === 'complete_plan' ? 'draft' : '' });
        } else if (action.action_type === 'start_appraisal' || action.action_type === 'view_appraisal') {
            this.onOpenAppraisalRecord({ id: action.appraisal_id });
        } else {
            if (action.plan_id) this.onOpenPlanRecord({ id: action.plan_id });
            else if (action.appraisal_id) this.onOpenAppraisalRecord({ id: action.appraisal_id });
        }
    }

    // ============================================================
    // FULL PLAN / APPRAISAL DETAILS (EMPLOYEE VIEW)
    // ============================================================

    openFullPlanDetails = (plan) => {
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

    closeFullPlanDetails = () => {
        this.state.show_full_plan_details = false;
        this.state.selected_full_plan = null;
    }

    openFullAppraisalDetails = async (appraisal) => {
        if (!appraisal || appraisal.constructor?.name === 'PointerEvent') {
            this.env.services.notification.add("Cannot open appraisal details: Invalid data", { type: "danger" });
            return;
        }
        const appraisalId = appraisal.id || appraisal.appraisal_id;
        if (!appraisalId) {
            this.env.services.notification.add("Cannot open appraisal details: Missing ID", { type: "danger" });
            return;
        }
        this.state.show_full_appraisal_details = true;
        this.state.selected_full_appraisal = null;
        try {
            const result = await rpc("/hr_pms_dashboard/get_appraisal_details", { appraisal_id: appraisalId });
            if (result && result.success) {
                this.state.selected_full_appraisal = result.data;
            } else {
                this.env.services.notification.add(result?.error || "Failed to load appraisal details", { type: "danger" });
            }
        } catch (error) {
            this.env.services.notification.add("Error loading appraisal details", { type: "danger" });
        }
    }

    closeFullAppraisalDetails = () => {
        this.state.show_full_appraisal_details = false;
        this.state.selected_full_appraisal = null;
    }

    // ============================================================
    // EXPORT - PLAN
    // ============================================================

    exportPlanToExcel = () => {
        if (!this.state.selected_full_plan || !this.state.selected_full_plan.kpis) {
            this.env.services.notification.add('No data to export', { type: 'warning' });
            return;
        }
        const plan = this.state.selected_full_plan;
        const clean = (val, maxLen = 100) => {
            if (!val) return '-';
            return String(val).replace(/\r\n|\n|\r/g, ' ').replace(/\s+/g, ' ').trim().substring(0, maxLen);
        };
        const escape = (val) => {
            const str = clean(val);
            return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str;
        };
        const csvLines = [
            `Plan For:,${escape(plan.name || '')}`,
            `Cycle Name:,${escape(plan.cycle || '')}`,
            `Department:,${escape(plan.department || '-')}`,
            `Evaluation Group:,${escape(plan.evaluation_group || '-')}`,
            `Primary Manager:,${escape(plan.supervisor_name || '-')}`,
            `Secondary Manager:,${escape(plan.secondary_name || '-')}`,
            `Reviewer:,${escape(plan.reviewer_name || '-')}`,
            `Status:,${escape(plan.state || '-')}`,
            '',
            'KRA / GOAL,KPI / METRIC,DESCRIPTION,CRITERIA,SCORE (WEIGHTAGE),TARGET',
        ];
        const grouped = {};
        plan.kpis.forEach(kpi => {
            const kra = kpi.kra_name || 'No KRA';
            if (!grouped[kra]) grouped[kra] = [];
            grouped[kra].push(kpi);
        });
        Object.entries(grouped).forEach(([kraName, kraKpis]) => {
            kraKpis.forEach((kpi, index) => {
                csvLines.push([
                    index === 0 ? kraName : '',
                    kpi.kpi_name || '-',
                    clean(kpi.description, 100),
                    clean(kpi.criteria, 100),
                    `${kpi.weightage || 0}%`,
                    kpi.target || 'Not Set',
                ].map(escape).join(','));
            });
        });
        this._downloadCSV(csvLines.join('\n'), `${plan.cycle || 'plan'}_${plan.name || 'details'}.csv`);
        this.env.services.notification.add("Exported successfully!", { type: "success" });
    }

    exportPlanToPDF = async () => {
        const modalBody = document.querySelector('.pms_plan_modal_body');
        if (!modalBody) return;
        const element = modalBody.cloneNode(true);
        element.style.maxHeight = 'none';
        element.style.overflow = 'visible';
        element.style.height = 'auto';
        element.querySelectorAll('*').forEach(el => {
            el.style.overflow = 'visible';
            el.style.maxHeight = 'none';
        });
        const opt = {
            margin: [0.4, 0.4, 0.4, 0.4],
            filename: `${this.state.selected_full_plan.cycle || 'plan'}_details.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2, letterRendering: true, useCORS: true, scrollX: 0, scrollY: 0 },
            jsPDF: { unit: 'in', format: 'a4', orientation: 'landscape' },
            pagebreak: { mode: ['avoid-all', 'css', 'legacy'], avoid: ['tr', 'td'] },
        };
        this.env.services.notification.add("Exporting to PDF...", { type: "info" });
        html2pdf().set(opt).from(element).toPdf().get('pdf').then(pdf => {
            const totalPages = pdf.internal.getNumberOfPages();
            for (let i = 1; i <= totalPages; i++) {
                pdf.setPage(i);
                pdf.setFontSize(8);
                pdf.setTextColor(150);
                pdf.text(`Page ${i} of ${totalPages}`, pdf.internal.pageSize.getWidth() / 2, pdf.internal.pageSize.getHeight() - 0.2, { align: 'center' });
            }
        }).save();
    }

    // ============================================================
    // EXPORT - APPRAISAL
    // ============================================================

    exportAppraisalToExcel = () => {
        if (!this.state.selected_full_appraisal) {
            this.env.services.notification.add("No data to export", { type: "warning" });
            return;
        }
        const appraisal = this.state.selected_full_appraisal;
        const escape = (val) => {
            const str = String(val ?? '-');
            return str.includes(',') || str.includes('"') || str.includes('\n') ? `"${str.replace(/"/g, '""')}"` : str;
        };
        const csvLines = [
            `Appraisal For:,${escape(appraisal.name)}`,
            `Cycle Name:,${escape(appraisal.cycle)}`,
            `Department:,${escape(appraisal.department)}`,
            `Status:,${escape(appraisal.state)}`,
            `Primary Manager:,${escape(appraisal.supervisor_name)}`,
            `Secondary Manager:,${escape(appraisal.secondary_name || '-')}`,
            `Reviewer:,${escape(appraisal.reviewer_name || '-')}`,
            `Total Weightage:,${escape(appraisal.total_weightage || 0)}%`,
            '', 'KPI SCORES,,,,,,',
            'KPI,Weightage,Emp Score,1st Manager,2nd Manager,Reviewer Score',
        ];
        (appraisal.kpi_lines || []).forEach(line => {
            csvLines.push([escape(line.kpi_name), escape(line.weightage || 0),
                escape(line.self_score || '-'), escape(line.supervisor_score || '-'),
                escape(line.secondary_score || '-'), escape(line.reviewer_score || '-')].join(','));
        });
        csvLines.push('', 'COMPETENCY SCORES,,,,,,', 'Competency,Emp Score,1st Manager,2nd Manager,Reviewer Score');
        (appraisal.competency_lines || []).forEach(line => {
            csvLines.push([escape(line.competency_name), escape(line.self_score || '-'),
                escape(line.supervisor_score || '-'), escape(line.secondary_score || '-'),
                escape(line.reviewer_score || '-')].join(','));
        });
        csvLines.push('', 'FINAL SCORE SUMMARY,,,,,,',
            `KPI Total:,${escape(appraisal.kpi_total || 0)},,,,`,
            `Competency Total:,${escape(appraisal.competency_total || 0)},,,,`,
            `Final Score:,${escape(appraisal.final_score || 0)},,,,`,
            `Rating:,${escape(appraisal.rating || '-')},,,,`,
            '', 'BONUS SUMMARY,,,,,,',
            `Rating Tier:,${escape(appraisal.rating || '-')},,,,`,
            `Basic Pay:,${escape(appraisal.basic_pay_display || appraisal.basic_pay || 0)},,,,`,
            `Bonus Eligibility %:,${escape(appraisal.eligibility_pct || 0)}%,,,,`,
            `Bonus Amount:,${escape(appraisal.bonus_amount_display || appraisal.bonus_amount || 0)},,,,`,
        );
        this._downloadCSV(csvLines.join('\n'), `${appraisal.cycle || 'appraisal'}_${appraisal.name || 'details'}.csv`);
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
        const kpiRows = (appraisal.kpi_lines || []).map(l => `<tr><td style="padding:6px 8px;border:1px solid #c5d5ea;">${l.kpi_name || '-'}</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.weightage || 0}%</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.self_score || 0}</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.supervisor_score || 0}</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.secondary_score || '-'}</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.reviewer_score || 0}</td></tr>`).join('');
        const compRows = (appraisal.competency_lines || []).map(l => `<tr><td style="padding:6px 8px;border:1px solid #c5d5ea;">${l.competency_name || '-'}</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.self_score || 0}</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.supervisor_score || 0}</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.secondary_score || '-'}</td><td style="padding:6px 8px;border:1px solid #c5d5ea;text-align:center;">${l.reviewer_score || 0}</td></tr>`).join('');
        const html = `<div style="font-family:Arial,sans-serif;padding:16px;">
            <div style="background:#1a3557;color:#fff;padding:14px;text-align:center;font-size:16px;font-weight:bold;">Performance Appraisal — ${appraisal.name || ''}</div>
            <div style="background:#2563a8;color:#fff;display:flex;justify-content:space-around;padding:8px;">
                <div><span style="font-size:9px;color:#aecde8;">Cycle</span><br/><b>${appraisal.cycle || '-'}</b></div>
                <div><span style="font-size:9px;color:#aecde8;">Department</span><br/><b>${appraisal.department || '-'}</b></div>
                <div><span style="font-size:9px;color:#aecde8;">Status</span><br/><b>${appraisal.state || '-'}</b></div>
                <div><span style="font-size:9px;color:#aecde8;">Final Score</span><br/><b>${appraisal.final_score || 0}</b></div>
                <div><span style="font-size:9px;color:#aecde8;">Rating</span><br/><b>${appraisal.rating || '-'}</b></div>
            </div>
            ${kpiRows ? `<div style="margin-top:14px;"><div style="background:#1a3557;color:#fff;padding:7px;font-size:11px;font-weight:bold;">KPI SCORES</div><table style="width:100%;border-collapse:collapse;font-size:11px;"><thead><tr style="background:#2563a8;color:#fff;"><th style="padding:7px;border:1px solid #1a3557;">KPI</th><th style="padding:7px;border:1px solid #1a3557;width:8%;">Weight</th><th style="padding:7px;border:1px solid #1a3557;width:10%;">Self</th><th style="padding:7px;border:1px solid #1a3557;width:10%;">1st Mgr</th><th style="padding:7px;border:1px solid #1a3557;width:10%;">2nd Mgr</th><th style="padding:7px;border:1px solid #1a3557;width:10%;">Reviewer</th></tr></thead><tbody>${kpiRows}</tbody></table></div>` : ''}
            ${compRows ? `<div style="margin-top:14px;"><div style="background:#1a3557;color:#fff;padding:7px;font-size:11px;font-weight:bold;">COMPETENCY SCORES</div><table style="width:100%;border-collapse:collapse;font-size:11px;"><thead><tr style="background:#2563a8;color:#fff;"><th style="padding:7px;border:1px solid #1a3557;">Competency</th><th style="padding:7px;border:1px solid #1a3557;width:10%;">Self</th><th style="padding:7px;border:1px solid #1a3557;width:10%;">1st Mgr</th><th style="padding:7px;border:1px solid #1a3557;width:10%;">2nd Mgr</th><th style="padding:7px;border:1px solid #1a3557;width:10%;">Reviewer</th></tr></thead><tbody>${compRows}</tbody></table></div>` : ''}
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

    // ============================================================
    // EXPORT - COMPLETED CYCLE (EMPLOYEE VIEW)
    // ============================================================

    exportCompletedCycleToExcel = () => {
        if (!this.state.selected_completed_cycle) {
            this.env.services.notification.add("No data to export", { type: "warning" });
            return;
        }
        const cycle = this.state.selected_completed_cycle;
        const escape = (val) => {
            const str = String(val ?? '-');
            return str.includes(',') || str.includes('"') || str.includes('\n') ? `"${str.replace(/"/g, '""')}"` : str;
        };
        const csvLines = [
            `Appraisal For:,${escape(cycle.employee_name)}`,
            `Cycle Name:,${escape(cycle.cycle_name)}`,
            `Department:,${escape(cycle.department)}`,
            `Status:,Completed`,
            `Primary Manager:,${escape(cycle.supervisor_name)}`,
            `Secondary Manager:,${escape(cycle.secondary_name || '-')}`,
            `Reviewer:,${escape(cycle.reviewer_name || '-')}`,
            `Total Weightage:,${escape(cycle.total_weightage || 0)}%`,
            '', 'KPI SCORES,,,,,,',
            'KPI,Weightage,Self Score,1st Manager,2nd Manager,Reviewer Score',
        ];
        (cycle.kpi_lines || []).forEach(line => {
            csvLines.push([escape(line.kpi_name), escape(line.weightage || 0),
                escape(line.self_score || '-'), escape(line.supervisor_score || '-'),
                escape(line.secondary_score || '-'), escape(line.reviewer_score || '-')].join(','));
        });
        csvLines.push('', 'COMPETENCY SCORES,,,,,,', 'Competency,Self Score,1st Manager,2nd Manager,Reviewer Score');
        (cycle.competency_lines || []).forEach(line => {
            csvLines.push([escape(line.competency_name), escape(line.self_score || '-'),
                escape(line.supervisor_score || '-'), escape(line.secondary_score || '-'),
                escape(line.reviewer_score || '-')].join(','));
        });
        csvLines.push('', 'FINAL SCORE SUMMARY,,,,,,',
            `Final Score:,${escape(cycle.final_score || 0)},,,,`,
            `Rating:,${escape(cycle.rating || '-')},,,,`,
        );
        this._downloadCSV(csvLines.join('\n'), `${cycle.cycle_name}_appraisal_details.csv`);
        this.env.services.notification.add("Exported successfully!", { type: "success" });
    }



    // ============================================================
    // FILTER METHODS
    // ============================================================

   filterCyclePlanningData() {
    const search = (this.state.cycle_planning_search || '').toLowerCase();
    if (!search) {
        this.state.filtered_cycle_planning_data = [...this.state.cycle_planning_data];
    } else {
        this.state.filtered_cycle_planning_data = this.state.cycle_planning_data.filter(function(plan) {
            return plan.name.toLowerCase().includes(search) || plan.department.toLowerCase().includes(search);
        });
    }
}

exportCompletedCycleToPDF() {
    if (!this.state.selected_completed_cycle) {
        this.env.services.notification.add("No data to export", { type: "warning" });
        return;
    }
    const cycle = this.state.selected_completed_cycle;

    const tableWrapper = document.getElementById('completed_cycle_export_table');
    if (!tableWrapper) {
        this.env.services.notification.add("Table not found", { type: "warning" });
        return;
    }

    this.env.services.notification.add("Generating PDF...", { type: "info" });

    const self = this;

    // Work directly on the ORIGINAL element, no cloning
    // Temporarily override styles to remove overflow clipping
    const originalStyles = {
        overflow: tableWrapper.style.overflow,
        overflowX: tableWrapper.style.overflowX,
        maxHeight: tableWrapper.style.maxHeight,
        height: tableWrapper.style.height,
        width: tableWrapper.style.width,
    };

    const innerTable = tableWrapper.querySelector('table');
    const originalTableStyles = innerTable ? {
        minWidth: innerTable.style.minWidth,
        width: innerTable.style.width,
        fontSize: innerTable.style.fontSize,
    } : {};

    // Apply expanded styles directly to the real element
    tableWrapper.style.overflow = 'visible';
    tableWrapper.style.overflowX = 'visible';
    tableWrapper.style.maxHeight = 'none';
    tableWrapper.style.height = 'auto';
    tableWrapper.style.width = 'auto';

    if (innerTable) {
        innerTable.style.minWidth = 'unset';
        innerTable.style.width = 'auto';
        innerTable.style.fontSize = '10px';
    }

    setTimeout(function() {
        const fullWidth = tableWrapper.scrollWidth;
        const fullHeight = tableWrapper.scrollHeight;

        const opt = {
            margin: [0.2, 0.2, 0.2, 0.2],
            filename: (cycle && cycle.name ? cycle.name : 'completed_cycle') + '_appraisal_report.pdf',
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: {
                scale: 2,
                useCORS: true,
                logging: true,   // turn on so you can see errors in console
                scrollX: 0,
                scrollY: 0,
                width: fullWidth,
                height: fullHeight,
                windowWidth: fullWidth,
            },
            jsPDF: { unit: 'in', format: 'a3', orientation: 'landscape' },
        };

        html2pdf().set(opt).from(tableWrapper).save()
            .then(function() {
                // Restore original styles after export
                tableWrapper.style.overflow = originalStyles.overflow;
                tableWrapper.style.overflowX = originalStyles.overflowX;
                tableWrapper.style.maxHeight = originalStyles.maxHeight;
                tableWrapper.style.height = originalStyles.height;
                tableWrapper.style.width = originalStyles.width;

                if (innerTable) {
                    innerTable.style.minWidth = originalTableStyles.minWidth;
                    innerTable.style.width = originalTableStyles.width;
                    innerTable.style.fontSize = originalTableStyles.fontSize;
                }

                self.env.services.notification.add("PDF exported successfully!", { type: "success" });
            })
            .catch(function() {
                // Restore on error too
                tableWrapper.style.overflow = originalStyles.overflow;
                tableWrapper.style.overflowX = originalStyles.overflowX;
                tableWrapper.style.maxHeight = originalStyles.maxHeight;
                tableWrapper.style.height = originalStyles.height;
                tableWrapper.style.width = originalStyles.width;

                if (innerTable) {
                    innerTable.style.minWidth = originalTableStyles.minWidth;
                    innerTable.style.width = originalTableStyles.width;
                    innerTable.style.fontSize = originalTableStyles.fontSize;
                }

                self.env.services.notification.add("Error generating PDF", { type: "danger" });
            });

    }, 300);
}
    filterCycleAppraisalData = () => {
        const search = (this.state.cycle_appraisal_search || '').toLowerCase();
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

    filterCompletedCycles = () => {
        const searchTerm = (this.state.completed_cycle_search || '').toLowerCase().trim();
        if (!searchTerm) {
            this.state.filtered_past_cycles = [...(this.state.employee?.past_cycles || [])];
        } else {
            this.state.filtered_past_cycles = (this.state.employee?.past_cycles || []).filter(cycle =>
                cycle.cycle_name?.toLowerCase().includes(searchTerm)
            );
        }
    }

    // ============================================================
    // HR MANAGER STAT CARD CLICKS
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

    onClickEmployeesInActiveCycles = () => {
    const uniqueIds = this._dataCache?.employees_in_active_cycles_ids || [];

    if (uniqueIds.length === 0) {
        this.env.services.notification.add("No employees found in active cycles", { type: "warning" });
        return;
    }


    this.action.doAction({
        type: 'ir.actions.act_window',
        res_model: 'hr.employee',
        views: [[false, 'list']],
        domain: [['id', 'in', uniqueIds]],
        target: 'current',
        name: 'Employees in Active Cycles',
    });
}

    // ============================================================
    // MAIN DATA LOAD
    // ============================================================

    async _loadData() {
        try {
            const data = await rpc("/hr_pms_dashboard/data", { requested_role: this.state.requestedRole });
            if (data.error) {
                this.state.error = data.error + (data.traceback ? '\n' + data.traceback : '');
                this.state.loading = false;
                return;
            }
            this._dataCache = data;
            this.state.employee_id = data.employee_id || 0;
            this.state.employee_name = data.employee_name || "";

            if (this.state.requestedRole === 'hr_manager' && data.role === 'hr_manager') {
                this.state.role = 'hr_manager';
                this.state.stats = data.stats || {};
                this.state.stats.employees_in_active_cycles = data.employees_in_active_cycles || 0;
                this.state.active_cycles_list = data.active_cycles_list || [];
                this.state.completed_cycles_list = data.completed_cycles_list || [];
                this.state.filtered_completed_cycles_list = [...(data.completed_cycles_list || [])];
                this.state.top_performers = data.top_performers || [];
                this.state.bottom_performers = data.bottom_performers || [];
                this.state.employees_with_plan = data.employees_with_plan || [];
                this.state.employees_no_plan_count = data.employees_no_plan_count || 0;
                this.state.employees_no_appraisal_count = data.employees_no_appraisal_count || 0;
                this.state.loading = false;
                await this._ensureChartJS();
                return;
            }

            if (this.state.requestedRole === 'employee' && data.employee) {
                this.state.role = 'employee';
                this.state.employee = data.employee;
                if (data.employee.past_cycles) {
                    this.state.filtered_past_cycles = [...data.employee.past_cycles];
                }
                this.state.loading = false;
                await this._ensureChartJS();
                await this._waitForDOM(200);
                this._destroyAllCharts();

                return;
            }

            if (this.state.requestedRole === 'supervisor' && data.supervisor) {
                this.state.role = 'supervisor';
                this.state.supervisor = data.supervisor;
                this.state.loading = false;
                await this._ensureChartJS();
                return;
            }

            if (this.state.requestedRole === 'reviewer' && data.reviewer) {
                this.state.role = 'reviewer';
                this.state.reviewer = data.reviewer;
                this.state.loading = false;
                await this._ensureChartJS();
                return;
            }

            // Fallback
            this.state.role = data.role;
            this.state.loading = false;

        } catch (e) {
            console.error("Dashboard load error:", e);
            this.state.error = "Failed to load dashboard data. Please refresh.";
            this.state.loading = false;
        }
    }

    // ============================================================
    // CHART HELPERS
    // ============================================================

    async _ensureChartJS() {
        await new Promise(resolve => {
            const check = () => window.Chart ? resolve() : setTimeout(check, 100);
            check();
        });
    }

    async _waitForDOM(ms) {
        await new Promise(resolve => setTimeout(resolve, ms));
    }

    _destroyAllCharts() {
        if (this.chartInstances && this.chartInstances.length) {
            this.chartInstances.forEach(chart => {
                try { if (chart && typeof chart.destroy === 'function') chart.destroy(); } catch (e) { }
            });
            this.chartInstances = [];
        }
        [
            'cyclePlansDeptChartRef', 'cyclePlansGroupChartRef', 'cyclePlanStatusChartRef',
        ].forEach(refName => {
            const ref = this[refName];
            if (ref && ref.el) {
                try {
                    const existing = window.Chart?.getChart(ref.el);
                    if (existing) existing.destroy();
                } catch (e) { }
            }
        });
    }

    _renderPlanningChartsByRole = async () => {
        if (this.state.role === 'hr_manager') {
            await this._renderCyclePlanningCharts();
        }
        // Supervisor and reviewer planning charts use cyclePlanStatusChartRef only
        else if (this.state.role === 'supervisor' || this.state.role === 'reviewer') {
            await this._renderCyclePlanStatusChart(this.state.selected_cycle?.team_plans || this.state.selected_cycle?.all_plans || []);
        }
    }

    _renderCyclePlanStatusChart = async (plans) => {
        await this._ensureChartJS();
        await this._waitForDOM(200);
        const Chart = window.Chart;
        if (!Chart || !this.cyclePlanStatusChartRef.el) return;
        const existing = Chart.getChart(this.cyclePlanStatusChartRef.el);
        if (existing) existing.destroy();
        const statusMap = { draft: 0, pending_supervisor: 0, pending_secondary_supervisor: 0, pending_reviewer: 0, approved: 0 };
        plans.forEach(plan => { if (statusMap.hasOwnProperty(plan.state_key)) statusMap[plan.state_key]++; });
        const values = [statusMap.draft, statusMap.pending_supervisor, statusMap.pending_secondary_supervisor, statusMap.pending_reviewer, statusMap.approved];
        if (!values.some(v => v > 0)) return;
        this.chartInstances.push(new Chart(this.cyclePlanStatusChartRef.el, {
            type: 'doughnut',
            data: {
                labels: ['Draft', 'Pending 1st', 'Pending 2nd', 'Pending Final', 'Approved'],
                datasets: [{ data: values, backgroundColor: ['#6c757d', '#0d6efd', '#ffc107', '#6f42c1', '#198754'], borderWidth: 1, borderColor: '#fff' }],
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '60%',
                plugins: { legend: { position: 'right', labels: { font: { size: 10 } } } },
            },
        }));
    }

    _renderCyclePlanningCharts = async () => {
        await this._ensureChartJS();
        await this._waitForDOM(200);
        const Chart = window.Chart;
        if (!Chart) return;

        [this.cyclePlansDeptChartRef, this.cyclePlansGroupChartRef, this.cyclePlanStatusChartRef].forEach(ref => {
            if (ref && ref.el) {
                const existing = Chart.getChart(ref.el);
                if (existing) existing.destroy();
            }
        });

        const planningData = this.state.cycle_planning_data;

        // Chart 1: By Department
        const deptMap = {};
        planningData.forEach(plan => {
            const dept = plan.department || 'No Department';
            deptMap[dept] = (deptMap[dept] || 0) + 1;
        });
        if (this.cyclePlansDeptChartRef.el && Object.keys(deptMap).length > 0) {
            this.chartInstances.push(new Chart(this.cyclePlansDeptChartRef.el, {
                type: 'bar',
                data: { labels: Object.keys(deptMap), datasets: [{ label: 'Number of Plans', data: Object.values(deptMap), backgroundColor: '#0d6efd', borderRadius: 4 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } },
            }));
        }

        // Chart 2: By Evaluation Group
        const groupMap = {};
        planningData.forEach(plan => {
            const group = plan.evaluation_group || 'No Group';
            groupMap[group] = (groupMap[group] || 0) + 1;
        });
        if (this.cyclePlansGroupChartRef.el && Object.keys(groupMap).length > 0) {
            this.chartInstances.push(new Chart(this.cyclePlansGroupChartRef.el, {
                type: 'bar',
                data: { labels: Object.keys(groupMap), datasets: [{ label: 'Number of Plans', data: Object.values(groupMap), backgroundColor: '#6f42c1', borderRadius: 4 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } },
            }));
        }

        // Chart 3: Status Breakdown
        await this._renderCyclePlanStatusChart(planningData);
    }


    // ============================================================
    // UTILITY
    // ============================================================

    _downloadCSV = (content, filename) => {
        const blob = new Blob(["\uFEFF" + content], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    _escapeHtml = (text) => {
        if (!text) return '';
        return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    _formatCurrency = (amount) => {
        if (!amount) return '0.00';
        return amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    navigateTo = (model, domain, name) => {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            views: [[false, 'list']],
            domain: domain || [],
            target: 'current',
            name: name || "Records",
        });
    }
}

registry.category("actions").add("pms_dashboard", PMSDashboard);