# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
FlowAgent execution engine package.

Public surface:
  run_workflow_background -- entry point for frappe.enqueue
  Runner                  -- directly callable synchronously (used by tests
                             and the "Run Now" button)
"""

from __future__ import annotations

import frappe

from .runner import Runner


def run_workflow_background(workflow_name, trigger_source="manual",
                            payload=None, user=None, dry_run=False,
                            existing_run_name=None):
    """Background-worker entry point.

    Lives at this dotted path so it can be referenced by frappe.enqueue
    without circular import worries.
    """
    if user and user != frappe.session.user:
        frappe.set_user(user)
    runner = Runner(
        workflow_name=workflow_name,
        trigger_source=trigger_source,
        payload=payload or {},
        user=user,
        dry_run=dry_run,
        existing_run_name=existing_run_name,
    )
    return runner.execute()


def resume_run(run_name: str, decision: str) -> str:
    """Resume a paused run after an approval decision arrives.

    Called from the approval API endpoint after it has validated the
    callback token. Constructs a Runner adopting the existing run doc,
    sets the resume hints (which node to continue from + which port the
    decision picks), and re-enters execution.

    `decision` is the short port suffix: 'approve' or 'reject'. The
    runner uses this to pick which outgoing edges to walk:
      - decision='approve' → edges with fromPort='out-approve'
      - decision='reject'  → edges with fromPort='out-reject'
    """
    run = frappe.get_doc("FlowAgent Workflow Run", run_name)
    if run.status != "Waiting":
        frappe.throw(
            f"Run {run_name} is in status {run.status}, not Waiting — "
            "cannot resume."
        )
    if not run.waiting_at_node:
        frappe.throw(f"Run {run_name} has no waiting_at_node — cannot resume.")

    runner = Runner(
        workflow_name=run.workflow,
        trigger_source=f"resume:{decision}",
        payload={},
        existing_run_name=run_name,
        user=run.owner,
    )
    runner._resume_from_node = run.waiting_at_node
    runner._resume_decision = decision

    # Clear the waiting markers so the run is no longer "Waiting" while
    # we continue executing it.
    frappe.db.set_value("FlowAgent Workflow Run", run_name, {
        "status": "Running",
        "waiting_token": None,
        "waiting_decision_port": "out-" + decision,
    }, update_modified=False)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Worker queue handoff: clearing waiting_token before enqueueing the resume job; the resume worker reads this run's state and must see the cleared token (else it would think the run is still Waiting).

    return runner.execute()


__all__ = ["Runner", "run_workflow_background", "resume_run"]
