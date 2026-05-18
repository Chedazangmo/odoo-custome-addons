/** @odoo-module **/

import { Component, useState, onMounted, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const AVAILABLE_VARS = [
    { name: "score", icon: "ti-star", desc: "Appraisal score (0–100)" },
    { name: "eligibility", icon: "ti-percentage", desc: "Rating-tier eligibility as a ratio (0–1)" },
    { name: "base_salary", icon: "ti-wallet", desc: "Employee base salary" },
    { name: "years_service", icon: "ti-calendar", desc: "Employee tenure in years" },
    { name: "months_served", icon: "ti-calendar", desc: "Months served in current cycle (based on bonus date vs cycle start)" },
];

const OPERATORS = [
    { label: "+", val: "+", kind: "op", group: "basic" },
    { label: "-", val: "-", kind: "op", group: "basic" },
    { label: "×", val: "*", kind: "op", group: "basic" },
    { label: "÷", val: "/", kind: "op", group: "basic" },
    { label: "(", val: "(", kind: "op", group: "parentheses" },
    { label: ")", val: ")", kind: "op", group: "parentheses" },
    { label: "round", val: "round(", kind: "fn", group: "math" },
    { label: "min", val: "min(", kind: "fn", group: "math" },
    { label: "max", val: "max(", kind: "fn", group: "math" },
    { label: "abs", val: "abs(", kind: "fn", group: "math" },
    { label: "sqrt", val: "sqrt(", kind: "fn", group: "math" },
    { label: "pow", val: "pow(", kind: "fn", group: "math" },
];

const RATE_PRESETS = [
    { label: "5%", val: "0.05" }, { label: "10%", val: "0.10" }, { label: "15%", val: "0.15" },
    { label: "20%", val: "0.20" }, { label: "25%", val: "0.25" }, { label: "30%", val: "0.30" },
    { label: "50%", val: "0.50" }, { label: "75%", val: "0.75" }, { label: "100%", val: "1.00" },
];

const CONSTANT_PRESETS = [
    { label: "0", val: "0" }, { label: "1", val: "1" }, { label: "2", val: "2" }, { label: "100", val: "100" },
];

const SAFE_BUILTINS = {
    abs: Math.abs, round: Math.round, floor: Math.floor, ceil: Math.ceil,
    min: Math.min, max: Math.max, sqrt: Math.sqrt, pow: Math.pow, int: parseInt, float: parseFloat,
};

export class FormulaBuilderWidget extends Component {
    static template = "pms.FormulaBuilderWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");

        this.state = useState({
            tokens: [],
            customNum: "",
            validationStatus: null,
            validationMsg: "",
        });

        this.vars = AVAILABLE_VARS;
        this.basicOps = OPERATORS.filter(op => op.group === "basic");
        this.parenthesisOps = OPERATORS.filter(op => op.group === "parentheses");
        this.mathOps = OPERATORS.filter(op => op.group === "math");
        this.ratePresets = RATE_PRESETS;
        this.constantPresets = CONSTANT_PRESETS;

        onMounted(() => {
            const currentVal = this.props.record?.data[this.props.name];
            if (currentVal && currentVal.trim()) {
                this._loadFromString(currentVal.trim());
            }
        });

        onWillUpdateProps((nextProps) => {
            const newVal = nextProps.record?.data[nextProps.name];
            const currentExpr = this._getExprString();
            if (newVal !== currentExpr && newVal && newVal.trim()) {
                this._loadFromString(newVal.trim());
            }
        });
    }

    _loadFromString(expr) {
        if (!expr) {
            this.state.tokens = [];
            return;
        }
        
        const tokenPattern = /[a-zA-Z_][a-zA-Z0-9_]*|[\d.]+|[+\-*/()]/g;
        const parts = expr.match(tokenPattern) || [];
        
        const newTokens = [];
        for (let i = 0; i < parts.length; i++) {
            const p = parts[i];
            let kind = "op";
            let label = p;
            let val = p;
            
            const foundVar = AVAILABLE_VARS.find((v) => v.name === p);
            if (foundVar) {
                kind = "var";
                label = foundVar.name;
                val = foundVar.name;
            } else if (!isNaN(Number(p)) && p !== "") {
                kind = "num";
                label = p;
                val = p;
            } else if (OPERATORS.find(op => op.val === p && op.kind === "fn")) {
                kind = "fn";
                label = p;
                val = p;
            }
            
            newTokens.push({
                id: Date.now() + i + Math.random(),
                val: val,
                label: label,
                kind: kind,
            });
        }
        
        this.state.tokens = newTokens;
    }

    _getExprString() {
        if (!this.state || !this.state.tokens) return "";
        return this.state.tokens.map((t) => t.val).join(" ");
    }

    _pushToken(tok) {
        const newToken = { id: Date.now() + Math.random(), ...tok };
        this.state.tokens = [...this.state.tokens, newToken];
        this._syncField();
        this._clearValidation();
    }

    _syncField() {
        if (this.props.record && this.props.name) {
            this.props.record.update({ [this.props.name]: this._getExprString() });
        }
    }

    _clearValidation() {
        this.state.validationStatus = null;
        this.state.validationMsg = "";
    }

    onVarClick = (v) => {
        this._pushToken({ val: v.name, label: v.name, kind: "var" });
    }

    onOpClick = (op) => {
        this._pushToken({ val: op.val, label: op.label, kind: op.kind });
    }

    onPresetClick = (p) => {
        this._pushToken({ val: p.val, label: p.val, kind: "num" });
    }

    onConstantClick = (c) => {
        this._pushToken({ val: c.val, label: c.val, kind: "num" });
    }

    onAddNum = () => {
        const raw = this.state.customNum.trim();
        if (!raw || isNaN(Number(raw))) {
            this.notification.add("Please enter a valid number", { type: "warning" });
            return;
        }
        this._pushToken({ val: raw, label: raw, kind: "num" });
        this.state.customNum = "";
    }

    onNumKeydown = (ev) => {
        if (ev.key === "Enter") this.onAddNum();
    }

    onRemoveToken = (tokenId) => {
        const newTokens = this.state.tokens.filter(t => t.id !== tokenId);
        this.state.tokens = newTokens;
        this._syncField();
        this._clearValidation();
    }

    onClear = () => {
        this.state.tokens = [];
        this._syncField();
        this._clearValidation();
    }

    onCopy = () => {
        const expr = this._getExprString();
        if (!expr) {
            this.notification.add("Nothing to copy", { type: "warning" });
            return;
        }
        navigator.clipboard.writeText(expr);
        this.notification.add("Formula copied to clipboard", { type: "success" });
    }

    onValidate = async () => {
        const expr = this._getExprString();
        if (!expr) {
            this.state.validationStatus = "error";
            this.state.validationMsg = "Formula is empty. Add at least one variable or constant.";
            return;
        }

        const sample = { score: 85, eligibility: 0.75, base_salary: 50000, years_service: 5, months_served: 6 };

        try {
            const paramNames = [...Object.keys(sample), ...Object.keys(SAFE_BUILTINS)];
            const paramVals = [...Object.values(sample), ...Object.values(SAFE_BUILTINS)];
            
            const fn = new Function(...paramNames, `"use strict"; return (${expr});`);
            let result = fn(...paramVals);

            if (typeof result !== "number" || isNaN(result) || !isFinite(result)) {
                throw new Error("Formula must evaluate to a finite number.");
            }

            this.state.validationStatus = "ok";
            this.state.validationMsg = "Formula is valid! Ready to use in bonus calculations.";
            this.state.previewResult = {
                amount: result.toFixed(2),
                pct: ((result / sample.base_salary) * 100).toFixed(2),
                expr: expr
            };
            this.state.showPreview = true;
            this.notification.add(this.state.validationMsg, { type: "success" });
        } catch (e) {
            this.state.validationStatus = "error";
            this.state.validationMsg = e.message;
            this.state.showPreview = true;
            this.notification.add(this.state.validationMsg, { type: "danger" });
        }
    }
}

registry.category("fields").add("formula_builder", {
    component: FormulaBuilderWidget,
    supportedTypes: ["text", "char"],
    extractProps: ({ attrs }) => ({}),
});