# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Whitelisted methods exposed to the FlowAgent Studio frontend.

All methods require System Manager OR FlowAgent Manager.
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import cint


def _check_perm():
    if not (
        "System Manager" in frappe.get_roles()
        or "FlowAgent Manager" in frappe.get_roles()
    ):
        frappe.throw("Not permitted", frappe.PermissionError)


# -------------------------------------------------------------------------
# Workflow CRUD
# -------------------------------------------------------------------------
@frappe.whitelist()
def list_workflows():
    """Sidebar list of workflows."""
    _check_perm()
    return frappe.get_all(
        "FlowAgent Workflow",
        fields=["name", "workflow_name", "enabled", "trigger_type",
                "trigger_doctype", "last_run_status", "total_runs",
                "modified", "tags"],
        order_by="modified desc",
        limit=200,
    )


@frappe.whitelist()
def load_workflow(name: str):
    """Hydrate a workflow for the canvas."""
    _check_perm()
    doc = frappe.get_doc("FlowAgent Workflow", name)
    return {
        "name": doc.name,
        "workflow_name": doc.workflow_name,
        "enabled": bool(doc.enabled),
        "description": doc.description,
        "trigger": {
            "type": doc.trigger_type,
            "doctype": doc.trigger_doctype,
            "event": doc.trigger_event,
            "cron": doc.trigger_cron,
            "condition": doc.trigger_condition,
        },
        "nodes": doc.get_nodes(),
        "edges": doc.get_edges(),
        "viewport": _json_or_default(doc.viewport_json, {"x": 0, "y": 0, "zoom": 1}),
        "runtime": {
            "on_error": doc.on_error,
            "max_retries": doc.max_retries,
            "log_level": doc.log_level,
        },
        "stats": {
            "total_runs": doc.total_runs,
            "last_run_status": doc.last_run_status,
            "last_run_at": str(doc.last_run_at) if doc.last_run_at else None,
        },
        "webhook_path": doc.webhook_path,
    }


@frappe.whitelist()
def save_workflow(payload: str):
    """Save (create or update) a workflow from canvas state."""
    _check_perm()
    data = json.loads(payload) if isinstance(payload, str) else payload

    name = data.get("name") or data.get("workflow_name")
    if not name:
        frappe.throw("workflow_name is required")

    existing = frappe.db.exists("FlowAgent Workflow", name)
    if existing:
        doc = frappe.get_doc("FlowAgent Workflow", existing)
    else:
        doc = frappe.new_doc("FlowAgent Workflow")
        doc.workflow_name = name

    # Renames are handled by changing workflow_name to a different value
    new_name = data.get("workflow_name")
    if new_name and new_name != doc.workflow_name:
        doc.workflow_name = new_name

    doc.description = data.get("description") or ""
    doc.enabled = 1 if data.get("enabled") else 0

    trig = data.get("trigger") or {}
    doc.trigger_type = trig.get("type") or "Manual"
    doc.trigger_doctype = trig.get("doctype")
    doc.trigger_event = trig.get("event")
    doc.trigger_cron = trig.get("cron")
    doc.trigger_condition = trig.get("condition")

    doc.nodes_json = json.dumps(data.get("nodes") or [])
    doc.edges_json = json.dumps(data.get("edges") or [])
    doc.viewport_json = json.dumps(data.get("viewport") or {})

    runtime = data.get("runtime") or {}
    doc.on_error = runtime.get("on_error") or "Stop"
    doc.max_retries = cint(runtime.get("max_retries") or 0)
    doc.log_level = runtime.get("log_level") or "Info"
    doc.tags = data.get("tags")

    doc.flags.ignore_permissions = False
    doc.save()
    frappe.db.commit()

    # Verify the trigger index row got written. If the workflow is enabled
    # and DocType-event triggered, there MUST be a corresponding row in
    # FlowAgent Workflow Trigger Index for events to fire. This catches
    # cases where a hook ran but didn't write the row.
    index_status = _verify_index(doc)
    return {
        "name": doc.name,
        "modified": str(doc.modified),
        "index_status": index_status,
    }


def _verify_index(doc):
    """Return a small dict describing whether the trigger is actually
    registered for event firing. The Studio shows this in a toast after
    save so misconfigurations are immediately visible.
    """
    if not doc.enabled:
        return {"ok": True, "registered": False, "reason": "Workflow is disabled"}
    if doc.trigger_type != "DocType Event":
        return {
            "ok": True, "registered": True,
            "reason": f"{doc.trigger_type} trigger (no index row needed)",
        }
    row = frappe.db.get_value(
        "FlowAgent Workflow Trigger Index",
        {"workflow": doc.name},
        ["trigger_doctype", "trigger_event"],
        as_dict=True,
    )
    if row and row.trigger_doctype and row.trigger_event:
        return {
            "ok": True, "registered": True,
            "reason": f"Listening on {row.trigger_doctype} / {row.trigger_event}",
        }
    return {
        "ok": False, "registered": False,
        "reason": "Index row missing. Disable & re-enable, or check Diagnose.",
    }


