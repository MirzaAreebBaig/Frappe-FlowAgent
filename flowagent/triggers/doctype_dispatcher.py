# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
DocType event → workflow dispatch.

This module is wired via the `doc_events` wildcard in hooks.py. Every
single doctype save/submit/cancel/etc. flows through `on_event`. To stay
cheap, the dispatcher does an indexed lookup against the
`FlowAgent Workflow Trigger Index` table (which is maintained whenever
a workflow is saved) and bails out immediately if nothing matches.

Verbose mode (controlled by FlowAgent Settings.verbose_logging) writes
every fire/no-fire decision to Frappe's error log so you can tail
`bench logs` and watch dispatch behaviour in real time when debugging.
"""

from __future__ import annotations

import frappe


# Map Frappe's lifecycle hook names to our friendlier event labels.
_EVENT_MAP = {
    "after_insert": "After Insert",
    "on_update": "After Save",
    "on_submit": "After Submit",
    "on_cancel": "After Cancel",
    "on_trash": "After Delete",
    "on_change": "On Change",
}


def on_event(doc, method=None):
    """Wildcard doc_events handler.

    Called for every doctype event. We do the cheapest possible filter
    here — if no workflow listens for this (doctype, event) pair, return
    in <1ms.
    """
    event = _EVENT_MAP.get(method)
    if not event:
        return

    # Skip our own doctypes to avoid feedback loops (a workflow run
    # creating Workflow Run docs could otherwise re-trigger workflows).
    if doc.doctype.startswith("FlowAgent ") or doc.doctype == "FlowAgent Settings":
        return

    # Cheap index lookup. We use frappe.db.get_all explicitly (not
    # frappe.get_all) because the latter applies permission filters that
    # could hide rows when triggered as Administrator from a webhook.
    try:
        workflows = frappe.db.get_all(
            "FlowAgent Workflow Trigger Index",
            filters={"trigger_doctype": doc.doctype, "trigger_event": event},
            pluck="workflow",
        )
    except Exception as e:
        # Index table may not exist yet during initial migration. Don't
        # blow up the user's save — log and skip.
        frappe.log_error(
            title="FlowAgent: trigger index lookup failed",
            message=f"{type(e).__name__}: {e}\nDocType: {doc.doctype}\nEvent: {event}",
        )
        return

    if not workflows:
        if _verbose():
            frappe.logger("flowagent").debug(
                f"[FlowAgent] No workflows for {doc.doctype}/{event}"
            )
        return

    if _verbose():
        frappe.logger("flowagent").info(
            f"[FlowAgent] {doc.doctype}/{event} → {len(workflows)} workflow(s): {workflows}"
        )

    for wf_name in workflows:
        try:
            _dispatch_one(wf_name, doc, event)
        except Exception as e:
            # One workflow's failure must not block others on the same event
            frappe.log_error(
                title=f"FlowAgent: dispatch failed for {wf_name}",
                message=f"{type(e).__name__}: {e}\nDocType: {doc.doctype}\nEvent: {event}",
            )


def _dispatch_one(wf_name: str, doc, event: str):
    """Enqueue (or inline-run) a workflow for this doc event."""
    # Direct DB read — bypass any cached doc so we always see the latest
    # `enabled` and `trigger_condition` state.
    wf_row = frappe.db.get_value(
        "FlowAgent Workflow",
        wf_name,
        ["enabled", "trigger_condition"],
        as_dict=True,
    )
    if not wf_row:
        return
    if not wf_row.enabled:
        if _verbose():
            frappe.logger("flowagent").info(
                f"[FlowAgent] {wf_name} indexed but not enabled — skipping"
            )
        return

    if wf_row.trigger_condition:
        try:
            if not _eval_condition(wf_row.trigger_condition, doc):
                if _verbose():
                    frappe.logger("flowagent").info(
                        f"[FlowAgent] {wf_name} condition rejected this doc"
                    )
                return
        except Exception as e:
            frappe.log_error(
                title=f"FlowAgent: trigger condition error on {wf_name}",
                message=f"{type(e).__name__}: {e}\n\nCondition:\n{wf_row.trigger_condition}",
            )
            return

    payload = _build_payload(doc, event)
    user = frappe.session.user or "Administrator"

    # Try the background queue first; fall back to inline if Redis is
    # unavailable. Inline is slower but at least the workflow runs.
    try:
        frappe.enqueue(
            "flowagent.engine.run_workflow_background",
            queue="default",
            timeout=600,
            workflow_name=wf_name,
            trigger_source=f"doctype:{doc.doctype}/{event}",
            payload=payload,
            user=user,
        )
        if _verbose():
            frappe.logger("flowagent").info(
                f"[FlowAgent] ENQUEUED {wf_name} for {doc.doctype}/{doc.name}"
            )
    except Exception as e:
        frappe.log_error(
            title=f"FlowAgent: enqueue failed for {wf_name} — running inline",
            message=f"{type(e).__name__}: {e}",
        )
        # Inline fallback. We swallow any exception so the user's save
        # isn't broken by a downstream workflow bug.
        try:
            from ..engine import run_workflow_background
            run_workflow_background(
                workflow_name=wf_name,
                trigger_source=f"doctype:{doc.doctype}/{event}",
                payload=payload,
                user=user,
            )
        except Exception as inner:
            frappe.log_error(
                title=f"FlowAgent: inline fallback failed for {wf_name}",
                message=f"{type(inner).__name__}: {inner}",
            )


def _build_payload(doc, event: str) -> dict:
    """Serialise the doc into a payload that the workflow can consume."""
    return {
        "doc": doc.as_dict(no_default_fields=False),
        "doc_name": doc.name,
        "doctype": doc.doctype,
        "event": event,
        "user": frappe.session.user,
    }


def _eval_condition(expr: str, doc) -> bool:
    """Evaluate the trigger_condition Python expression.

    Uses Frappe's safe_exec so user-authored conditions can't do
    arbitrary IO. Conditions should assign to `result` or be a single
    expression that the safe evaluator can read.
    """
    from frappe.utils.safe_exec import safe_exec

    local = {"doc": doc, "result": None}
    # Wrap a bare expression so safe_exec captures it
    code = expr if "result" in expr or "\n" in expr else f"result = bool({expr})"
    safe_exec(code, _locals=local)
    return bool(local.get("result"))


def _verbose() -> bool:
    """Read the verbose toggle from settings. Cached for the request."""
    try:
        return bool(frappe.db.get_single_value("FlowAgent Settings", "verbose_logging"))
    except Exception:
        return False
