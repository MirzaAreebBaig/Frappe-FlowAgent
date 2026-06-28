# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Scheduled housekeeping.
"""

from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.utils import now_datetime


def cleanup_old_runs():
    """Delete Workflow Run history older than the configured retention."""
    settings = frappe.get_single("FlowAgent Settings")
    days = int(settings.run_retention_days or 30)
    if days <= 0:
        return  # 0 = keep forever
    cutoff = now_datetime() - timedelta(days=days)
    old = frappe.get_all(
        "FlowAgent Workflow Run",
        filters={"creation": ("<", cutoff)},
        pluck="name",
        limit=500,  # cap per tick to keep this cheap
    )
    for name in old:
        try:
            frappe.delete_doc(
                "FlowAgent Workflow Run", name,
                ignore_permissions=True, force=True, delete_permanently=True,
            )
        except Exception:
            # Skip stuck rows; next tick will try again
            continue
    if old:
        frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Batch operation: cleanup task deleted up to 500 stale runs; commit so DB locks release before this scheduled tick ends.


def expire_waiting_runs():
    """Sweep runs in status=Waiting whose waiting_expires_at is in the past.

    Default policy on expiry: mark Failed with a clear error message.
    Per-node `on_timeout` configuration (approve / reject / fail) is read
    from the original logic_approval node's cfg and applied accordingly.

    Capped at 50 per tick — if more are stuck somehow, the next tick
    picks up the rest.
    """
    cutoff = now_datetime()
    expired = frappe.get_all(
        "FlowAgent Workflow Run",
        filters={
            "status": "Waiting",
            "waiting_expires_at": ("<", cutoff),
        },
        fields=["name", "workflow", "waiting_at_node"],
        limit=50,
    )
    if not expired:
        return

    for r in expired:
        try:
            _resolve_expired_run(r)
        except Exception as e:
            frappe.log_error(
                title=f"FlowAgent: expire_waiting_runs failed for {r['name']}",
                message=f"{type(e).__name__}: {e}",
            )
    frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Batch operation: expired waiting runs were marked Failed or re-enqueued for resume; commit so the next scheduler tick sees a clean state.


def _resolve_expired_run(run_info: dict):
    """Apply the approval node's `on_timeout` policy to an expired run.

    Falls back to 'reject' (a safe default — don't auto-approve things
    because the approver was on vacation).
    """
    run_name = run_info["name"]
    paused_at = run_info.get("waiting_at_node")
    wf_name = run_info.get("workflow")

    # Look up the approval node's on_timeout config
    on_timeout = "reject"
    if paused_at and wf_name:
        try:
            wf = frappe.get_doc("FlowAgent Workflow", wf_name)
            for n in wf.get_nodes():
                if n.get("id") == paused_at and n.get("type") == "logic_approval":
                    cfg = n.get("cfg") or {}
                    on_timeout = (cfg.get("on_timeout") or "reject").lower()
                    break
        except Exception:
            pass

    if on_timeout == "fail":
        frappe.db.set_value("FlowAgent Workflow Run", run_name, {
            "status": "Failed",
            "error_message": "Approval timed out — no decision received within the configured window.",
            "waiting_token": None,
        }, update_modified=False)
        return

    # Resume with the timeout decision (approve / reject)
    if on_timeout not in ("approve", "reject"):
        on_timeout = "reject"
    frappe.enqueue(
        "flowagent.engine.resume_run",
        run_name=run_name,
        decision=on_timeout,
        queue="default",
        timeout=600,
    )