@frappe.whitelist()
def delete_workflow(name: str):
    _check_perm()
    frappe.delete_doc("FlowAgent Workflow", name)
    frappe.db.commit()
    return {"deleted": name}


# -------------------------------------------------------------------------
# Running & runs
# -------------------------------------------------------------------------
@frappe.whitelist()
def run_workflow_now(name: str, payload: str | None = None, sync: int = 0):
    """Manually fire a workflow.

    sync=1 → run in this request and return the full result (good for the
              Studio's Run button so users see traces immediately).
    sync=0 → enqueue and return the queued run name.

    If the payload is shaped {"doctype": "...", "name": "..."} we hydrate
    the actual document and pass it as trigger.doc — this is how the
    Studio's "Run against a record" dialog works.
    """
    _check_perm()
    parsed_payload = {}
    if payload:
        try:
            parsed_payload = json.loads(payload) if isinstance(payload, str) else payload
        except json.JSONDecodeError:
            frappe.throw("payload must be valid JSON")

    # Hydrate a {doctype, name} shape into a full trigger payload
    if (isinstance(parsed_payload, dict)
            and parsed_payload.get("doctype")
            and parsed_payload.get("name")
            and "doc" not in parsed_payload):
        dt = parsed_payload["doctype"]
        dn = parsed_payload["name"]
        try:
            doc = frappe.get_doc(dt, dn)
            parsed_payload = {
                "doc": doc.as_dict(no_default_fields=False),
                "doc_name": doc.name,
                "doctype": dt,
                "event": "Manual",
                "user": frappe.session.user,
            }
        except frappe.DoesNotExistError:
            frappe.throw(f"{dt} {dn} does not exist")

    if cint(sync):
        from ..engine.runner import Runner
        run_name = Runner(
            workflow_name=name,
            trigger_source="studio_manual",
            payload=parsed_payload,
            user=frappe.session.user,
        ).execute()
        return get_run(run_name)

    # Async enqueue
    frappe.enqueue(
        "flowagent.engine.run_workflow_background",
        queue="default",
        timeout=600,
        workflow_name=name,
        trigger_source="studio_manual",
        payload=parsed_payload,
        user=frappe.session.user,
    )
    return {"queued": True}


@frappe.whitelist()
def get_run(run_name: str):
    """Return a single run with its full step trace."""
    _check_perm()
    doc = frappe.get_doc("FlowAgent Workflow Run", run_name)
    return {
        "name": doc.name,
        "workflow": doc.workflow,
        "status": doc.status,
        "trigger_source": doc.trigger_source,
        "started_at": str(doc.started_at) if doc.started_at else None,
        "ended_at": str(doc.ended_at) if doc.ended_at else None,
        "duration_ms": doc.duration_ms,
        "trigger_payload": _json_or_default(doc.trigger_payload, {}),
        "final_context": _json_or_default(doc.final_context, {}),
        "error_message": doc.error_message,
        "steps": [
            {
                "step_index": s.step_index,
                "node_id": s.node_id,
                "node_type": s.node_type,
                "node_label": s.node_label,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "input": _json_or_default(s.input_snapshot, None),
                "output": _json_or_default(s.output_snapshot, None),
                "error": s.error,
            }
            for s in doc.steps
        ],
    }


@frappe.whitelist()
def recent_runs(workflow: str | None = None, limit: int = 20):
    """Recent runs for the Stats / log panel."""
    _check_perm()
    filters = {}
    if workflow:
        filters["workflow"] = workflow
    return frappe.get_all(
        "FlowAgent Workflow Run",
        filters=filters,
        fields=["name", "workflow", "status", "trigger_source",
                "started_at", "duration_ms"],
        order_by="creation desc",
        limit=cint(limit),
    )


@frappe.whitelist()
def workflow_stats(workflow: str | None = None):
    """Aggregate stats for the Studio's Stats tab."""
    _check_perm()
    filters = {}
    if workflow:
        filters["workflow"] = workflow
    total = frappe.db.count("FlowAgent Workflow Run", filters)
    ok = frappe.db.count("FlowAgent Workflow Run", {**filters, "status": "Success"})
    err = frappe.db.count(
        "FlowAgent Workflow Run",
        {**filters, "status": ("in", ["Failed", "Timeout"])},
    )
    avg_ms = frappe.db.sql(
        "SELECT AVG(duration_ms) FROM `tabFlowAgent Workflow Run` "
        "WHERE status='Success'"
        + (" AND workflow=%s" if workflow else ""),
        (workflow,) if workflow else (),
    )
    avg = int(avg_ms[0][0] or 0) if avg_ms else 0
    return {"runs": total, "ok": ok, "err": err, "avg_ms": avg}


