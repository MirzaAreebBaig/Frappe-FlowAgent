# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Top error messages grouped across runs.

We can pull errors from two places:
- Run-level (`error_message` on the parent doc)  — fatal errors
- Step-level (`error` on the child step rows)     — caught per-node errors

This report combines both. The first line of each error is treated as
the message identity (full message lives in the row's tooltip / detail).
"""
from __future__ import annotations

import frappe
from frappe import _


def execute(filters: dict | None = None):
    filters = filters or {}
    where_parent, params_p = _build_parent_where(filters)

    # Group by the FIRST LINE of error_message so wildly-different
    # stack traces with the same headline collapse into one row.
    rows = frappe.db.sql(
        f"""
        SELECT
            r.workflow                                        AS workflow,
            COALESCE(s.node_label, s.node_type, '(run-level)') AS node_label,
            SUBSTRING_INDEX(
                COALESCE(NULLIF(s.error, ''), r.error_message),
                '\n', 1
            )                                                  AS error_first_line,
            COUNT(*)                                           AS occurrences,
            MIN(r.creation)                                    AS first_seen,
            MAX(r.creation)                                    AS last_seen
        FROM `tabFlowAgent Workflow Run` AS r
        LEFT JOIN `tabFlowAgent Workflow Run Step` AS s
            ON s.parent = r.name AND s.error IS NOT NULL AND s.error != ''
        WHERE {where_parent}
          AND (
            (r.error_message IS NOT NULL AND r.error_message != '')
            OR (s.error IS NOT NULL AND s.error != '')
          )
        GROUP BY r.workflow, node_label, error_first_line
        ORDER BY occurrences DESC, last_seen DESC
        LIMIT 100
        """,
        params_p,
        as_dict=True,
    )

    columns = [
        {"label": _("Workflow"),    "fieldname": "workflow",          "fieldtype": "Link",
         "options": "FlowAgent Workflow", "width": 220},
        {"label": _("Node"),        "fieldname": "node_label",        "fieldtype": "Data",     "width": 200},
        {"label": _("Error"),       "fieldname": "error_first_line",  "fieldtype": "Data",     "width": 420},
        {"label": _("Occurrences"), "fieldname": "occurrences",       "fieldtype": "Int",      "width": 110},
        {"label": _("First Seen"),  "fieldname": "first_seen",        "fieldtype": "Datetime", "width": 160},
        {"label": _("Last Seen"),   "fieldname": "last_seen",         "fieldtype": "Datetime", "width": 160},
    ]

    # Top 10 errors by frequency — horizontal bar so long messages
    # fit somewhat readably. (Frappe Charts doesn't have a true
    # horizontal bar, so we use a vertical bar with truncated labels.)
    top = rows[:10]
    chart = None
    if top:
        chart = {
            "data": {
                "labels": [
                    (r["error_first_line"] or "")[:60] + ("…" if len(r["error_first_line"] or "") > 60 else "")
                    for r in top
                ],
                "datasets": [
                    {"name": _("Occurrences"), "values": [r["occurrences"] for r in top]},
                ],
            },
            "type": "bar",
            "colors": ["#EF4444"],
            "axisOptions": {"xAxisMode": "tick"},
        }

    summary = [
        {"value": sum(r["occurrences"] for r in rows),
         "label": _("Total Errors"), "indicator": "Red", "datatype": "Int"},
        {"value": len(rows),
         "label": _("Distinct Errors"), "indicator": "Orange", "datatype": "Int"},
        {"value": len({r["workflow"] for r in rows}),
         "label": _("Affected Workflows"), "indicator": "Blue", "datatype": "Int"},
    ]

    return columns, rows, None, chart, summary


def _build_parent_where(filters: dict) -> tuple[str, list]:
    conditions: list[str] = ["1=1"]
    params: list = []
    if filters.get("from_date"):
        conditions.append("r.creation >= %s")
        params.append(filters["from_date"])
    if filters.get("to_date"):
        conditions.append("r.creation <= %s")
        params.append(str(filters["to_date"]) + " 23:59:59")
    if filters.get("workflow"):
        conditions.append("r.workflow = %s")
        params.append(filters["workflow"])
    return " AND ".join(conditions), params
