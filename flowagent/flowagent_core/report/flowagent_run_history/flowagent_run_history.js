// Copyright (c) 2026, FlowAgent and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["FlowAgent Run History"] = {
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
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: ["", "Queued", "Running", "Success", "Failed", "Timeout", "Cancelled"].join("\n"),
        },
        {
            fieldname: "trigger_source",
            label: __("Trigger contains"),
            fieldtype: "Data",
            description: __("Filter by trigger source substring (e.g. 'webhook' or 'studio')"),
        },
        {
            fieldname: "has_error",
            label: __("Only with errors"),
            fieldtype: "Check",
            default: 0,
        },
        {
            fieldname: "limit",
            label: __("Limit"),
            fieldtype: "Int",
            default: 500,
        },
    ],

    formatter: function (value, row, column, data, default_formatter) {
        const v = default_formatter(value, row, column, data);
        if (column.fieldname === "status" && data) {
            const colours = {
                Success: "#10B981", Failed: "#EF4444", Timeout: "#F97316",
                Running: "#6366F1", Queued: "#94A3B8", Cancelled: "#A1A1AA",
            };
            const c = colours[data.status] || "#6B7280";
            return `<span style="color:${c};font-weight:600">${data.status}</span>`;
        }
        if (column.fieldname === "error_first_line" && value) {
            return `<span style="color:#B91C1C">${v}</span>`;
        }
        return v;
    },
};
