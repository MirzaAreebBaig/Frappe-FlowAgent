# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Post-install / post-migrate hooks.

We ensure the FlowAgent Settings single exists and seed a couple of
example workflows so a fresh install isn't an empty canvas.
"""

import frappe


def after_install():
    """Run once after `bench install-app flowagent`."""
    _ensure_role()
    _ensure_settings()
    # Order matters: ensure the cards/charts exist BEFORE the workspace
    # is re-imported, otherwise the workspace's references would point
    # to records that don't exist yet and Frappe would silently drop them.
    _refresh_dashboard_assets()
    _refresh_workspace()
    frappe.db.commit()


def after_migrate():
    """Run after every `bench migrate` — idempotent."""
    _ensure_role()
    _ensure_settings()
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


def _refresh_dashboard_assets():
    """Force-import every FlowAgent Number Card and Dashboard Chart JSON
    file from disk.

    Why: Frappe's automatic sync during migrate picks up DocTypes and
    Reports reliably, but Number Card / Dashboard Chart JSONs in module
    folders are NOT always re-imported on subsequent migrates — and
    sometimes not imported at all if the order of operations is off.

    The symptom is a workspace that shows headers and shortcuts but
    not the cards/charts referenced in its `content` JSON: Frappe
    couldn't find the records by name so it skipped those blocks.

    Approach:
      1. Try `import_file_by_path(force=True)` on each JSON — the
         canonical Frappe mechanism.
      2. After each import, verify the record exists with the expected
         name. If not, fall back to explicit creation. This covers a
         Number Card autoname quirk where `field:label` autoname can
         re-derive the name from `label` when the explicit `name` is
         stripped by certain import paths.
      3. Force `is_public=1` on every record so the workspace can
         render them regardless of the viewing user's role.
    """
    import glob
    import json as _json
    import os
    from frappe.modules.import_file import import_file_by_path

    app_path = frappe.get_app_path("flowagent")

    for subdir, doctype in (("number_card", "Number Card"),
                            ("dashboard_chart", "Dashboard Chart")):
        pattern = os.path.join(
            app_path, "flowagent_core", subdir, "*", "*.json",
        )
        for path in sorted(glob.glob(pattern)):
            try:
                with open(path) as f:
                    spec = _json.load(f)
                expected_name = spec.get("name") or spec.get("label")
                if not expected_name:
                    continue

                # First attempt: the canonical Frappe import
                try:
                    import_file_by_path(path, force=True)
                except Exception as e:
                    frappe.log_error(
                        title=f"FlowAgent: import_file_by_path failed for {doctype} {expected_name}",
                        message=f"{type(e).__name__}: {e}",
                    )

                # Verify and fall back to explicit upsert if needed
                if not frappe.db.exists(doctype, expected_name):
                    _explicit_upsert(doctype, expected_name, spec)

                # Force is_public so workspaces can render the record
                if frappe.db.exists(doctype, expected_name):
                    if not frappe.db.get_value(doctype, expected_name, "is_public"):
                        frappe.db.set_value(doctype, expected_name, "is_public", 1)
            except Exception as e:
                frappe.log_error(
                    title=f"FlowAgent: failed to refresh {os.path.basename(path)}",
                    message=f"{type(e).__name__}: {e}",
                )


def _explicit_upsert(doctype: str, name: str, spec: dict):
    """Create or update a Number Card / Dashboard Chart record by hand
    using the spec dict. Used as a fallback when Frappe's normal import
    path doesn't produce the record with the expected name.
    """
    SKIP = {"doctype", "creation", "modified", "modified_by", "owner",
            "idx", "docstatus"}

    is_new = not frappe.db.exists(doctype, name)
    if is_new:
        doc = frappe.new_doc(doctype)
        # Set name explicitly; defeats the `field:label` autoname rule
        # on Number Card when the explicit name needs to be preserved.
        doc.name = name
        doc.flags.name_set = True
    else:
        doc = frappe.get_doc(doctype, name)

    for k, v in spec.items():
        if k in SKIP:
            continue
        try:
            doc.set(k, v)
        except Exception:
            # Field doesn't exist on this doctype version — skip silently.
            # Better to have a working card with one missing optional field
            # than to fail import entirely.
            pass

    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True
    try:
        if is_new:
            doc.insert(ignore_permissions=True)
        else:
            doc.save()
    except frappe.DuplicateEntryError:
        # Race or rename collision — record is already there, move on
        pass
    except Exception as e:
        frappe.log_error(
            title=f"FlowAgent: _explicit_upsert failed for {doctype} {name}",
            message=f"{type(e).__name__}: {e}",
        )


def _refresh_workspace():
    """Re-import the FlowAgent workspace from disk on every migrate.

    Why: Frappe's standard workspace sync during migrate preserves user
    edits, which is normally what you want — but here we ship layout
    updates with new releases (number cards, charts, links to reports)
    and want users on a fresh upgrade to see them.

    We only force-refresh `is_standard=1` workspaces with no `for_user`
    set — never touch a workspace someone has customised as their own.
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

        # Re-import from disk so the new layout takes effect immediately,
        # without waiting for another migrate cycle.
        import os
        from frappe.modules.import_file import import_file_by_path
        ws_path = os.path.join(
            frappe.get_app_path("flowagent"),
            "flowagent_core", "workspace", "flowagent", "flowagent.json",
        )
        if os.path.exists(ws_path):
            import_file_by_path(ws_path, force=True)
    except Exception as e:
        # Workspace refresh is best-effort; never let it break migrate.
        frappe.log_error(
            title="FlowAgent: workspace refresh skipped",
            message=f"{type(e).__name__}: {e}",
        )
