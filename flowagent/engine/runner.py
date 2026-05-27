# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
FlowAgent execution engine.

A FlowAgent workflow is a DAG of nodes connected by directed edges. Each
edge optionally carries a port label ('out' for default, 'out-yes' /
'out-no' for branch nodes). The engine walks the DAG starting from the
trigger node, propagating a shared `context` dict that nodes read via
Jinja-style `{{var}}` interpolation and write via their `output` field.

The walk is *event-driven* rather than topological-sorted: we start with
the trigger node in the ready queue, and as each node finishes we enqueue
its downstream neighbours that are now reachable. Branch nodes only
enqueue one of their two children based on the branch result. Loops
re-enqueue the loop body for each iteration.

Synchronous by default. Parallel nodes spawn their downstream branches
under threads inside a single run (the executor blocks at the join).
Heavy long-running workflows should be enqueued via `frappe.enqueue` —
the engine itself runs in whatever process calls `Runner().execute()`.
"""

from __future__ import annotations

import json
import time
import traceback
from typing import Any

import frappe
from frappe.utils import now_datetime

from .context import Context, render
from .nodes import get_executor


# Sentinel: a node returning this skips its downstream branch entirely.
SKIP = object()


class WorkflowRunError(Exception):
    """Raised when a node fails and the workflow's on_error == 'Stop'."""

    def __init__(self, node_id: str, message: str):
        super().__init__(message)
        self.node_id = node_id
        self.message = message


