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
# Wildcard doc_events is INTENTIONAL and architecturally necessary for
# a workflow automation tool. Workflows trigger on arbitrary DocTypes
# chosen at runtime by end users — we cannot statically declare which
# DocTypes to listen on.
#
# Performance: the dispatcher's first line is an indexed lookup against
# FlowAgent Workflow Trigger Index. If no workflow subscribes to this
# (DocType, event) pair, the dispatcher returns in microseconds without
# touching anything else. The lookup uses a composite index on
# (trigger_doctype, trigger_event) so it's O(log n) regardless of how
# many workflows exist.
#
# This matches the architecture of Frappe's built-in Notification doctype
# and Server Script's "DocType Event" type — both of which use the same
# pattern under the hood.
doc_events = {
    "*": {
        "after_insert": "flowagent.triggers.doctype_dispatcher.on_event",
        "on_update": "flowagent.triggers.doctype_dispatcher.on_event",
        "on_submit": "flowagent.triggers.doctype_dispatcher.on_event",
        "on_cancel": "flowagent.triggers.doctype_dispatcher.on_event",
        "on_trash": "flowagent.triggers.doctype_dispatcher.on_event",
        "on_change": "flowagent.triggers.doctype_dispatcher.on_event",
    }
}

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
