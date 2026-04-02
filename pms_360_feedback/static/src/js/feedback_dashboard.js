/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, xml } from "@odoo/owl";

export class FeedbackDashboard extends Component {
    static template = xml`
        <div t-att-class="'fb-outer ' + (state.darkMode ? 'fb-dark' : 'fb-light')">

            <t t-if="state.loading">
                <div class="fb-loading">
                    <div class="fb-spinner"/>
                    <p>Loading your feedback...</p>
                </div>
            </t>

            <t t-if="!state.loading and !state.employeeName">
                <div class="fb-empty">
                    <div class="fb-empty-icon">⚠️</div>
                    <h2>No employee record found</h2>
                    <p>Please contact HR to link your user account to an employee profile.</p>
                </div>
            </t>

            <t t-if="!state.loading and state.employeeName">
                <div class="fb-header">
                    <div class="fb-header-left">
                        <h1>Feedback <span>Dashboard</span></h1>
                        <p>A visual summary of all feedback received about you</p>
                    </div>
                    <div class="fb-header-right">
                        <button class="fb-theme-toggle" t-on-click="toggleTheme">
                            <t t-if="state.darkMode">☀️ Light Mode</t>
                            <t t-if="!state.darkMode">🌙 Dark Mode</t>
                        </button>
                        <div class="fb-employee-badge">
                            <div class="fb-avatar">
                                <t t-esc="state.employeeInitial"/>
                            </div>
                            <span class="fb-emp-name" t-esc="state.employeeName"/>
                        </div>
                    </div>
                </div>

                <t t-if="state.sessions.length === 0">
                    <div class="fb-empty">
                        <div class="fb-empty-icon">📭</div>
                        <h2>No feedback yet</h2>
                        <p>Once colleagues submit feedback about you, your dashboard will appear here.</p>
                    </div>
                </t>

                <t t-if="state.sessions.length > 0">
                    <div class="fb-session-bar">
                        <label>Session</label>
                        <t t-foreach="state.sessions" t-as="session" t-key="session.id">
                            <button
                                t-att-class="'fb-session-pill' + (state.selectedSessionId === session.id ? ' active' : '')"
                                t-on-click="() => this.selectSession(session.id)">
                                <t t-esc="session.name"/>
                            </button>
                        </t>
                    </div>

                    <div class="fb-stats-row">
                        <div class="fb-stat-card">
                            <div class="fb-stat-value" t-esc="state.totalResponses"/>
                            <div class="fb-stat-label">Responses Received</div>
                        </div>
                        <div class="fb-stat-card">
                            <div class="fb-stat-value" t-esc="state.summaries.length"/>
                            <div class="fb-stat-label">Questions Answered</div>
                        </div>
                        <div class="fb-stat-card">
                            <div class="fb-stat-value fb-stat-session" t-esc="state.selectedSessionName"/>
                            <div class="fb-stat-label">Current Session</div>
                        </div>
                    </div>

                    <t t-if="state.summaries.length === 0">
                        <div class="fb-empty">
                            <div class="fb-empty-icon">🔍</div>
                            <h2>No responses yet</h2>
                            <p>No feedback has been submitted for this session yet.</p>
                        </div>
                    </t>

                    <div class="fb-questions">
                        <t t-foreach="state.summaries" t-as="summary" t-key="summary_index">
                            <div class="fb-question-card">
                                <div class="fb-q-header">
                                    <div class="fb-q-text" t-esc="summary.question"/>
                                    <span t-att-class="'fb-q-badge ' + summary.type">
                                        <t t-if="summary.type === 'radio'">Single Choice</t>
                                        <t t-if="summary.type === 'checkbox'">Multi Choice</t>
                                        <t t-if="summary.type === 'text'">Open Text</t>
                                    </span>
                                </div>

                                <t t-if="summary.type === 'radio' || summary.type === 'checkbox'">
                                    <div class="fb-bars">
                                        <t t-foreach="summary.bars" t-as="bar" t-key="bar.label">
                                            <div class="fb-bar-row">
                                                <div class="fb-bar-label" t-esc="bar.label"/>
                                                <div class="fb-bar-track">
                                                    <div t-att-class="'fb-bar-fill ' + summary.type"
                                                         t-attf-style="width: {{bar.percent}}%"/>
                                                </div>
                                                <div class="fb-bar-count" t-esc="bar.count"/>
                                            </div>
                                        </t>
                                    </div>
                                    <div class="fb-note">Based on <t t-esc="summary.total"/> response(s)</div>
                                </t>

                                <t t-if="summary.type === 'text'">
                                    <t t-if="summary.texts.length > 0">
                                        <div class="fb-text-list">
                                            <t t-foreach="summary.texts" t-as="text" t-key="text_index">
                                                <div class="fb-text-item" t-esc="text"/>
                                            </t>
                                        </div>
                                    </t>
                                    <t t-if="summary.texts.length === 0">
                                        <p class="fb-no-text">No text responses submitted.</p>
                                    </t>
                                </t>
                            </div>
                        </t>
                    </div>
                </t>
            </t>
        </div>
    `;

    static props = {};

