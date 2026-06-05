# Copyright (c) 2026, FlowAgent
# For license information, please see license.txt
"""Install / migrate hooks for FlowAgent.

Idempotent: safe to run any number of times. Handled in order:
1. Ensure the FlowAgent Manager role exists
2. Ensure the FlowAgent Settings singleton exists
3. Delete leftover `FlowAgent X`-prefixed Number Cards / Charts from
   earlier (broken) install attempts so they don't sit around as orphans
4. Re-import all Number Cards, Dashboard Charts, and the Workspace JSON
   from disk so users see layout updates with every release

With v0.3.7+ we ship records named `Runs Today`, `Daily Runs`, etc. —
matching the Number Card / Dashboard Chart autoname rules
(`field:label` and `field:chart_name` respectively). This means Frappe's
standard import path produces records with the names our workspace
content blocks reference, so the rendering "just works" without any
of the `name_set` flag gymnastics from earlier versions.
"""
from __future__ import annotations

import frappe


# Records from previous (broken) install attempts. These were created
# under the old "FlowAgent X" naming scheme that didn't match Frappe's
# autoname rules. Now they're orphans — clean them out.
_LEGACY_PREFIXED_CARDS = [
    "FlowAgent Runs Today",
    "FlowAgent Failed Today",
    "FlowAgent Avg Duration 7d",
    "FlowAgent AI Cost Month",
    "FlowAgent Active Workflows",
]
_LEGACY_PREFIXED_CHARTS = [
    "FlowAgent Daily Runs",
    "FlowAgent Cost Trend",
    "FlowAgent Status Breakdown",
    "FlowAgent Top Workflows",
]


def after_install():
    """Run once after `bench install-app flowagent`."""
    _ensure_role()
    _ensure_settings()
    _cleanup_legacy_assets()
    _refresh_dashboard_assets()
    _refresh_workspace()
    frappe.db.commit()


def after_migrate():
    """Run after every `bench migrate` — idempotent."""
    _ensure_role()
    _ensure_settings()
    _cleanup_legacy_assets()
    _refresh_dashboard_assets()
    _refresh_workspace()
    frappe.db.commit()


def _ensure_role():
    if not frappe.db.exists("Role", "FlowAgent Manager"):
        role = frappe.new_doc("Role")
        role.role_name = "FlowAgent Manager"
        role.desk_access = 1
        role.flags.ignore_permissions = True
        role.insert(ignore_permissions=True)


def _ensure_settings():
    if not frappe.db.exists("FlowAgent Settings", "FlowAgent Settings"):
        doc = frappe.new_doc("FlowAgent Settings")
        doc.default_model = "claude-sonnet-4-5"
        doc.max_steps_per_run = 100
        doc.max_agent_iterations = 8
        doc.run_retention_days = 30
        doc.webhook_secret = frappe.generate_hash(length=32)
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)


def _cleanup_legacy_assets():
    """Delete the `FlowAgent X`-prefixed Number Cards and Dashboard
    Charts left behind by v0.3.4-v0.3.6 install attempts.

    Safe because we only delete records with an exact name match from a
    known-finite list — no wildcard / startswith / module-wide deletion
    that could touch a user-created record.
    """
    for name in _LEGACY_PREFIXED_CARDS:
        if frappe.db.exists("Number Card", name):
            try:
                frappe.delete_doc("Number Card", name,
                                  ignore_permissions=True, force=True)
            except Exception as e:
                frappe.log_error(
                    title=f"FlowAgent: cleanup failed for legacy Number Card {name}",
                    message=f"{type(e).__name__}: {e}",
                )

    for name in _LEGACY_PREFIXED_CHARTS:
        if frappe.db.exists("Dashboard Chart", name):
            try:
                frappe.delete_doc("Dashboard Chart", name,
                                  ignore_permissions=True, force=True)
            except Exception as e:
                frappe.log_error(
                    title=f"FlowAgent: cleanup failed for legacy Dashboard Chart {name}",
                    message=f"{type(e).__name__}: {e}",
                )


def _refresh_dashboard_assets():
    """Import every Number Card and Dashboard Chart JSON from disk.

    Now that record names match their label/chart_name (i.e. align with
    the autoname rules), Frappe's standard import does the right thing.
    No need to set `flags.name_set` or do a manual upsert anymore.
    """
    import glob
    import os
    from frappe.modules.import_file import import_file_by_path

    app_path = frappe.get_app_path("flowagent")

    for subdir in ("number_card", "dashboard_chart"):
        pattern = os.path.join(
            app_path, "flowagent_core", subdir, "*", "*.json",
        )
        for path in sorted(glob.glob(pattern)):
            try:
                import_file_by_path(path, force=True)
            except Exception as e:
                frappe.log_error(
                    title=f"FlowAgent: import failed for {os.path.basename(path)}",
                    message=f"{type(e).__name__}: {e}",
                )


def _refresh_workspace():
    """Re-import the FlowAgent workspace from disk on every migrate.

    Frappe normally preserves user edits to workspaces during migrate
    (which would block our layout updates from landing). We only force
    refresh `is_standard=1` workspaces with no `for_user` set — i.e.
    the shared "system" copy — and never touch a personal customised
    version.
    """
    try:
        if frappe.db.exists("Workspace", "FlowAgent"):
            ws_info = frappe.db.get_value(
                "Workspace", "FlowAgent",
                ["for_user", "is_standard"], as_dict=True,
            ) or {}
            if not ws_info.get("for_user") and ws_info.get("is_standard"):
                frappe.delete_doc(
                    "Workspace", "FlowAgent",
                    ignore_permissions=True, force=True,
                )

        import os
        from frappe.modules.import_file import import_file_by_path
        ws_path = os.path.join(
            frappe.get_app_path("flowagent"),
            "flowagent_core", "workspace", "flowagent", "flowagent.json",
        )
        if os.path.exists(ws_path):
            import_file_by_path(ws_path, force=True)
    except Exception as e:
        # Best-effort: never let workspace refresh break migrate.
        frappe.log_error(
            title="FlowAgent: workspace refresh skipped",
            message=f"{type(e).__name__}: {e}",
        )
