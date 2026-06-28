# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class FlowAgentWorkflow(Document):
    """A FlowAgent workflow: a DAG of nodes that runs in response to a trigger."""

    # ---------- lifecycle ----------
    def validate(self):
        self._normalise_json("nodes_json", default=[])
        self._normalise_json("edges_json", default=[])
        self._normalise_json("viewport_json", default={"x": 0, "y": 0, "zoom": 1})
        self._validate_graph()
        self._validate_trigger()
        if self.trigger_type == "Webhook" and not self.webhook_path:
            self.webhook_path = frappe.generate_hash(length=16)

    def on_update(self):
        # Re-index trigger bindings so the dispatcher can find this workflow fast.
        # `on_update` is the correct Frappe controller hook that fires after any
        # save (insert or update). `after_save` is NOT a valid hook name despite
        # the misleading name — it never gets called.
        _rebuild_trigger_index(self)
        # Snapshot a version. We use a hash-based dedupe so spam-clicking Save
        # doesn't produce a thousand identical versions.
        _maybe_snapshot_version(self)

    def on_trash(self):
        frappe.db.delete("FlowAgent Workflow Trigger Index", {"workflow": self.name})
        # Cascade delete versions and runs
        for v in frappe.get_all("FlowAgent Workflow Version", filters={"workflow": self.name}, pluck="name"):
            frappe.delete_doc("FlowAgent Workflow Version", v, ignore_permissions=True, force=True)
        for run in frappe.get_all("FlowAgent Workflow Run", filters={"workflow": self.name}, pluck="name"):
            frappe.delete_doc("FlowAgent Workflow Run", run, ignore_permissions=True, force=True)

    # ---------- helpers ----------
    def _normalise_json(self, field: str, default):
        """Parse field as JSON; if blank or malformed, set to default-as-JSON."""
        raw = getattr(self, field, None)
        if not raw:
            setattr(self, field, json.dumps(default))
            return
        try:
            json.loads(raw)
        except (TypeError, ValueError):
            frappe.throw(f"{field} is not valid JSON", title="FlowAgent")

    def _validate_graph(self):
        nodes = json.loads(self.nodes_json or "[]")
        edges = json.loads(self.edges_json or "[]")
        node_ids = {n.get("id") for n in nodes}
        if len(node_ids) != len(nodes):
            frappe.throw("Workflow contains duplicate node IDs")
        for e in edges:
            if e.get("from") not in node_ids or e.get("to") not in node_ids:
                frappe.throw(f"Edge references unknown node: {e}")
        # We tolerate zero-node drafts so the user can save WIP, but block
        # enable-with-empty-graph because that would dispatch on every event
        # to a no-op.
        if self.enabled and not nodes:
            frappe.throw("Cannot enable an empty workflow — add at least a trigger node")

    def _validate_trigger(self):
        if self.trigger_type == "DocType Event":
            if not self.trigger_doctype:
                frappe.throw("DocType Event triggers require a DocType")
            if not self.trigger_event:
                frappe.throw("DocType Event triggers require an event")
        elif self.trigger_type == "Schedule":
            if not self.trigger_cron:
                frappe.throw("Schedule triggers require a cron expression")
            from croniter import croniter
            if not croniter.is_valid(self.trigger_cron):
                frappe.throw(f"Invalid cron expression: {self.trigger_cron}")

    # ---------- public API ----------
    def get_nodes(self):
        return json.loads(self.nodes_json or "[]")

    def get_edges(self):
        return json.loads(self.edges_json or "[]")


