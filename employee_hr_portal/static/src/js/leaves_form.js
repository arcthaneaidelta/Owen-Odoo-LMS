/** @odoo-module **/

const jsonRpc = (url, params) =>
    fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
    })
        .then((r) => r.json())
        .then((r) => r.result);

const qs = (selector) => document.querySelector(selector);

function handleLeaveType() {
    const leaveType = qs("#leave_types");
    if (!leaveType) return;
    const selected = leaveType.options[leaveType.selectedIndex];
    const requestUnit = selected ? selected.dataset.request_unit : null;
    const hoursCheckbox = qs("#request_unit_hours");
    const hoursLabel = qs("label[for='request_unit_hours']");
    const hourDates = qs("#hour_dates");

    if (requestUnit === "hour") {
        hoursCheckbox && (hoursCheckbox.style.display = "");
        hoursLabel && (hoursLabel.style.display = "");
    } else {
        if (hoursCheckbox) {
            hoursCheckbox.checked = false;
            hoursCheckbox.style.display = "none";
        }
        hoursLabel && (hoursLabel.style.display = "none");
        hourDates && hourDates.classList.add("d-none");
    }
}

function handleNumberOfDays() {
    let request_unit_half = false;
    let request_unit_hours = false;
    let request_hour_from, request_hour_to, request_date_from_period;

    const date_from = qs("#date_from")?.value;
    const date_to = qs("#date_to")?.value;
    const leave_types = qs("#leave_types")?.value;
    const request_date_from = qs("#request_date_from")?.value;
    const request_date_to = qs("#request_date_to")?.value;

    if (qs("#request_unit_half")?.checked) {
        request_unit_half = true;
        request_unit_hours = false;
        const ruh = qs("#request_unit_hours");
        if (ruh) ruh.checked = false;
        request_date_from_period = qs("#request_date_from_period")?.value;
    }

    if (qs("#request_unit_hours")?.checked) {
        request_unit_hours = true;
        request_unit_half = false;
        const ruh = qs("#request_unit_half");
        if (ruh) ruh.checked = false;
        request_hour_from = qs("#request_hour_from")?.value;
        request_hour_to = qs("#request_hour_to")?.value;
    }

    jsonRpc("/leave/number_of_days", {
        date_from,
        date_to,
        request_date_from,
        request_unit_half,
        request_unit_hours,
        request_date_to,
        request_date_from_period,
        request_hour_from,
        request_hour_to,
        leave_types,
    }).then((vals) => {
        if (!vals) return;

        if ("number_of_days" in vals) {
            const nd = vals.number_of_days;
            if ("days" in nd || "hours" in nd) {
                const label = qs("label[for='number_of_days']");
                const ndInput = qs("#number_of_days");
                const ndSpan = qs("#number_of_days_span");
                // ✅ null-check each element individually before setting
                if (label) label.textContent = "Duration (Days)*";
                if (ndInput) ndInput.value = nd.days ?? "";
                if (ndSpan) ndSpan.textContent = nd.hours ?? "";
            }
        }

        const dfEl = qs("#date_from");
        const dtEl = qs("#date_to");
        if (dfEl) dfEl.value = vals.date_from ?? "";
        if (dtEl) dtEl.value = vals.date_to ?? "";

        if ("support_document" in vals) {
            const attachForm = qs("#attachment_id_form");
            const ufile = qs("input[name='ufile']");
            if (vals.support_document) {
                attachForm?.classList.remove("d-none");
                if (ufile) ufile.required = true;
            } else {
                attachForm?.classList.add("d-none");
                if (ufile) ufile.required = false;
            }
        }
    });
}

