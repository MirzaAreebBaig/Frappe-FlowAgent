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
    frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Cross-process visibility: workflow was just saved and we're about to verify the trigger index row exists by querying it via a fresh frappe.db.exists; without commit the new row isn't visible to subsequent reads in this session.

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

    If the row is missing despite the workflow being enabled and properly
    configured, this attempts one auto-recovery rebuild so a transient
    failure in after_save doesn't leave the user stuck.
    """
    if not doc.enabled:
        return {"ok": True, "registered": False, "reason": "Workflow is disabled"}
    if doc.trigger_type != "DocType Event":
        return {
            "ok": True, "registered": True,
            "reason": f"{doc.trigger_type} trigger (no index row needed)",
        }

    # Workflow itself must have populated trigger fields, otherwise it's
    # a frontend bug we should surface plainly.
    if not doc.trigger_doctype:
        return {
            "ok": False, "registered": False,
            "reason": "trigger_doctype is empty on the workflow. Re-pick "
                      "the DocType on the trigger node (don't just type — "
                      "select from the autocomplete) and save again.",
        }
    if not doc.trigger_event:
        return {
            "ok": False, "registered": False,
            "reason": "trigger_event is empty on the workflow. Pick an "
                      "event from the dropdown on the trigger node.",
        }

    def _lookup_row():
        return frappe.db.get_value(
            "FlowAgent Workflow Trigger Index",
            {"workflow": doc.name},
            ["trigger_doctype", "trigger_event"],
            as_dict=True,
        )

    row = _lookup_row()
    if row and row.trigger_doctype and row.trigger_event:
        # Index row exists. But: hooks.py builds doc_events at module
        # load time. If the user just added a trigger on a DocType that
        # wasn't in doc_events when the worker started, the dispatcher
        # for THIS DocType isn't wired yet and won't fire until restart.
        restart_needed = _restart_required_for(row.trigger_doctype, row.trigger_event)
        if restart_needed:
            return {
                "ok": True, "registered": True,
                "restart_needed": True,
                "reason": (
                    f"Listening on {row.trigger_doctype} / {row.trigger_event}. "
                    f"Run `bench restart` on the server to activate this trigger — "
                    f"FlowAgent only wires DocTypes seen at worker startup."
                ),
            }
        return {
            "ok": True, "registered": True,
            "restart_needed": False,
            "reason": f"Listening on {row.trigger_doctype} / {row.trigger_event}",
        }

    # Auto-recovery: try one explicit rebuild. This catches cases where
    # after_save ran in a way that didn't persist (e.g. nested savepoint
    # rollback). Anything still failing here is a real bug, captured in
    # the error log.
    try:
        from ..flowagent_core.doctype.flowagent_workflow.flowagent_workflow import (
            _rebuild_trigger_index,
        )
        _rebuild_trigger_index(doc)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Worker queue handoff: trigger index just got rebuilt; flush to DB so the dispatcher running in other worker processes can see the new bindings immediately.
        row = _lookup_row()
        if row and row.trigger_doctype and row.trigger_event:
            return {
                "ok": True, "registered": True,
                "reason": f"Listening on {row.trigger_doctype} / {row.trigger_event} (auto-recovered)",
            }
    except Exception as e:
        frappe.log_error(
            title="FlowAgent: auto-recovery rebuild failed",
            message=f"{type(e).__name__}: {e}\nWorkflow: {doc.name}\n"
                    f"trigger_doctype={doc.trigger_doctype!r}\n"
                    f"trigger_event={doc.trigger_event!r}\n"
                    f"enabled={doc.enabled}",
        )
        return {
            "ok": False, "registered": False,
            "reason": f"Index rebuild failed: {type(e).__name__}: {e}",
        }

    return {
        "ok": False, "registered": False,
        "reason": "Index row could not be created. Check Error Log for details.",
    }


def _restart_required_for(trigger_doctype: str, trigger_event: str) -> bool:
    """Check whether the current worker's loaded doc_events covers this
    (DocType, event) pair. Returns True if a `bench restart` is needed
    for the trigger to actually start firing.

    Frappe's doc_events are loaded from hooks.py once at app discovery
    time. FlowAgent builds them dynamically from the trigger index — so
    when a user adds a new trigger DocType, hooks.py needs to be
    re-evaluated (which happens on bench restart) for that DocType to
    be wired into the global event dispatch.
    """
    try:
        # Map FlowAgent event labels to Frappe controller hook names.
        # Kept in sync with the same map in hooks.py:_build_doc_events.
        event_map = {
            "After Insert": "after_insert",
            "After Save":   "on_update",
            "After Submit": "on_submit",
            "After Cancel": "on_cancel",
            "After Delete": "on_trash",
            "On Change":    "on_change",
        }
        hook_name = event_map.get(trigger_event)
        if not hook_name:
            return False  # Not a doctype event we'd register anyway

        # frappe.get_hooks returns the merged hooks across all apps.
        # We ask specifically for our handler under (doc_events, dt, hook).
        handlers = frappe.get_hooks(
            "doc_events", default={}, app_name="flowagent"
        )
        if not isinstance(handlers, dict):
            return True  # Unexpected shape; assume restart needed
        dt_handlers = handlers.get(trigger_doctype) or {}
        return "flowagent.triggers.doctype_dispatcher.on_event" not in (
            dt_handlers.get(hook_name) or []
            if isinstance(dt_handlers.get(hook_name), list)
            else [dt_handlers.get(hook_name)] if dt_handlers.get(hook_name) else []
        )
    except Exception:
        # If anything goes wrong, err on the side of "restart needed"
        # so the user gets the heads-up rather than a silent failure.
        return True


@frappe.whitelist()
def delete_workflow(name: str):
    _check_perm()
    frappe.delete_doc("FlowAgent Workflow", name)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Cross-process visibility: workflow was deleted; commit so any in-flight dispatchers / scheduler ticks don't try to load it as if it still exists.
    return {"deleted": name}


# -------------------------------------------------------------------------
# Running & runs
# -------------------------------------------------------------------------
@frappe.whitelist()
def run_workflow_now(name: str, payload: str | None = None, sync: int = 0, dry_run: int = 0):
    """Manually fire a workflow.

    sync=1 → run in this request and return the full result (good for the
              Studio's Run button so users see traces immediately).
    sync=0 → enqueue and return the queued run name.

    dry_run=1 → write nodes (Frappe create/update/submit/script) and
                integrations (email, WhatsApp, Slack, HTTP POST, Sheets writes,
                Razorpay create) DO NOT execute. AI nodes, fetches, and reads
                still run so you can preview the full data flow safely.

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

    is_dry = bool(cint(dry_run))
    trigger_source = "studio_dry_run" if is_dry else "studio_manual"

    if cint(sync):
        from ..engine.runner import Runner
        run_name = Runner(
            workflow_name=name,
            trigger_source=trigger_source,
            payload=parsed_payload,
            user=frappe.session.user,
            dry_run=is_dry,
        ).execute()
        return get_run(run_name)

    # Async enqueue. Pre-create the Run doc here (and commit) so the
    # client receives its name immediately and can start polling for
    # streamed step updates. The background runner adopts it via
    # existing_run_name.
    run_doc = frappe.get_doc({
        "doctype": "FlowAgent Workflow Run",
        "workflow": name,
        "status": "Queued",
        "trigger_source": trigger_source,
        "started_at": frappe.utils.now_datetime(),
        "trigger_payload": json.dumps(parsed_payload, default=str)[:140000],
    })
    run_doc.flags.ignore_permissions = True
    run_doc.insert(ignore_permissions=True)
    frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Worker queue handoff: the run doc was just created and we're about to frappe.enqueue a background job that will load it by name. Without commit the worker would race and not find the row.

    frappe.enqueue(
        "flowagent.engine.run_workflow_background",
        queue="default",
        timeout=600,
        workflow_name=name,
        trigger_source=trigger_source,
        payload=parsed_payload,
        user=frappe.session.user,
        dry_run=is_dry,
        existing_run_name=run_doc.name,
    )
    return {"queued": True, "run_name": run_doc.name}


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
        "ai_calls": doc.get("ai_calls") or 0,
        "ai_tokens_in": doc.get("ai_tokens_in") or 0,
        "ai_tokens_out": doc.get("ai_tokens_out") or 0,
        "ai_cost_usd": float(doc.get("ai_cost_usd") or 0),
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
    """Aggregate stats for the Studio's Stats tab.

    Returns:
        runs, ok, err, avg_ms — totals
        last_50 — list of {status, duration_ms} for the most recent 50 runs,
                  oldest first (so the sparkline draws left-to-right)
        top_errors — list of {error, count} for the most common failure
                     messages (first line only)
    """
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

    # Last 50 runs for sparkline (oldest first for left-to-right display)
    last_50_rows = frappe.get_all(
        "FlowAgent Workflow Run",
        filters=filters,
        fields=["status", "duration_ms"],
        order_by="creation desc",
        limit=50,
    )
    last_50 = list(reversed(last_50_rows))

    # Top error messages (first line, no traceback)
    top_errors = []
    if err:
        error_rows = frappe.get_all(
            "FlowAgent Workflow Run",
            filters={**filters, "status": ("in", ["Failed", "Timeout"]), "error_message": ("is", "set")},
            fields=["error_message"],
            order_by="creation desc",
            limit=200,
        )
        counts: dict[str, int] = {}
        for r in error_rows:
            first_line = (r.error_message or "").split("\n")[0][:140].strip()
            if not first_line:
                continue
            counts[first_line] = counts.get(first_line, 0) + 1
        top_errors = [
            {"error": e, "count": c}
            for e, c in sorted(counts.items(), key=lambda x: -x[1])[:3]
        ]

    # Cumulative AI usage across all runs of this workflow.
    where_clause = ""
    params: tuple = ()
    if workflow:
        where_clause = "WHERE workflow=%s"
        params = (workflow,)
    usage_row = frappe.db.sql(
        f"SELECT COALESCE(SUM(ai_calls), 0), COALESCE(SUM(ai_tokens_in), 0), "
        f"       COALESCE(SUM(ai_tokens_out), 0), COALESCE(SUM(ai_cost_usd), 0) "
        f"FROM `tabFlowAgent Workflow Run` {where_clause}",
        params,
    )
    if usage_row and usage_row[0]:
        ai_calls_total, ai_in_total, ai_out_total, ai_cost_total = usage_row[0]
    else:
        ai_calls_total = ai_in_total = ai_out_total = ai_cost_total = 0

    return {
        "runs": total, "ok": ok, "err": err, "avg_ms": avg,
        "last_50": last_50, "top_errors": top_errors,
        "ai_calls_total":  int(ai_calls_total or 0),
        "ai_tokens_total": int((ai_in_total or 0) + (ai_out_total or 0)),
        "ai_cost_total":   float(ai_cost_total or 0),
    }


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


# =================================================================
# Versioning
# =================================================================
@frappe.whitelist()
def list_versions(workflow: str):
    """Return all versions of a workflow, most recent first."""
    _check_perm()
    if not workflow:
        return []
    rows = frappe.get_all(
        "FlowAgent Workflow Version",
        filters={"workflow": workflow},
        fields=["name", "version_label", "message", "created_by_user", "creation"],
        order_by="creation desc",
        limit=50,
    )
    # Count nodes per version for the UI (cheap-ish — one query each, capped at 50)
    for r in rows:
        nodes_json = frappe.db.get_value("FlowAgent Workflow Version", r.name, "nodes_json")
        try:
            r["node_count"] = len(json.loads(nodes_json or "[]"))
        except Exception:
            r["node_count"] = 0
    return rows


@frappe.whitelist()
def get_version(version: str):
    """Fetch one version's full snapshot."""
    _check_perm()
    v = frappe.get_doc("FlowAgent Workflow Version", version)
    return {
        "name": v.name,
        "workflow": v.workflow,
        "version_label": v.version_label,
        "message": v.message,
        "created_by_user": v.created_by_user,
        "creation": v.creation,
        "nodes": json.loads(v.nodes_json or "[]"),
        "edges": json.loads(v.edges_json or "[]"),
        "trigger": json.loads(v.trigger_json or "{}"),
        "viewport": json.loads(v.viewport_json or "{}"),
    }


@frappe.whitelist()
def restore_version(version: str):
    """Restore a version's snapshot onto its parent workflow.

    This creates a new snapshot (the pre-restore state) automatically via
    the workflow's after_save hook, so restoration is itself reversible.
    """
    _check_perm()
    v = frappe.get_doc("FlowAgent Workflow Version", version)
    wf = frappe.get_doc("FlowAgent Workflow", v.workflow)
    # Copy snapshot fields back. We don't touch enabled/workflow_name etc
    # so a restore is purely about the graph, not the meta.
    trig = json.loads(v.trigger_json or "{}")
    wf.nodes_json = v.nodes_json
    wf.edges_json = v.edges_json
    wf.viewport_json = v.viewport_json or wf.viewport_json
    if trig.get("type"):
        wf.trigger_type = trig.get("type")
        wf.trigger_doctype = trig.get("doctype") or ""
        wf.trigger_event = trig.get("event") or ""
        wf.cron = trig.get("cron") or ""
    wf.save()
    return {"restored": True, "workflow": wf.name}


@frappe.whitelist()
def annotate_version(version: str, message: str):
    """Set/update the message field on a version. Lets users add a note
    like 'before refactor' after the fact."""
    _check_perm()
    frappe.db.set_value("FlowAgent Workflow Version", version, "message", message)
    return {"ok": True}


# =================================================================
# Bulk re-trigger
# =================================================================
@frappe.whitelist()
def bulk_retrigger(workflow: str, doctype: str | None = None,
                   from_date: str | None = None, to_date: str | None = None,
                   filters_json: str | None = None,
                   max_docs: int = 100, dry_run: int = 0):
    """Run a workflow against a batch of historic documents.

    Use case: you ship a new workflow that AI-classifies new Leads, and you
    want to apply it retroactively to last month's leads. Without this,
    you'd have to manually re-save each one or write a script.

    Defaults to dry_run=1 (preview) so users see what would happen first.

    Args:
        workflow: The Workflow doc name to fire.
        doctype: DocType to scan. Defaults to the workflow's trigger doctype.
        from_date / to_date: Inclusive bounds on `creation`. Optional.
        filters_json: Extra Frappe filter conditions as JSON.
        max_docs: Hard cap to prevent runaway batches. Capped at 500.
        dry_run: If 1, runs each workflow execution in dry-run mode too.

    Returns:
        {"queued": N, "preview": [first 10 doc names], "doctype": ..., "dry_run": ...}
    """
    _check_perm()
    cap = min(500, int(max_docs or 100))
    wf = frappe.get_doc("FlowAgent Workflow", workflow)
    target_dt = doctype or wf.trigger_doctype
    if not target_dt:
        frappe.throw(
            "Cannot bulk re-trigger: workflow has no doctype trigger and "
            "no doctype was specified."
        )

    # Build filters. Date bounds compose cleanly:
    #   from + to     →  "between" range
    #   from only     →  ">="
    #   to only       →  "<="
    # Any user-supplied filters_json takes priority on other fields; only the
    # "creation" key is overridden when a date range is also provided.
    filters = {}
    if filters_json:
        try:
            filters = json.loads(filters_json)
        except json.JSONDecodeError:
            frappe.throw("filters_json must be valid JSON")
    if from_date and to_date:
        filters["creation"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["creation"] = [">=", from_date]
    elif to_date:
        filters["creation"] = ["<=", to_date]

    docs = frappe.get_all(target_dt, filters=filters, pluck="name", limit=cap, order_by="creation asc")

    is_dry = bool(cint(dry_run))

    # Enqueue each one
    for dn in docs:
        try:
            doc = frappe.get_doc(target_dt, dn)
            payload = {
                "doc": doc.as_dict(no_default_fields=False),
                "doc_name": dn,
                "doctype": target_dt,
                "event": "Bulk Retrigger",
                "user": frappe.session.user,
            }
            frappe.enqueue(
                "flowagent.engine.run_workflow_background",
                queue="long",  # batch runs go to the long-running queue
                timeout=600,
                workflow_name=workflow,
                trigger_source="bulk_retrigger",
                payload=payload,
                user=frappe.session.user,
                dry_run=is_dry,
            )
        except Exception as e:
            frappe.log_error(
                title=f"FlowAgent bulk_retrigger: failed to enqueue {target_dt}/{dn}",
                message=str(e),
            )

    return {
        "queued": len(docs),
        "preview": docs[:10],
        "doctype": target_dt,
        "dry_run": is_dry,
        "cap": cap,
    }


@frappe.whitelist()
def preview_retrigger_count(workflow: str, doctype: str | None = None,
                            from_date: str | None = None, to_date: str | None = None,
                            filters_json: str | None = None):
    """Count how many docs would be re-triggered, without queuing anything.
    Used by the Studio UI to show "this will run against N docs"."""
    _check_perm()
    wf = frappe.get_doc("FlowAgent Workflow", workflow)
    target_dt = doctype or wf.trigger_doctype
    if not target_dt:
        return {"count": 0, "doctype": None}
    filters = {}
    if filters_json:
        try:
            filters = json.loads(filters_json)
        except json.JSONDecodeError:
            pass
    if from_date and to_date:
        filters["creation"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["creation"] = [">=", from_date]
    elif to_date:
        filters["creation"] = ["<=", to_date]
    count = frappe.db.count(target_dt, filters)
    return {"count": count, "doctype": target_dt}
