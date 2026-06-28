# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
AI cost analysis — daily breakdown of token usage and estimated USD cost.

Two grouping modes via the `group_by` filter:
- "Day"      → one row per calendar day (default)
- "Workflow" → one row per workflow, totalled over the range
- "Day + Workflow" → row per (day, workflow) pair

The chart is always a daily cost trend regardless of grouping, since
that's the most actionable visual.
"""
from __future__ import annotations

import frappe
from frappe import _


def execute(filters: dict | None = None):
    filters = filters or {}
    where, params = _build_where(filters)
    group_by = filters.get("group_by") or "Day"

    if group_by == "Day":
        select_cols = "DATE(creation) AS bucket_date, NULL AS workflow"
        group_cols = "DATE(creation)"
        first_label = _("Date")
        first_field = "bucket_date"
        first_type = "Date"
    elif group_by == "Workflow":
        select_cols = "NULL AS bucket_date, workflow"
        group_cols = "workflow"
        first_label = _("Workflow")
        first_field = "workflow"
        first_type = "Link"
    else:  # "Day + Workflow"
        select_cols = "DATE(creation) AS bucket_date, workflow"
        group_cols = "DATE(creation), workflow"
        first_label = _("Date")
        first_field = "bucket_date"
        first_type = "Date"
    # SAFETY: This f-string composes a fixed-shape SQL query — only
    # the WHERE clause structure ("col >= %s AND status IN (%s, %s)")
    # is interpolated from a private _build_where helper that emits
    # only hardcoded condition strings with %s placeholders.
    # All user-supplied filter VALUES go through the `params` argument
    # and are properly escaped by frappe.db.sql. The interpolated
    # parts (group_cols, select_cols, where) never contain user input.

    rows = frappe.db.sql(  # nosemgrep: frappe-sql-format-injection
        f"""
        SELECT
            {select_cols},
            COUNT(*)                                       AS runs,
            COALESCE(SUM(ai_calls), 0)                     AS ai_calls,
            COALESCE(SUM(ai_tokens_in), 0)                 AS tokens_in,
            COALESCE(SUM(ai_tokens_out), 0)                AS tokens_out,
            COALESCE(SUM(ai_tokens_in + ai_tokens_out), 0) AS tokens_total,
            COALESCE(SUM(ai_cost_usd), 0)                  AS cost_total
        FROM `tabFlowAgent Workflow Run`
        WHERE {where}
        GROUP BY {group_cols}
        ORDER BY bucket_date DESC, workflow
        """,
        params,
        as_dict=True,
    )

    # Per-row derived metrics
    for r in rows:
        r["cost_total"] = float(r.get("cost_total") or 0)
        runs = r.get("runs") or 0
        r["avg_cost_per_run"] = round(r["cost_total"] / runs, 6) if runs else 0
        ai = r.get("ai_calls") or 0
        r["avg_cost_per_call"] = round(r["cost_total"] / ai, 6) if ai else 0

    # Filter to AI-bearing rows only when grouped by Workflow — a workflow
    # that never made AI calls would just be a row of zeros, not useful.
    if group_by == "Workflow":
        rows = [r for r in rows if r["ai_calls"] > 0]

    columns: list[dict] = [
        {"label": first_label, "fieldname": first_field, "fieldtype": first_type,
         "options": "FlowAgent Workflow" if first_field == "workflow" else None,
         "width": 160 if first_field == "bucket_date" else 220},
    ]
    if group_by == "Day + Workflow":
        columns.append({"label": _("Workflow"), "fieldname": "workflow",
                        "fieldtype": "Link", "options": "FlowAgent Workflow", "width": 220})

    columns.extend([
        {"label": _("Runs"),         "fieldname": "runs",         "fieldtype": "Int", "width": 90},
        {"label": _("AI Calls"),     "fieldname": "ai_calls",     "fieldtype": "Int", "width": 90},
        {"label": _("Tokens In"),    "fieldname": "tokens_in",    "fieldtype": "Int", "width": 110},
        {"label": _("Tokens Out"),   "fieldname": "tokens_out",   "fieldtype": "Int", "width": 110},
        {"label": _("Tokens Total"), "fieldname": "tokens_total", "fieldtype": "Int", "width": 120},
        {"label": _("Cost (USD)"),   "fieldname": "cost_total",   "fieldtype": "Currency",
         "options": "USD",           "width": 130},
        {"label": _("Cost/Run"),     "fieldname": "avg_cost_per_run", "fieldtype": "Currency",
         "options": "USD",           "width": 120},
        {"label": _("Cost/Call"),    "fieldname": "avg_cost_per_call", "fieldtype": "Currency",
         "options": "USD",           "width": 120},
    ])

    # Daily cost trend — query independently so it works regardless of
    # the table's group_by mode. Sorted oldest → newest for a left→right
    # left-to-right line chart.
    # SAFETY: This f-string composes a fixed-shape SQL query — only
    # the WHERE clause structure ("col >= %s AND status IN (%s, %s)")
    # is interpolated from a private _build_where helper that emits
    # only hardcoded condition strings with %s placeholders.
    # All user-supplied filter VALUES go through the `params` argument
    # and are properly escaped by frappe.db.sql. The interpolated
    # parts (group_cols, select_cols, where) never contain user input.
    daily = frappe.db.sql(  # nosemgrep: frappe-sql-format-injection
        f"""
        SELECT DATE(creation) AS d, COALESCE(SUM(ai_cost_usd), 0) AS cost
        FROM `tabFlowAgent Workflow Run`
        WHERE {where}
        GROUP BY DATE(creation)
        ORDER BY DATE(creation) ASC
        """,
        params,
        as_dict=True,
    )

    chart = None
    if daily:
        chart = {
            "data": {
                "labels":   [str(d["d"]) for d in daily],
                "datasets": [
                    {"name": _("Cost (USD)"), "values": [float(d["cost"] or 0) for d in daily]},
                ],
            },
            "type": "line",
            "colors": ["#A855F7"],
            "lineOptions": {"regionFill": 1, "hideDots": 0, "spline": 1},
            "axisOptions": {"xIsSeries": 1},
        }

    summary = [
        {"value": sum(r["runs"]         for r in rows), "label": _("Runs"),
         "indicator": "Blue", "datatype": "Int"},
        {"value": sum(r["ai_calls"]     for r in rows), "label": _("AI Calls"),
         "indicator": "Blue", "datatype": "Int"},
        {"value": sum(r["tokens_total"] for r in rows), "label": _("Tokens"),
         "indicator": "Blue", "datatype": "Int"},
        {"value": round(sum(r["cost_total"] for r in rows), 4), "label": _("Total Cost"),
         "indicator": "Purple", "datatype": "Currency", "currency": "USD"},
    ]

    return columns, rows, None, chart, summary


def _build_where(filters: dict) -> tuple[str, list]:
    conditions: list[str] = ["1=1"]
    params: list = []

    if filters.get("from_date"):
        conditions.append("creation >= %s")
        params.append(filters["from_date"])
    if filters.get("to_date"):
        conditions.append("creation <= %s")
        params.append(str(filters["to_date"]) + " 23:59:59")
    if filters.get("workflow"):
        conditions.append("workflow = %s")
        params.append(filters["workflow"])
    if filters.get("only_with_cost"):
        conditions.append("ai_cost_usd > 0")
    return " AND ".join(conditions), params
