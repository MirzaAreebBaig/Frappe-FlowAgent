# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Slowest nodes across all runs in a window.

Queries the Workflow Run Step child table joined to its parent run for
the date filter. Returns rolled-up metrics per (workflow, node) so the
user can answer "which step is my bottleneck?"
"""
from __future__ import annotations

import frappe
from frappe import _


def execute(filters: dict | None = None):
    filters = filters or {}
    where_parent, params = _build_parent_where(filters)
    where_step = ["1=1"]
    if filters.get("node_type"):
        where_step.append("s.node_type = %s")
        params.append(filters["node_type"])
    if filters.get("status"):
        where_step.append("s.status = %s")
        params.append(filters["status"])
    where_step_sql = " AND ".join(where_step)
    # SAFETY: This f-string composes a fixed-shape SQL query — only
    # the WHERE clause structure ("col >= %s AND status IN (%s, %s)")
    # is interpolated from a private _build_where helper that emits
    # only hardcoded condition strings with %s placeholders.
    # All user-supplied filter VALUES go through the `params` argument
    # and are properly escaped by frappe.db.sql. The interpolated
    # parts (group_cols, select_cols, where) never contain user input.

    rows = frappe.db.sql(
        # nosemgrep: frappe-sql-format-injection
        f"""
        SELECT
            r.workflow                                       AS workflow,
            s.node_id                                        AS node_id,
            COALESCE(s.node_label, s.node_type)              AS node_label,
            s.node_type                                      AS node_type,
            COUNT(*)                                         AS executions,
            ROUND(AVG(s.duration_ms), 0)                     AS avg_ms,
            MAX(s.duration_ms)                               AS max_ms,
            MIN(s.duration_ms)                               AS min_ms,
            SUM(CASE WHEN s.status = 'Failed' THEN 1 ELSE 0 END) AS failures
        FROM `tabFlowAgent Workflow Run Step` AS s
        INNER JOIN `tabFlowAgent Workflow Run` AS r
            ON s.parent = r.name
        WHERE {where_parent} AND {where_step_sql}
        GROUP BY r.workflow, s.node_id, s.node_label, s.node_type
        HAVING AVG(s.duration_ms) > 0
        ORDER BY avg_ms DESC
        LIMIT 100
        """,
        params,
        as_dict=True,
    )

    for r in rows:
        r["avg_ms"] = int(r.get("avg_ms") or 0)
        r["max_ms"] = int(r.get("max_ms") or 0)
        r["min_ms"] = int(r.get("min_ms") or 0)

    columns = [
        {"label": _("Workflow"),  "fieldname": "workflow",   "fieldtype": "Link",
         "options": "FlowAgent Workflow", "width": 220},
        {"label": _("Node"),      "fieldname": "node_label", "fieldtype": "Data",     "width": 200},
        {"label": _("Type"),      "fieldname": "node_type",  "fieldtype": "Data",     "width": 140},
        {"label": _("Executions"),"fieldname": "executions", "fieldtype": "Int",      "width": 110},
        {"label": _("Avg ms"),    "fieldname": "avg_ms",     "fieldtype": "Int",      "width": 100},
        {"label": _("Max ms"),    "fieldname": "max_ms",     "fieldtype": "Int",      "width": 100},
        {"label": _("Min ms"),    "fieldname": "min_ms",     "fieldtype": "Int",      "width": 100},
        {"label": _("Failures"),  "fieldname": "failures",   "fieldtype": "Int",      "width": 100},
    ]

    # Bar chart: top 12 slowest. Each label is "WorkflowName › NodeLabel" so
    # there's enough context to recognise rows even when they're tightly
    # packed.
    top = rows[:12]
    chart = None
    if top:
        chart = {
            "data": {
                "labels": [f"{r['workflow']} › {r['node_label']}" for r in top],
                "datasets": [
                    {"name": _("Avg ms"), "values": [r["avg_ms"] for r in top]},
                    {"name": _("Max ms"), "values": [r["max_ms"] for r in top]},
                ],
            },
            "type": "bar",
            "colors": ["#6366F1", "#F59E0B"],
            "axisOptions": {"xAxisMode": "tick"},
        }

    summary = [
        {"value": len(rows), "label": _("Distinct Nodes"),
         "indicator": "Blue", "datatype": "Int"},
        {"value": (rows[0]["avg_ms"] if rows else 0),
         "label": _("Slowest Avg (ms)"), "indicator": "Orange", "datatype": "Int"},
        {"value": (rows[0]["max_ms"] if rows else 0),
         "label": _("Worst Max (ms)"),   "indicator": "Red",    "datatype": "Int"},
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