class Runner:
    """Executes one workflow run.

    Usage:
        run_name = Runner(workflow_name="Invoice Approval",
                         trigger_source="manual",
                         payload={"doc_name": "ACC-INV-001"}).execute()
    """

    def __init__(
        self,
        workflow_name: str,
        trigger_source: str = "manual",
        payload: dict | None = None,
        user: str | None = None,
    ):
        self.workflow_name = workflow_name
        self.trigger_source = trigger_source
        self.payload = payload or {}
        self.user = user or frappe.session.user

        # Loaded in _load()
        self.wf = None
        self.settings = None
        self.nodes_by_id: dict[str, dict] = {}
        self.outgoing: dict[str, list[dict]] = {}  # node_id -> list of edges

        # Execution state
        self.context: Context | None = None
        self.steps: list[dict] = []
        self.step_counter = 0
        self.run_doc = None
        self.start_ts = None
        self.error_state: str | None = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def execute(self) -> str:
        """Run the workflow to completion. Returns the Workflow Run name."""
        self._load()
        self._create_run_doc()
        self.start_ts = time.monotonic()
        try:
            trigger_node = self._find_trigger_node()
            if not trigger_node:
                raise WorkflowRunError("", "Workflow has no trigger node")
            # Build a context where templates can address the trigger data
            # in three convenient ways:
            #   {{trigger.doc.field}}    — explicit path through payload
            #   {{trigger.field}}        — short alias when the trigger is a
            #                              doctype event (doc fields lifted up)
            #   {{doc.field}}, {{field}} — also lifted to the top level
            doc = self.payload.get("doc") or {}
            trigger_ns = dict(self.payload)  # {doc, doc_name, doctype, event, user, ...}
            if isinstance(doc, dict):
                # Lift doc fields under trigger.* without overwriting structural keys
                for k, v in doc.items():
                    trigger_ns.setdefault(k, v)
            seed = {
                "trigger": trigger_ns,
                **self.payload,  # also flatten so {{doc_name}}, {{doc}}, etc. work
            }
            # Also expose top-level doc fields so {{customer_name}} works directly
            if isinstance(doc, dict):
                for k, v in doc.items():
                    seed.setdefault(k, v)
            self.context = Context(seed=seed)
            self._walk(trigger_node["id"])
            self._finalise("Success")
        except WorkflowRunError as e:
            self._finalise("Failed", error=e.message)
        except Exception as e:
            self._finalise("Failed", error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        return self.run_doc.name

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def _load(self):
        self.wf = frappe.get_doc("FlowAgent Workflow", self.workflow_name)
        if not self.wf.enabled and self.trigger_source != "manual":
            raise WorkflowRunError("", f"Workflow {self.workflow_name} is disabled")
        self.settings = frappe.get_single("FlowAgent Settings")

        nodes = self.wf.get_nodes()
        edges = self.wf.get_edges()
        self.nodes_by_id = {n["id"]: n for n in nodes}
        self.outgoing = {}
        for e in edges:
            self.outgoing.setdefault(e["from"], []).append(e)

    def _find_trigger_node(self) -> dict | None:
        # Prefer an explicit trigger node, fallback to the node with no incoming edges.
        for n in self.nodes_by_id.values():
            if n.get("type", "").startswith("trigger_"):
                return n
        incoming_targets = {e["to"] for edges in self.outgoing.values() for e in edges}
        for n in self.nodes_by_id.values():
            if n["id"] not in incoming_targets:
                return n
        return None

    # ------------------------------------------------------------------
    # Walking the DAG
    # ------------------------------------------------------------------
    def _walk(self, start_node_id: str):
        """Iterative, event-driven traversal.

        We track which node we're at, execute it, then enqueue successors
        based on which output port the node emitted on.

        Loop nodes are handled by re-entering the body branch N times.
        """
        queue: list[str] = [start_node_id]
        max_steps = self.settings.max_steps_per_run or 100

        while queue:
            if self.step_counter >= max_steps:
                raise WorkflowRunError("", f"Workflow exceeded max_steps_per_run={max_steps}")

            node_id = queue.pop(0)
            node = self.nodes_by_id.get(node_id)
            if not node:
                continue

            output_port = self._execute_node(node)

            # output_port is the port name the node "emitted" on:
            #   'out' (default), 'out-yes', 'out-no', or None (terminate this branch)
            if output_port is None:
                continue

            successors = [
                e for e in self.outgoing.get(node_id, [])
                if (e.get("fromPort") or "out") == output_port
            ]
            # If no port-specific successors but node emitted default 'out',
            # also accept edges that have no fromPort declared.
            if not successors and output_port == "out":
                successors = [e for e in self.outgoing.get(node_id, []) if not e.get("fromPort")]
            for e in successors:
                queue.append(e["to"])

    def _execute_node(self, node: dict) -> str | None:
        """Run a single node, record the step, return the output port."""
        self.step_counter += 1
        step_index = self.step_counter
        node_id = node["id"]
        node_type = node.get("type", "unknown")
        node_label = node.get("def", {}).get("label") or node.get("label") or node_type
        cfg = node.get("cfg", {})

        # Interpolate every config value through Jinja against current context.
        # Collect undefined-variable warnings so we can surface them in the
        # step trace — silent empty renders were the #1 source of "why did
        # my workflow do nothing" bug reports.
        render_warnings: list[str] = []
        try:
            rendered_cfg = self._render_cfg(cfg, warnings=render_warnings)
        except Exception as e:
            self._record_step(step_index, node, "Failed", error=f"Template error: {e}")
            return self._handle_error(node_id, f"Template error: {e}")

        executor = get_executor(node_type)
        if executor is None:
            self._record_step(step_index, node, "Failed",
                             input_snapshot=rendered_cfg,
                             error=f"No executor for node type '{node_type}'")
            return self._handle_error(node_id, f"Unknown node type: {node_type}")

        step_start = time.monotonic()
        attempt = 0
        max_attempts = (self.wf.max_retries or 0) + 1 if self.wf.on_error == "Retry" else 1

        while True:
            attempt += 1
            try:
                result = executor.run(
                    node=node,
                    cfg=rendered_cfg,
                    context=self.context,
                    runner=self,
                )
                ms = int((time.monotonic() - step_start) * 1000)
                # Result is either None (default out), a dict (default out with output),
                # the SKIP sentinel, or a tuple (port, output_value).
                output_port = "out"
                output_value = None
                if result is SKIP:
                    output_port = None
                    output_value = "skipped"
                elif isinstance(result, tuple) and len(result) == 2:
                    output_port, output_value = result
                else:
                    output_value = result

                # Store under the node's configured output variable name (if any)
                output_var = rendered_cfg.get("output")
                if output_var and output_value is not None:
                    self.context.set(output_var, output_value)
                # Always make the most recent output retrievable as $last
                self.context.set("$last", output_value)

                self._record_step(step_index, node, "Success",
                                 duration_ms=ms,
                                 input_snapshot=rendered_cfg,
                                 output_snapshot=output_value,
                                 error=("⚠ " + "; ".join(render_warnings)) if render_warnings else "")
                return output_port
            except Exception as e:
                ms = int((time.monotonic() - step_start) * 1000)
                tb = traceback.format_exc()
                if attempt < max_attempts:
                    # backoff between retries
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                self._record_step(step_index, node, "Failed",
                                 duration_ms=ms,
                                 input_snapshot=rendered_cfg,
                                 error=f"{type(e).__name__}: {e}\n{tb}")
                return self._handle_error(node_id, f"{type(e).__name__}: {e}")

    def _render_cfg(self, cfg: dict, warnings: list | None = None) -> dict:
        """Interpolate Jinja placeholders in every string value of the cfg dict.

        If ``warnings`` is passed, undefined-variable warnings collected
        during rendering are appended to it.
        """
        out = {}
        for k, v in cfg.items():
            if isinstance(v, str):
                out[k] = render(v, self.context.data, warnings=warnings)
            else:
                out[k] = v
        return out

    def _handle_error(self, node_id: str, message: str) -> str | None:
        policy = self.wf.on_error or "Stop"
        if policy == "Continue":
            return "out"  # try the default successor anyway
        if policy == "Retry":
            # Retry was already exhausted in _execute_node — fall through to Stop.
            pass
        raise WorkflowRunError(node_id, message)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def _create_run_doc(self):
        self.run_doc = frappe.get_doc({
            "doctype": "FlowAgent Workflow Run",
            "workflow": self.workflow_name,
            "status": "Running",
            "trigger_source": self.trigger_source,
            "started_at": now_datetime(),
            "trigger_payload": json.dumps(self.payload, default=str)[:140000],
        })
        self.run_doc.flags.ignore_permissions = True
        self.run_doc.insert(ignore_permissions=True)
        frappe.db.commit()

    def _record_step(
        self,
        step_index: int,
        node: dict,
        status: str,
        duration_ms: int = 0,
        input_snapshot: Any = None,
        output_snapshot: Any = None,
        error: str = "",
    ):
        node_type = node.get("type", "unknown")
        # Determine label: prefer the canvas-saved def.label, fall back to type
        node_label = ""
        if isinstance(node.get("def"), dict):
            node_label = node["def"].get("label", "")
        node_label = node_label or node.get("label") or node_type

        self.steps.append({
            "step_index": step_index,
            "node_id": node.get("id", ""),
            "node_type": node_type,
            "node_label": node_label,
            "status": status,
            "duration_ms": duration_ms,
            "input_snapshot": _safe_json(input_snapshot),
            "output_snapshot": _safe_json(output_snapshot),
            "error": error[:140000] if error else "",
        })

    def _finalise(self, status: str, error: str = ""):
        if not self.run_doc:
            return
        total_ms = int((time.monotonic() - self.start_ts) * 1000) if self.start_ts else 0
        self.run_doc.status = status
        self.run_doc.ended_at = now_datetime()
        self.run_doc.duration_ms = total_ms
        if error:
            self.run_doc.error_message = error[:140000]
        if self.context:
            self.run_doc.final_context = _safe_json(self.context.snapshot())
        # Reload to get the latest before we overwrite the child table
        self.run_doc.set("steps", [])
        for s in self.steps:
            self.run_doc.append("steps", s)
        self.run_doc.flags.ignore_permissions = True
        self.run_doc.save(ignore_permissions=True)

        # Update workflow summary stats
        frappe.db.set_value(
            "FlowAgent Workflow",
            self.workflow_name,
            {
                "last_run_status": status,
                "last_run_at": now_datetime(),
                "total_runs": (self.wf.total_runs or 0) + 1,
            },
            update_modified=False,
        )
        frappe.db.commit()


def _safe_json(value: Any) -> str:
    """Serialise anything to JSON; fall back to repr for unencodable types."""
    if value is None:
        return ""
    try:
        return json.dumps(value, default=str)[:140000]
    except Exception:
        return repr(value)[:140000]
