// Copyright (c) 2026, FlowAgent and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["FlowAgent Slowest Nodes"] = {
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
            fieldname: "node_type",
            label: __("Node Type"),
            fieldtype: "Data",
            description: __("Exact node type, e.g. 'ai_llm' or 'int_http'"),
        },
        {
            fieldname: "status",
            label: __("Step Status"),
            fieldtype: "Select",
            options: ["", "Success", "Failed", "Skipped"].join("\n"),
        },
    ],
};
