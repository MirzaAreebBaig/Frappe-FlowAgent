# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Chronological run history. The "what happened?" report.

Pulls FlowAgent Workflow Run records with their key fields, sortable
and filterable. First line of any error message shows in the row.
"""
from __future__ import annotations

import frappe
from frappe import _


def execute(filters: dict | None = None):
    filters = filters or {}
    where, params = _build_where(filters)
    limit = int(filters.get("limit") or 500)

    rows = frappe.db.sql(
        f"""
        SELECT
            name,
            workflow,
            status,
            trigger_source,
            started_at,
            ended_at,
            duration_ms,
            ai_calls,
            ai_tokens_in,
            ai_tokens_out,
            ai_cost_usd,
            SUBSTRING_INDEX(COALESCE(error_message, ''), '\n', 1) AS error_first_line
        FROM `tabFlowAgent Workflow Run`
        WHERE {where}
        ORDER BY creation DESC
        LIMIT %s
        """,
        params + [limit],
        as_dict=True,
    )

    for r in rows:
        r["tokens_total"] = (r.get("ai_tokens_in") or 0) + (r.get("ai_tokens_out") or 0)
        r["ai_cost_usd"]  = float(r.get("ai_cost_usd") or 0)

    columns = [
        {"label": _("Run"),         "fieldname": "name",            "fieldtype": "Link",
         "options": "FlowAgent Workflow Run", "width": 220},
        {"label": _("Workflow"),    "fieldname": "workflow",        "fieldtype": "Link",
         "options": "FlowAgent Workflow", "width": 200},
        {"label": _("Status"),      "fieldname": "status",          "fieldtype": "Data",     "width": 90},
        {"label": _("Trigger"),     "fieldname": "trigger_source",  "fieldtype": "Data",     "width": 130},
        {"label": _("Started At"),  "fieldname": "started_at",      "fieldtype": "Datetime", "width": 160},
        {"label": _("Duration ms"), "fieldname": "duration_ms",     "fieldtype": "Int",      "width": 110},
        {"label": _("AI Calls"),    "fieldname": "ai_calls",        "fieldtype": "Int",      "width": 80},
        {"label": _("Tokens"),      "fieldname": "tokens_total",    "fieldtype": "Int",      "width": 100},
        {"label": _("AI Cost"),     "fieldname": "ai_cost_usd",     "fieldtype": "Currency",
         "options": "USD",          "width": 110},
        {"label": _("Error"),       "fieldname": "error_first_line","fieldtype": "Data",     "width": 320},
    ]

    # Donut of the status distribution within the result set
    chart = None
    if rows:
        status_counts: dict[str, int] = {}
        for r in rows:
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        # Stable colour map by status
        colour_for = {
            "Success":   "#10B981",
            "Failed":    "#EF4444",
            "Timeout":   "#F97316",
            "Running":   "#6366F1",
            "Queued":    "#94A3B8",
            "Cancelled": "#A1A1AA",
        }
        labels = list(status_counts.keys())
        chart = {
            "data": {
                "labels": labels,
                "datasets": [{"values": [status_counts[s] for s in labels]}],
            },
            "type": "donut",
            "colors": [colour_for.get(s, "#6B7280") for s in labels],
            "height": 240,
        }

    summary = [
        {"value": len(rows),                                          "label": _("Runs"),
         "indicator": "Blue", "datatype": "Int"},
        {"value": sum(1 for r in rows if r["status"] == "Success"),   "label": _("Success"),
         "indicator": "Green", "datatype": "Int"},
        {"value": sum(1 for r in rows if r["status"] in ("Failed", "Timeout")),
         "label": _("Failed"), "indicator": "Red", "datatype": "Int"},
        {"value": round(sum(r["ai_cost_usd"] for r in rows), 4),
         "label": _("AI Cost"), "indicator": "Purple", "datatype": "Currency", "currency": "USD"},
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
    if filters.get("status"):
        st = filters["status"]
        if isinstance(st, list):
            ph = ", ".join(["%s"] * len(st))
            conditions.append(f"status IN ({ph})")
            params.extend(st)
        else:
            conditions.append("status = %s")
            params.append(st)
    if filters.get("trigger_source"):
        # LIKE so the user can match "webhook:" or "schedule" loosely
        conditions.append("trigger_source LIKE %s")
        params.append(f"%{filters['trigger_source']}%")
    if filters.get("has_error"):
        conditions.append("error_message IS NOT NULL AND error_message != ''")

    return " AND ".join(conditions), params