    setup() {
        this.orm = useService("orm");
        const savedTheme = localStorage.getItem('fb_dashboard_theme');
        this.state = useState({
            loading: true,
            darkMode: savedTheme ? savedTheme === 'dark' : true,
            employeeName: "",
            employeeInitial: "",
            sessions: [],
            selectedSessionId: null,
            selectedSessionName: "",
            summaries: [],
            totalResponses: 0,
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    toggleTheme() {
        this.state.darkMode = !this.state.darkMode;
        localStorage.setItem('fb_dashboard_theme', this.state.darkMode ? 'dark' : 'light');
    }

    async loadData() {
        const myEmployee = await this.orm.call(
            "pms.feedback.response",
            "get_my_employee_id",
            []
        );

        if (!myEmployee || !myEmployee.id) {
            this.state.loading = false;
            return;
        }

        this.state.employeeName = myEmployee.name;
        this.state.employeeInitial = myEmployee.name[0].toUpperCase();
        this.employeeId = myEmployee.id;

        const responses = await this.orm.searchRead(
            "pms.feedback.response",
            [
                ["state", "=", "submitted"],
                ["reviewee_employee_id", "=", myEmployee.id],
            ],
            ["id", "session_id", "answer_ids"],
        );

        const sessionMap = {};
        responses.forEach(r => {
            if (r.session_id) {
                sessionMap[r.session_id[0]] = { id: r.session_id[0], name: r.session_id[1] };
            }
        });
        this.state.sessions = Object.values(sessionMap);
        this.allResponses = responses;

        if (this.state.sessions.length > 0) {
            await this.selectSession(this.state.sessions[0].id);
        }

        this.state.loading = false;
    }

    async selectSession(sessionId) {
        this.state.selectedSessionId = sessionId;
        const session = this.state.sessions.find(s => s.id === sessionId);
        this.state.selectedSessionName = session ? session.name : "";

        const responses = this.allResponses.filter(
            r => r.session_id && r.session_id[0] === sessionId
        );
        this.state.totalResponses = responses.length;

        if (!responses.length) {
            this.state.summaries = [];
            return;
        }

        const allAnswerIds = responses.flatMap(r => r.answer_ids);
        if (!allAnswerIds.length) {
            this.state.summaries = [];
            return;
        }

        const answers = await this.orm.searchRead(
            "pms.feedback.answer",
            [["id", "in", allAnswerIds]],
            ["id", "question_id", "question_type", "radio_answer_id", "checkbox_answer_ids", "text_answer"],
        );

        const questionIds = [...new Set(answers.map(a => a.question_id[0]))];

        const questions = await this.orm.searchRead(
            "pms.feedback.question",
            [["id", "in", questionIds]],
            ["id", "question_text", "question_type", "sequence", "option_ids"],
            { order: "sequence asc" }
        );

        const allOptionIds = questions.flatMap(q => q.option_ids);
        const options = allOptionIds.length ? await this.orm.searchRead(
            "pms.feedback.question.option",
            [["id", "in", allOptionIds]],
            ["id", "option_text", "question_id", "sequence"],
            { order: "sequence asc" }
        ) : [];

        const answersByQuestion = {};
        answers.forEach(a => {
            const qid = a.question_id[0];
            if (!answersByQuestion[qid]) answersByQuestion[qid] = [];
            answersByQuestion[qid].push(a);
        });

        const summaries = [];
        questions.forEach(q => {
            const qAnswers = answersByQuestion[q.id] || [];
            if (!qAnswers.length) return;

            const qOptions = options.filter(o => o.question_id[0] === q.id);
            const summary = {
                question: q.question_text,
                type: q.question_type,
                total: qAnswers.length,
            };

            if (q.question_type === "radio") {
                const counts = {};
                qAnswers.forEach(a => {
                    if (a.radio_answer_id) {
                        const label = a.radio_answer_id[1];
                        counts[label] = (counts[label] || 0) + 1;
                    }
                });
                const maxCount = Math.max(...Object.values(counts), 1);
                summary.bars = qOptions.map(o => ({
                    label: o.option_text,
                    count: counts[o.option_text] || 0,
                    percent: Math.round(((counts[o.option_text] || 0) / maxCount) * 100),
                }));

            } else if (q.question_type === "checkbox") {
                const counts = {};
                qAnswers.forEach(a => {
                    (a.checkbox_answer_ids || []).forEach(optId => {
                        const opt = options.find(o => o.id === optId);
                        if (opt) counts[opt.option_text] = (counts[opt.option_text] || 0) + 1;
                    });
                });
                const maxCount = Math.max(...Object.values(counts), 1);
                summary.bars = qOptions.map(o => ({
                    label: o.option_text,
                    count: counts[o.option_text] || 0,
                    percent: Math.round(((counts[o.option_text] || 0) / maxCount) * 100),
                }));

            } else {
                summary.texts = qAnswers.map(a => a.text_answer).filter(Boolean);
            }

            summaries.push(summary);
        });

        this.state.summaries = summaries;
    }
}

registry.category("actions").add("pms_feedback_dashboard", FeedbackDashboard);