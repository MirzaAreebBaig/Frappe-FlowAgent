# Copyright (c) 2026, FlowAgent
# For license information, please see license.txt
"""
Approval callback endpoint.

The logic_approval node emails approvers two URLs:

  /api/method/flowagent.api.approval.decide?token=<token>&decision=approve
  /api/method/flowagent.api.approval.decide?token=<token>&decision=reject

When clicked, this endpoint:
  1. Validates the token against the Waiting run
  2. Validates the run hasn't already been decided / expired
  3. Enqueues a background resume of the workflow
  4. Returns a small HTML page confirming the decision

Tokens are non-guessable (32 bytes of entropy) so the URLs are
themselves the auth mechanism. We don't require a logged-in user —
approvers might be external (vendors, customers) and shouldn't need
desk access.

A separate scheduled task `expire_waiting_runs` (in tasks.py) sweeps
the run table for runs past their `waiting_expires_at` and either
resumes them with the configured `on_timeout` decision or fails them.
"""
from __future__ import annotations

import frappe


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def decide(token: str = None, decision: str = None):
    """Receive an approval/rejection decision.

    Guest-allowed because approvers may not have desk accounts. Auth is
    via the unguessable token itself, which was emailed to the specific
    approver.
    """
    if not token or not decision:
        return _html_response(
            "Missing parameters",
            "The link appears to be malformed. Both `token` and `decision` are required.",
            error=True,
        )

    decision = (decision or "").strip().lower()
    if decision not in ("approve", "reject"):
        return _html_response(
            "Invalid decision",
            "Decision must be 'approve' or 'reject'.",
            error=True,
        )

    # Find the Waiting run by token. We use frappe.get_all (not
    # frappe.db.get_value) so we explicitly handle the not-found case.
    matches = frappe.get_all(
        "FlowAgent Workflow Run",
        filters={"waiting_token": token, "status": "Waiting"},
        fields=["name", "workflow", "waiting_expires_at"],
        limit=1,
        ignore_permissions=True,
    )
    if not matches:
        # Token doesn't match a Waiting run. Could be: already decided,
        # token invalid, run was cancelled, etc. Tell the user without
        # leaking which.
        return _html_response(
            "Already decided or invalid link",
            "This approval link is no longer valid. It may have already "
            "been decided, expired, or never existed.",
            error=True,
        )

    run_info = matches[0]
    run_name = run_info["name"]

    # Expiry check. If the run expired, fail it explicitly rather than
    # processing the late decision.
    if run_info["waiting_expires_at"]:
        from frappe.utils import now_datetime
        if run_info["waiting_expires_at"] < now_datetime():
            try:
                _fail_expired(run_name)
            except Exception:
                pass
            return _html_response(
                "Approval expired",
                "The approval window for this workflow has passed. "
                "Please ask the workflow owner to re-trigger if still needed.",
                error=True,
            )

    # Enqueue the resume in the background — don't block the HTTP
    # response on whatever the downstream nodes do.
    try:
        frappe.enqueue(
            "flowagent.engine.resume_run",
            run_name=run_name,
            decision=decision,
            queue="default",
            timeout=600,
        )
    except Exception as e:
        return _html_response(
            "Failed to resume workflow",
            f"The decision was received but resuming the workflow failed: "
            f"{type(e).__name__}: {e}",
            error=True,
        )

    pretty_decision = "Approved" if decision == "approve" else "Rejected"
    colour = "#10B981" if decision == "approve" else "#EF4444"
    return _html_response(
        f"{pretty_decision}",
        f"The workflow ({frappe.utils.escape_html(run_info['workflow'])}) "
        "has been notified and will continue.",
        accent=colour,
    )


def _fail_expired(run_name: str) -> None:
    """Mark an expired Waiting run as Failed with a clear message."""
    frappe.db.set_value("FlowAgent Workflow Run", run_name, {
        "status": "Failed",
        "error_message": "Approval timed out — no decision received within the configured window.",
        "waiting_token": None,
    }, update_modified=False)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Force visibility: the user is about to be shown the "expired" page; the failed status must be persisted before any subsequent retry/poll could re-read this run.


def _html_response(title: str, body: str, error: bool = False, accent: str | None = None):
    """Render a styled confirmation page using Frappe's web page response.

    `frappe.respond_as_web_page` is the canonical way to return HTML
    from a whitelisted endpoint — it handles the response type, content
    type, and template wrapping for us.
    """
    if accent is None:
        accent = "#EF4444" if error else "#10B981"

    html_body = f"""
<style>
  .fa-approval-card {{
    background: white; border-radius: 12px; padding: 40px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
    max-width: 480px; margin: 64px auto;
    border-top: 4px solid {accent};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }}
  .fa-approval-card h2 {{
    margin: 0 0 12px 0; font-size: 22px; color: {accent}; font-weight: 600;
  }}
  .fa-approval-card p {{ margin: 0; color: #4B5563; line-height: 1.5; }}
  .fa-approval-card .meta {{
    margin-top: 24px; padding-top: 16px; border-top: 1px solid #E5E7EB;
    font-size: 12px; color: #9CA3AF;
  }}
</style>
<div class="fa-approval-card">
  <h2>{frappe.utils.escape_html(title)}</h2>
  <p>{body}</p>
  <div class="meta">FlowAgent · You can close this tab.</div>
</div>
"""
    frappe.respond_as_web_page(
        title="FlowAgent",
        html=html_body,
        indicator_color="red" if error else "green",
        primary_action=None,
    )
    # Return value isn't shown to the user — respond_as_web_page took
    # over the response. Returning a marker keeps Frappe's API happy.
    return {"ok": not error, "title": title}
