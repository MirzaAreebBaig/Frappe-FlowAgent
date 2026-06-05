// Copyright (c) 2026, FlowAgent and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["FlowAgent Workflow Performance"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
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

    // Colour the Success % cell so the user can scan failing workflows fast.
    formatter: function (value, row, column, data, default_formatter) {
        const v = default_formatter(value, row, column, data);
        if (column.fieldname === "success_rate" && data) {
            const pct = data.success_rate || 0;
            let color = "#10B981";          // green
            if (pct < 99) color = "#F59E0B"; // amber
            if (pct < 90) color = "#EF4444"; // red
            return `<span style="color:${color};font-weight:600">${v}</span>`;
        }
        if (column.fieldname === "failed_count" && data && data.failed_count > 0) {
            return `<span style="color:#EF4444;font-weight:500">${v}</span>`;
        }
        return v;
    },
};