function handleRequestUnitHalf() {
    const half = qs("#request_unit_half");
    if (!half) return;
    if (half.checked) {
        qs("#request_date_to")?.classList.add("d-none");
        qs("#request_date_to")?.removeAttribute("required");
        qs("#request_date_from_period")?.classList.remove("d-none");
        qs("#request_date_from_period")?.setAttribute("required", "required");
        qs("#to")?.classList.remove("d-none");
        qs("#request_date_from")?.classList.remove("col-md-9", "col-sm-9");
        qs("#request_date_from")?.classList.add("col-md-4", "col-sm-4");
        qs("#hour_dates")?.classList.add("d-none");
        const ruh = qs("#request_unit_hours");
        if (ruh) ruh.checked = false;
    } else {
        qs("#request_date_to")?.classList.remove("d-none");
        qs("#request_date_from_period")?.classList.add("d-none");
        qs("#request_date_from_period")?.removeAttribute("required");
        qs("#request_date_to")?.setAttribute("required", "required");
    }
}

function handleRequestUnitHours() {
    const hours = qs("#request_unit_hours");
    if (!hours) return;
    if (hours.checked) {
        qs("#request_date_from")?.classList.add("col-md-9", "col-sm-9");
        qs("#request_date_from")?.classList.remove("col-md-4", "col-sm-4");
        qs("#to")?.classList.add("d-none");
        qs("#request_date_to")?.classList.add("d-none");
        qs("#request_date_from_period")?.classList.add("d-none");
        qs("#hour_dates")?.classList.remove("d-none");
        qs("#request_hour_from")?.setAttribute("required", "required");
        qs("#request_hour_to")?.setAttribute("required", "required");
        const ruhalf = qs("#request_unit_half");
        if (ruhalf) ruhalf.checked = false;
    } else {
        qs("#to")?.classList.remove("d-none");
        if (!qs("#request_unit_half")?.checked) {
            qs("#request_date_to")?.classList.remove("d-none");
        }
        qs("#hour_dates")?.classList.add("d-none");
        qs("#request_date_from")?.classList.remove("col-md-9", "col-sm-9");
        qs("#request_date_from")?.classList.add("col-md-4", "col-sm-4");
        qs("#request_hour_from")?.removeAttribute("required");
        qs("#request_hour_to")?.removeAttribute("required");
    }
}

function initLeavesForm() {
    if (!qs("#leave_types")) return;  // 👈 Exit early if not on leave form

    handleLeaveType();
    handleRequestUnitHalf();
    handleRequestUnitHours();
    handleNumberOfDays();

    qs("#leave_types")?.addEventListener("change", () => {
        handleLeaveType();
        handleRequestUnitHalf();
        handleRequestUnitHours();
        handleNumberOfDays();
    });

    qs("#request_unit_half")?.addEventListener("change", () => {
        const val = qs("#request_date_from")?.value;
        if (qs("#request_date_to")) qs("#request_date_to").value = val ?? "";
        handleRequestUnitHalf();
        handleNumberOfDays();
    });

    qs("#request_unit_hours")?.addEventListener("change", () => {
        const val = qs("#request_date_from")?.value;
        if (qs("#request_date_to")) qs("#request_date_to").value = val ?? "";
        handleRequestUnitHours();
        handleNumberOfDays();
    });

    qs("#request_date_from")?.addEventListener("change", () => {
        const val = qs("#request_date_from")?.value;
        if (qs("#request_date_to")) qs("#request_date_to").value = val ?? "";
        handleNumberOfDays();
    });

    qs("#request_date_to")?.addEventListener("change", handleNumberOfDays);
    qs("#request_date_from_period")?.addEventListener("change", handleNumberOfDays);
    qs("#request_hour_from")?.addEventListener("change", handleNumberOfDays);
    qs("#request_hour_to")?.addEventListener("change", handleNumberOfDays);

    qs("#reset_confirm")?.addEventListener("click", (e) => {
        e.preventDefault();
        const form = e.target.closest("form");
        const input = document.createElement("input");
        input.type = "text";
        input.name = "confirm";
        input.value = "true";
        form.appendChild(input);
        form.submit();
    });
}

// ✅ KEY FIX: Odoo modules load asynchronously, so DOMContentLoaded might have already passed
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLeavesForm);
} else {
    initLeavesForm();
}