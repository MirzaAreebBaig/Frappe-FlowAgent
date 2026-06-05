// Copyright (c) 2026, FlowAgent and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["FlowAgent AI Cost Analysis"] = {
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
        {
            fieldname: "group_by",
            label: __("Group By"),
            fieldtype: "Select",
            options: ["Day", "Workflow", "Day + Workflow"].join("\n"),
            default: "Day",
        },
        {
            fieldname: "only_with_cost",
            label: __("Only runs with AI cost"),
            fieldtype: "Check",
            default: 0,
            description: __("Hide rows with $0 — useful when most runs don't use AI"),
        },
    ],
};