@frappe.whitelist()
def diagnose(workflow: str | None = None):
    """Health-check for the trigger pipeline.

    Returns a structured report the Studio can render. Use this when a
    workflow "doesn't fire" — it tells you whether the doc_events hook
    is wired, whether the trigger index has rows, and whether the
    workflow is enabled and well-formed.
    """
    _check_perm()
    report = {"checks": [], "ok": True}

    def check(name, ok, detail=""):
        report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            report["ok"] = False

    # 1. Is the wildcard doc_events hook loaded?
    try:
        hooks = frappe.get_hooks("doc_events", {}) or {}
        wildcard = hooks.get("*", {})
        has_hook = any(
            "flowagent.triggers.doctype_dispatcher.on_event" in (
                v if isinstance(v, list) else [v]
            )
            for v in wildcard.values()
        )
        check("doc_events wildcard registered", has_hook,
              "Restart bench (bench restart) if this is False after install."
              if not has_hook else "")
    except Exception as e:
        check("doc_events wildcard registered", False, str(e))

    # 2. Trigger index table populated?
    index_count = frappe.db.count("FlowAgent Workflow Trigger Index")
    check(f"Trigger index has {index_count} row(s)", index_count > 0,
          "If 0, no enabled DocType-Event workflows exist. Save and enable one."
          if index_count == 0 else "")

    # 3. Specific workflow diagnostics
    if workflow:
        try:
            wf = frappe.get_doc("FlowAgent Workflow", workflow)
            check(f"Workflow {workflow} exists", True)
            check(f"  enabled = {bool(wf.enabled)}", bool(wf.enabled),
                  "Toggle 'Enabled' and save."
                  if not wf.enabled else "")
            check(f"  trigger_type = {wf.trigger_type}", True)
            if wf.trigger_type == "DocType Event":
                check(f"  trigger_doctype = {wf.trigger_doctype or '∅'}",
                      bool(wf.trigger_doctype),
                      "Pick a DocType on the trigger node and save."
                      if not wf.trigger_doctype else "")
                check(f"  trigger_event = {wf.trigger_event or '∅'}",
                      bool(wf.trigger_event),
                      "Pick an event on the trigger node and save."
                      if not wf.trigger_event else "")
                # Index row?
                idx = frappe.get_all(
                    "FlowAgent Workflow Trigger Index",
                    filters={"workflow": workflow},
                    fields=["trigger_doctype", "trigger_event"],
                )
                check(f"  index row exists ({len(idx)})", len(idx) > 0,
                      "Re-save the workflow to rebuild the index."
                      if not idx else "")
        except frappe.DoesNotExistError:
            check(f"Workflow {workflow} exists", False)

    # 4. Scheduler running? (proxy: did any scheduled job log a heartbeat?)
    try:
        from frappe.utils.scheduler import is_scheduler_inactive
        scheduler_down = is_scheduler_inactive()
        check("Scheduler enabled", not scheduler_down,
              "Run: bench --site <site> enable-scheduler"
              if scheduler_down else "")
    except Exception:
        pass  # not all Frappe versions expose this

    # 5. Anthropic key set?
    settings = frappe.get_single("FlowAgent Settings")
    has_key = bool(settings.get_password("anthropic_api_key", raise_exception=False))
    if not has_key:
        has_key = bool(frappe.conf.get("anthropic_api_key"))
    check("Anthropic API key configured", has_key,
          "Set the key in FlowAgent Settings if you plan to use AI nodes."
          if not has_key else "")

    return report
    """Aggregate stats for the Studio's Stats tab."""
    _check_perm()
    filters = {}
    if workflow:
        filters["workflow"] = workflow
    total = frappe.db.count("FlowAgent Workflow Run", filters)
    ok = frappe.db.count("FlowAgent Workflow Run", {**filters, "status": "Success"})
    err = frappe.db.count(
        "FlowAgent Workflow Run",
        {**filters, "status": ("in", ["Failed", "Timeout"])},
    )
    avg_ms = frappe.db.sql(
        "SELECT AVG(duration_ms) FROM `tabFlowAgent Workflow Run` "
        "WHERE status='Success'"
        + (" AND workflow=%s" if workflow else ""),
        (workflow,) if workflow else (),
    )
    avg = int(avg_ms[0][0] or 0) if avg_ms else 0
    return {"runs": total, "ok": ok, "err": err, "avg_ms": avg}


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _json_or_default(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default