def _rebuild_trigger_index(wf: "FlowAgentWorkflow"):
    """Maintain the FlowAgent Workflow Trigger Index — a flat lookup table
    used by the doc_events dispatcher.

    Uses direct SQL writes to bypass any doctype-level validation that
    might silently fail (the wildcard doc_events listener depends on this
    row existing — silent failures here mean workflows just never fire).
    """
    try:
        frappe.db.delete("FlowAgent Workflow Trigger Index", {"workflow": wf.name})
    except Exception as e:
        frappe.log_error(
            title=f"FlowAgent: failed to clean old trigger index for {wf.name}",
            message=f"{type(e).__name__}: {e}",
        )
        # keep going — we still want to insert the fresh row

    if not wf.enabled:
        return
    if wf.trigger_type != "DocType Event":
        return
    if not (wf.trigger_doctype and wf.trigger_event):
        frappe.log_error(
            title=f"FlowAgent: cannot index {wf.name} — missing trigger fields",
            message=f"trigger_doctype={wf.trigger_doctype!r}\n"
                    f"trigger_event={wf.trigger_event!r}",
        )
        return

    try:
        idx = frappe.new_doc("FlowAgent Workflow Trigger Index")
        idx.workflow = wf.name
        idx.trigger_doctype = wf.trigger_doctype
        idx.trigger_event = wf.trigger_event
        idx.flags.ignore_permissions = True
        idx.flags.ignore_validate = True
        idx.flags.ignore_mandatory = False  # we WANT to know if these are empty
        idx.insert(ignore_permissions=True)
        # Force-commit so the row is visible to subsequent reads in the
        # same request (e.g. _verify_index).
        frappe.db.commit()
    except Exception as e:
        # Log the real reason so the user / developer can see it
        frappe.log_error(
            title=f"FlowAgent: failed to insert trigger index for {wf.name}",
            message=f"{type(e).__name__}: {e}\n"
                    f"workflow={wf.name}\n"
                    f"trigger_doctype={wf.trigger_doctype!r}\n"
                    f"trigger_event={wf.trigger_event!r}\n"
                    f"enabled={wf.enabled}",
        )
        # Re-raise so the caller (save_workflow) can surface it
        raise


def _maybe_snapshot_version(wf):
    """Snapshot the workflow into FlowAgent Workflow Version, but only if
    the graph actually changed since the last snapshot. This keeps the
    history meaningful — saving without edits doesn't create noise."""
    import hashlib

    # Fingerprint the current state. We hash the canonical JSON so equivalent
    # graphs (same keys, same order) produce the same digest.
    payload = json.dumps({
        "nodes": json.loads(wf.nodes_json or "[]"),
        "edges": json.loads(wf.edges_json or "[]"),
        "trigger_type": wf.trigger_type,
        "trigger_doctype": wf.trigger_doctype,
        "trigger_event": wf.trigger_event,
        "cron": wf.cron,
    }, sort_keys=True)
    digest = hashlib.sha1(payload.encode()).hexdigest()

    # Compare with the most recent version's digest (stored in version_label).
    last = frappe.get_all(
        "FlowAgent Workflow Version",
        filters={"workflow": wf.name},
        fields=["name", "version_label"],
        order_by="creation desc",
        limit=1,
    )
    if last and last[0].version_label and last[0].version_label.endswith(digest[:8]):
        return  # no change since last snapshot

    # Count existing versions for a friendly label (v1, v2, ...)
    count = frappe.db.count("FlowAgent Workflow Version", {"workflow": wf.name})
    label = f"v{count + 1}-{digest[:8]}"

    try:
        ver = frappe.new_doc("FlowAgent Workflow Version")
        ver.workflow = wf.name
        ver.version_label = label
        ver.created_by_user = frappe.session.user
        ver.message = ""  # blank for auto-snapshots; user can edit later
        ver.nodes_json = wf.nodes_json
        ver.edges_json = wf.edges_json
        ver.trigger_json = json.dumps({
            "type": wf.trigger_type,
            "doctype": wf.trigger_doctype,
            "event": wf.trigger_event,
            "cron": wf.cron,
        })
        ver.viewport_json = wf.viewport_json or "{}"
        ver.insert(ignore_permissions=True)
    except Exception as e:
        # Versioning is best-effort; don't break the save if it fails.
        frappe.log_error(
            title=f"FlowAgent: failed to snapshot version for {wf.name}",
            message=f"{type(e).__name__}: {e}",
        )
