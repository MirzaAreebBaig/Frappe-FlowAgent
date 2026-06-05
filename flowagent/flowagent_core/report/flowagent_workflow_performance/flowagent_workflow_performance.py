# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Per-workflow rollup of runs, durations, success rate, AI usage.

The "Is this workflow healthy?" report. Pulls FlowAgent Workflow Run
records in the filter window and groups by workflow. Includes a stacked
bar chart of Success vs Failed counts for the top 10 workflows.
"""
from __future__ import annotations

import frappe
from frappe import _


def execute(filters: dict | None = None):
    filters = filters or {}
    where, params = _build_where(filters)

    rows = frappe.db.sql(
        f"""
        SELECT
            workflow,
            COUNT(*)                                                 AS total_runs,
            SUM(CASE WHEN status = 'Success'           THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN status IN ('Failed','Timeout') THEN 1 ELSE 0 END) AS failed_count,
            ROUND(AVG(CASE WHEN status = 'Success' THEN duration_ms END), 0) AS avg_duration,
            MAX(duration_ms)                                         AS max_duration,
            COALESCE(SUM(ai_calls), 0)                               AS ai_calls_total,
            COALESCE(SUM(ai_tokens_in + ai_tokens_out), 0)           AS tokens_total,
            COALESCE(SUM(ai_cost_usd), 0)                            AS cost_total,
            MAX(creation)                                            AS last_run
        FROM `tabFlowAgent Workflow Run`
        WHERE {where}
        GROUP BY workflow
        ORDER BY total_runs DESC
        """,
        params,
        as_dict=True,
    )

    for r in rows:
        total = r.get("total_runs") or 0
        ok = r.get("success_count") or 0
        r["success_rate"] = round((ok / total * 100), 1) if total else 0
        r["avg_duration"] = int(r.get("avg_duration") or 0)
        r["max_duration"] = int(r.get("max_duration") or 0)
        r["cost_total"]   = float(r.get("cost_total") or 0)

    columns = [
        {"label": _("Workflow"),      "fieldname": "workflow",      "fieldtype": "Link",
         "options": "FlowAgent Workflow", "width": 240},
        {"label": _("Total Runs"),    "fieldname": "total_runs",    "fieldtype": "Int",      "width": 110},
        {"label": _("Success"),       "fieldname": "success_count", "fieldtype": "Int",      "width": 90},
        {"label": _("Failed"),        "fieldname": "failed_count",  "fieldtype": "Int",      "width": 90},
        {"label": _("Success %"),     "fieldname": "success_rate",  "fieldtype": "Percent",  "width": 105},
        {"label": _("Avg ms"),        "fieldname": "avg_duration",  "fieldtype": "Int",      "width": 100},
        {"label": _("Max ms"),        "fieldname": "max_duration",  "fieldtype": "Int",      "width": 100},
        {"label": _("AI Calls"),      "fieldname": "ai_calls_total","fieldtype": "Int",      "width": 90},
        {"label": _("Tokens"),        "fieldname": "tokens_total",  "fieldtype": "Int",      "width": 110},
        {"label": _("AI Cost (USD)"), "fieldname": "cost_total",    "fieldtype": "Currency",
         "options": "USD",            "width": 130},
        {"label": _("Last Run"),      "fieldname": "last_run",      "fieldtype": "Datetime", "width": 160},
    ]

    # Stacked bar of Success vs Failed for the top 10 workflows by volume.
    top = rows[:10]
    chart = None
    if top:
        chart = {
            "data": {
                "labels": [r["workflow"] for r in top],
                "datasets": [
                    {"name": _("Success"), "values": [r["success_count"] for r in top]},
                    {"name": _("Failed"),  "values": [r["failed_count"]  for r in top]},
                ],
            },
            "type": "bar",
            "colors": ["#10B981", "#EF4444"],
            "barOptions": {"stacked": 1},
            "axisOptions": {"xAxisMode": "tick"},
        }

    # Top-row summary cards above the chart
    total_runs = sum(r["total_runs"] for r in rows)
    total_ok   = sum(r["success_count"] for r in rows)
    total_fail = sum(r["failed_count"] for r in rows)
    total_cost = sum(r["cost_total"] for r in rows)
    summary = [
        {"value": total_runs, "label": _("Total Runs"),
         "indicator": "Blue", "datatype": "Int"},
        {"value": total_ok, "label": _("Successful"),
         "indicator": "Green", "datatype": "Int"},
        {"value": total_fail, "label": _("Failed"),
         "indicator": "Red", "datatype": "Int"},
        {"value": round(total_cost, 4), "label": _("AI Cost"),
         "indicator": "Purple", "datatype": "Currency",
         "currency": "USD"},
    ]

    return columns, rows, None, chart, summary


def _build_where(filters: dict) -> tuple[str, list]:
    """Compose a parameterised WHERE clause from the standard filter set."""
    conditions: list[str] = ["1=1"]
    params: list = []

    if filters.get("from_date"):
        conditions.append("creation >= %s")
        params.append(filters["from_date"])
    if filters.get("to_date"):
        # Push the right edge to end-of-day so the user's "to" is inclusive
        conditions.append("creation <= %s")
        params.append(str(filters["to_date"]) + " 23:59:59")
    if filters.get("workflow"):
        wf = filters["workflow"]
        if isinstance(wf, list):
            placeholders = ", ".join(["%s"] * len(wf))
            conditions.append(f"workflow IN ({placeholders})")
            params.extend(wf)
        else:
            conditions.append("workflow = %s")
            params.append(wf)
    return " AND ".join(conditions), params
