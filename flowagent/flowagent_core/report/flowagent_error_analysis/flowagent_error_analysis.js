// Copyright (c) 2026, FlowAgent and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["FlowAgent Error Analysis"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
            reqd: 1,
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: "workflow",
            label: __("Workflow"),
            fieldtype: "Link",
            options: "FlowAgent Workflow",
        },
    ],

    formatter: function (value, row, column, data, default_formatter) {
        const v = default_formatter(value, row, column, data);
        if (column.fieldname === "error_first_line" && value) {
            return `<span style="color:#B91C1C">${v}</span>`;
        }
        if (column.fieldname === "occurrences" && data) {
            const c = data.occurrences > 10 ? "#B91C1C" : data.occurrences > 3 ? "#B45309" : "inherit";
            return `<span style="color:${c};font-weight:600">${v}</span>`;
        }
        return v;
    },
};
