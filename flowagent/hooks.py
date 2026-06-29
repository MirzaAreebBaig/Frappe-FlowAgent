# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt

from . import __version__ as app_version  # noqa: F401

app_name = "flowagent"
app_title = "FlowAgent"
app_publisher = "FlowAgent"
app_description = "Visual AI Workflow Automation for Frappe — drag-and-drop builder with AI agents, DocType triggers, and multi-step orchestration"
app_email = "hello@flowagent.dev"
app_license = "MIT"
required_apps = []

# Includes
# ----------------------------------------------------------------------
# Bundled assets for the Studio page and Desk integrations.
app_include_css = "/assets/flowagent/css/flowagent.css"
app_include_js = "/assets/flowagent/js/flowagent.js"

# Installation
# ----------------------------------------------------------------------
after_install = "flowagent.install.after_install"
after_migrate = "flowagent.install.after_migrate"

# Website routes
# ----------------------------------------------------------------------
# Public-facing hosted forms. /f/<slug> resolves to www/flowagent_form.html
# which renders the FlowAgent Form with matching slug.
website_route_rules = [
    {"from_route": "/f/<slug>", "to_route": "flowagent_form"},
]

# DocType Events
# ----------------------------------------------------------------------
# We build doc_events dynamically from the FlowAgent Workflow Trigger
# Index table at module load time, listing only the specific DocTypes
# that have active workflow triggers — not a wildcard. This satisfies
# Frappe Cloud's audit recommendation and avoids firing the dispatcher
# on every doc operation across unrelated DocTypes.
#
# UX caveat: hooks.py is evaluated when Frappe imports the app
# (typically at worker startup). When a user adds a workflow with a
# trigger on a DocType not previously seen, the worker needs to be
# restarted (`bench restart`) for that DocType to be wired into
# doc_events. The Studio surfaces a banner after save when a restart
# is needed (see `_needs_restart_for_doctype` in api/studio.py).
#
# Architecture: the dispatcher does an indexed lookup against the
# trigger index on every event. For DocTypes WITHOUT a registered
# workflow trigger, no event hook fires at all — Frappe doesn't even
# call into our app. This is strictly better than the prior wildcard.

def _build_doc_events():
    """Read the trigger index and produce a targeted doc_events dict.

    Returns an empty dict if the DB isn't available (e.g. very first
    install before doctype sync runs). The dispatcher's diagnose
    endpoint can be used to verify what's currently wired.
    """
    try:
        import frappe
        # Only proceed if there's a real DB connection. During app
        # discovery (e.g. on `pip install`), there is none.
        if not getattr(frappe, "db", None):
            return {}
        # Check the trigger index table exists before querying it —
        # avoids a noisy error log on first install when doctype sync
        # hasn't created the table yet.
        if not frappe.db.table_exists("FlowAgent Workflow Trigger Index"):
            return {}
        rows = frappe.db.sql(
            "SELECT DISTINCT trigger_doctype, trigger_event "
            "FROM `tabFlowAgent Workflow Trigger Index` "
            "WHERE trigger_doctype IS NOT NULL "
            "  AND trigger_event IS NOT NULL "
            "  AND trigger_doctype != '' ",
            as_dict=True,
        )
    except Exception:
        # Any error during hook load must not crash Frappe — return
        # empty and let the diagnose endpoint surface the issue.
        return {}

    # Map FlowAgent's user-facing event names to Frappe's controller hooks
    event_map = {
        "After Insert": "after_insert",
        "After Save":   "on_update",
        "After Submit": "on_submit",
        "After Cancel": "on_cancel",
        "After Delete": "on_trash",
        "On Change":    "on_change",
    }
    HANDLER = "flowagent.triggers.doctype_dispatcher.on_event"
    result: dict = {}
    for row in rows:
        dt = row.get("trigger_doctype")
        hook = event_map.get(row.get("trigger_event"))
        if not dt or not hook:
            continue
        result.setdefault(dt, {})[hook] = HANDLER
    return result


doc_events = _build_doc_events()

# Scheduled Tasks
# ----------------------------------------------------------------------
scheduler_events = {
    "cron": {
        # Every minute — the scheduler tick that evaluates cron triggers.
        "* * * * *": [
            "flowagent.triggers.schedule_dispatcher.tick"
        ],
        # Every 5 minutes — sweep for paused-too-long approval runs and
        # apply their configured timeout policy.
        "*/5 * * * *": [
            "flowagent.tasks.expire_waiting_runs"
        ],
    },
    "hourly": [
        # Housekeeping: trim Workflow Run history older than retention
        "flowagent.tasks.cleanup_old_runs"
    ]
}

# Whitelisted methods exposed under /api/method/<dotted.path>
# (Frappe whitelists are declared on the method itself; this is just
# documentation of the public surface.)
#
# flowagent.api.studio.load_workflow
# flowagent.api.studio.save_workflow
# flowagent.api.studio.list_workflows
# flowagent.api.studio.delete_workflow
# flowagent.api.studio.run_workflow_now
# flowagent.api.studio.get_run
# flowagent.api.studio.recent_runs
# flowagent.api.ai_build.build_from_prompt
# flowagent.api.webhook.handle  (with token)

# Website route rules: the FlowAgent Studio page lives in the Desk,
# not the website, so no rules here.

# Fixtures: ship a few example workflows on install
fixtures = []
