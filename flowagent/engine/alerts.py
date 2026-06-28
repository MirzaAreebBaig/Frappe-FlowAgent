# Copyright (c) 2026, FlowAgent
# For license information, please see license.txt
"""Alert dispatch for FlowAgent.

Called from `Runner._finalise` whenever a run lands in a terminal
failure state (Failed or Timeout). Iterates active Alert Rules and
fires any whose condition matches, respecting per-rule cooldowns.

Channels supported:
  - Email           — Frappe's frappe.sendmail
  - Slack Webhook   — POST to a Slack incoming webhook URL
  - HTTP Webhook    — POST a JSON payload to an arbitrary URL

Failures inside alert dispatch are swallowed and logged — we never
let a misconfigured alert rule break the run that triggered it.
"""
from __future__ import annotations

import json

import frappe
from frappe.utils import add_to_date, now_datetime


def check_and_fire_alerts(run) -> None:
    """Entry point. Called from the runner after a run reaches a
    terminal status. `run` is the FlowAgent Workflow Run doc."""
    if run.status not in ("Failed", "Timeout"):
        return

    try:
        rules = frappe.get_all(
            "FlowAgent Alert Rule",
            filters={"enabled": 1},
            fields=[
                "name", "workflow", "trigger_condition",
                "threshold_count", "threshold_window_minutes",
                "channel", "channel_target", "message_template",
                "cooldown_minutes", "last_fired",
            ],
        )
    except Exception as e:
        frappe.log_error(
            title="FlowAgent alerts: rule lookup failed",
            message=f"{type(e).__name__}: {e}",
        )
        return

    for rule in rules:
        try:
            _evaluate_rule(rule, run)
        except Exception as e:
            frappe.log_error(
                title=f"FlowAgent alerts: rule {rule.name} failed",
                message=f"{type(e).__name__}: {e}",
            )


def _evaluate_rule(rule, run) -> None:
    # Workflow filter — empty means "all workflows"
    if rule.workflow and rule.workflow != run.workflow:
        return

    # Cooldown — silently skip if we fired recently
    if rule.last_fired and rule.cooldown_minutes:
        cutoff = add_to_date(now_datetime(), minutes=-int(rule.cooldown_minutes))
        if rule.last_fired > cutoff:
            return

    cond = rule.trigger_condition
    fire = False
    threshold_count_actual = None

    if cond == "On Failure" and run.status == "Failed":
        fire = True
    elif cond == "On Timeout" and run.status == "Timeout":
        fire = True
    elif cond == "Threshold":
        # Count recent failures in the rule's window
        window = int(rule.threshold_window_minutes or 10)
        cutoff = add_to_date(now_datetime(), minutes=-window)
        filters = {
            "status": ["in", ["Failed", "Timeout"]],
            "creation": [">", cutoff],
        }
        if rule.workflow:
            filters["workflow"] = rule.workflow
        threshold_count_actual = frappe.db.count(
            "FlowAgent Workflow Run", filters=filters
        )
        if threshold_count_actual >= int(rule.threshold_count or 3):
            fire = True

    if not fire:
        return

    _dispatch(rule, run, threshold_count_actual)

    # Record the fire timestamp so cooldown takes effect
    frappe.db.set_value(
        "FlowAgent Alert Rule", rule.name, "last_fired", now_datetime()
    )


def _dispatch(rule, run, threshold_count_actual) -> None:
    title, body = _format_message(rule, run, threshold_count_actual)

    channel = rule.channel
    target = (rule.channel_target or "").strip()
    if not target:
        return

    if channel == "Email":
        _send_email(target, title, body, run)
    elif channel == "Slack Webhook":
        _send_slack(target, title, body, run)
    elif channel == "HTTP Webhook":
        _send_http(target, title, body, run, threshold_count_actual)


def _format_message(rule, run, threshold_count) -> tuple[str, str]:
    """Render the alert message. Uses the rule's `message_template` as
    a Jinja template if set; otherwise a sensible default."""
    error_first_line = ""
    if run.error_message:
        error_first_line = str(run.error_message).split("\n", 1)[0][:300]

    title = f"FlowAgent: {run.workflow} {run.status}"
    default_body = (
        f"Workflow: {run.workflow}\n"
        f"Run: {run.name}\n"
        f"Status: {run.status}\n"
        f"Duration: {run.duration_ms or 0}ms\n"
    )
    if threshold_count is not None:
        default_body = (
            f"⚠ {threshold_count} failures in {rule.threshold_window_minutes}min\n\n"
            + default_body
        )
    if error_first_line:
        default_body += f"\nError: {error_first_line}"

    if rule.message_template:
        try:
            ctx = {
                "run": run.name,
                "workflow": run.workflow,
                "status": run.status,
                "error": error_first_line,
                "duration_ms": run.duration_ms or 0,
                "count": threshold_count,
            }
            # SAFETY: rule.message_template comes from a FlowAgent Alert
            # Rule document — writable only by System Manager and FlowAgent
            # Manager roles (see the doctype permissions). Same trust level
            # as Frappe's built-in Notification doctype. Sandboxed Jinja
            # blocks dangerous attribute access and globals; ctx values
            # are interpolated via the data dict, not the template string.
            body = frappe.render_template(rule.message_template, ctx)  # nosemgrep: frappe-ssti
        except Exception:
            # Fall back to default if template rendering fails
            body = default_body
    else:
        body = default_body

    return title, body


def _send_email(target: str, title: str, body: str, run) -> None:
    recipients = [r.strip() for r in target.split(",") if r.strip()]
    if not recipients:
        return
    site_url = frappe.utils.get_url()
    run_url = f"{site_url}/app/flowagent-workflow-run/{run.name}"
    html_body = (
        f"<p style='white-space:pre-wrap;font-family:monospace'>{frappe.utils.escape_html(body)}</p>"
        f"<p><a href='{run_url}'>Open run in FlowAgent →</a></p>"
    )
    frappe.sendmail(
        recipients=recipients,
        subject=title,
        message=html_body,
        delayed=False,
    )


def _send_slack(webhook_url: str, title: str, body: str, run) -> None:
    """Post to a Slack incoming webhook. Uses block kit for nicer layout."""
    site_url = frappe.utils.get_url()
    run_url = f"{site_url}/app/flowagent-workflow-run/{run.name}"
    color = "#EF4444" if run.status == "Failed" else "#F97316"
    payload = {
        "text": title,  # fallback text for notifications
        "attachments": [
            {
                "color": color,
                "title": title,
                "title_link": run_url,
                "text": body,
                "footer": "FlowAgent",
                "ts": int(frappe.utils.now_datetime().timestamp()),
            }
        ],
    }
    _post_json(webhook_url, payload)


def _send_http(url: str, title: str, body: str, run, threshold_count) -> None:
    site_url = frappe.utils.get_url()
    payload = {
        "title": title,
        "body": body,
        "run": run.name,
        "workflow": run.workflow,
        "status": run.status,
        "duration_ms": run.duration_ms or 0,
        "error": (run.error_message or "")[:1000],
        "threshold_count": threshold_count,
        "url": f"{site_url}/app/flowagent-workflow-run/{run.name}",
    }
    _post_json(url, payload)


def _post_json(url: str, payload: dict) -> None:
    import requests
    requests.post(url, json=payload, timeout=8)
