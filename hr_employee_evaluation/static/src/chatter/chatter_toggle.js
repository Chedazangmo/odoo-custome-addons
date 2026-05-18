/** @odoo-module **/

const PMS_SELECTORS = [
    ".o-mail-ChatterContainer",
    ".o_ChatterContainer", 
    ".o-mail-Chatter",
];

function pmsFindChatter() {
    for (const sel of PMS_SELECTORS) {
        const el = document.querySelector(sel);
        if (el) return el;
    }
    return null;
}

function pmsToggle(btn) {
    let backdrop = document.querySelector(".pms-chatter-backdrop");
    if (!backdrop) {
        backdrop = document.createElement("div");
        backdrop.className = "pms-chatter-backdrop";
        document.body.appendChild(backdrop);
    }

    const chatter = pmsFindChatter();
    if (!chatter) return;

    const isOpen = chatter.classList.toggle("pms-chatter-open");
    btn.classList.toggle("pms-chatter-active", isOpen);
    backdrop.classList.toggle("pms-chatter-backdrop-visible", isOpen);
}

function pmsClose() {
    const chatter = pmsFindChatter();
    const backdrop = document.querySelector(".pms-chatter-backdrop");
    const btn = document.querySelector(".pms-chatter-toggle-btn");
    
    if (chatter) chatter.classList.remove("pms-chatter-open");
    if (backdrop) backdrop.classList.remove("pms-chatter-backdrop-visible");
    if (btn) btn.classList.remove("pms-chatter-active");
}

document.addEventListener("click", (e) => {
    
    const toggleBtn = e.target.closest(".pms-chatter-toggle-btn");
    if (toggleBtn) {
        e.preventDefault();  // Stop default button behavior
        e.stopPropagation(); // Stop Odoo from interfering
        pmsToggle(toggleBtn);
        return;
    }
    
    if (e.target.closest(".pms-chatter-backdrop")) {
        e.preventDefault();
        e.stopPropagation();
        pmsClose();
    }
    
}, true); // true forces the event to bypass Odoo's framework blocks