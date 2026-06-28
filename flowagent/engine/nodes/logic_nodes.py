# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Logic nodes: condition, wait, loop, parallel.
"""

from __future__ import annotations

import json
import time

import frappe

from . import BaseExecutor, node


@node("logic_condition")
class ConditionNode(BaseExecutor):
    """Boolean branch. cfg.expr is a string expression that must evaluate
    to truthy / falsy under the current context.

    We do NOT use Python's eval — instead a tiny safe evaluator that
    supports comparisons, and/or, and dotted variable lookup. For
    anything complex use a tf_code node first.
    """

    def run(self, *, node, cfg, context, runner):
        expr = (cfg.get("expr") or "").strip()
        if not expr:
            return ("out-yes", True)  # vacuous truth
        try:
            result = _safe_eval(expr, context.data)
        except Exception as e:
            frappe.throw(f"Condition error: {e}")
        port = "out-yes" if result else "out-no"
        return (port, bool(result))


@node("logic_wait")
class WaitNode(BaseExecutor):
    """Sleep for N seconds. cfg.seconds — int."""

    def run(self, *, node, cfg, context, runner):
        sec = float(cfg.get("seconds") or 0)
        # Cap at 60s for synchronous runs — anything longer should be a scheduled workflow
        sec = min(sec, 60)
        if sec > 0:
            time.sleep(sec)
        return {"waited_seconds": sec}


@node("logic_loop")
class LoopNode(BaseExecutor):
    """Iterate over a list in context, re-firing downstream nodes for each item.

    cfg:
      items     — Jinja-rendered, expected to resolve to a list (or JSON list string)
      item_var  — variable name to expose each item under (default 'item')
      max_items — safety cap (default 100)

    Implementation note: rather than re-engineering the queue model, the
    loop node executes its downstream subgraph synchronously per item by
    cloning a Runner-like context push/pop. For a v1 we implement the
    simpler shape: the loop node iterates and stuffs each item into the
    context, and we expect a *single* downstream chain that gets walked
    once per item. The chain is the path from the loop's `out` port.
    """

    def run(self, *, node, cfg, context, runner):
        from ..runner import SKIP

        items = cfg.get("items")
        if isinstance(items, str):
            # Try parsing as JSON
            import json as _json
            try:
                items = _json.loads(items)
            except _json.JSONDecodeError:
                # Comma-split fallback
                items = [s.strip() for s in items.split(",") if s.strip()]
        if not isinstance(items, list):
            items = [items] if items is not None else []

        item_var = cfg.get("item_var") or "item"
        max_items = int(cfg.get("max_items") or 100)
        items = items[:max_items]

        # Walk the downstream subgraph once per item.
        successors = runner.outgoing.get(node["id"], [])
        downstream_ids = [e["to"] for e in successors if (e.get("fromPort") or "out") == "out"]

        results = []
        for i, it in enumerate(items):
            context.set(item_var, it)
            context.set(f"{item_var}_index", i)
            for ds in downstream_ids:
                runner._walk(ds)
            results.append(it)

        # We've already walked the downstream chains ourselves — tell the
        # outer runner to not walk them again.
        return SKIP if downstream_ids else results


@node("logic_parallel")
class ParallelNode(BaseExecutor):
    """Fan-out: all out edges are taken simultaneously by the runner's
    natural breadth-first behaviour. This node is mostly a marker — the
    runner already enqueues all matching successors.

    We just record the fan-out width as the output."""

    def run(self, *, node, cfg, context, runner):
        successors = runner.outgoing.get(node["id"], [])
        return {"branches": len(successors)}


# -------------------------------------------------------------------------
# Safe expression evaluator
# -------------------------------------------------------------------------
def _safe_eval(expr: str, data: dict):
    """Evaluate a comparison/boolean expression against the context.

    Supports:
      - Variables: any dotted path
      - Literals: numbers, "strings", true/false, null
      - Comparisons: == != < <= > >=
      - Boolean: and, or, not
      - 'in' for membership
      - Parentheses

    Uses `ast` to parse, then walks the tree, refusing anything outside
    the allowed node types. Much safer than eval().
    """
    import ast

    # Normalise word literals to Python syntax
    expr_py = expr.replace("&&", " and ").replace("||", " or ")
    expr_py = _replace_word(expr_py, "true", "True")
    expr_py = _replace_word(expr_py, "false", "False")
    expr_py = _replace_word(expr_py, "null", "None")

    tree = ast.parse(expr_py, mode="eval")

    def _ev(node):
        if isinstance(node, ast.Expression):
            return _ev(node.body)
        if isinstance(node, ast.BoolOp):
            vals = [_ev(v) for v in node.values]
            if isinstance(node.op, ast.And): return all(vals)
            if isinstance(node.op, ast.Or):  return any(vals)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _ev(node.operand)
        if isinstance(node, ast.Compare):
            left = _ev(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = _ev(comp)
                if isinstance(op, ast.Eq):    ok = left == right
                elif isinstance(op, ast.NotEq): ok = left != right
                elif isinstance(op, ast.Lt):  ok = _num(left) < _num(right)
                elif isinstance(op, ast.LtE): ok = _num(left) <= _num(right)
                elif isinstance(op, ast.Gt):  ok = _num(left) > _num(right)
                elif isinstance(op, ast.GtE): ok = _num(left) >= _num(right)
                elif isinstance(op, ast.In):  ok = left in right
                elif isinstance(op, ast.NotIn): ok = left not in right
                else: raise ValueError(f"Unsupported comparison: {op}")
                if not ok: return False
                left = right
            return True
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return data.get(node.id)
        if isinstance(node, ast.Attribute):
            base = _ev(node.value)
            if isinstance(base, dict):
                return base.get(node.attr)
            return getattr(base, node.attr, None)
        if isinstance(node, ast.Subscript):
            base = _ev(node.value)
            key = _ev(node.slice)
            try:
                return base[key]
            except (KeyError, IndexError, TypeError):
                return None
        if isinstance(node, ast.List):
            return [_ev(e) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(_ev(e) for e in node.elts)
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    return _ev(tree)


def _num(x):
    if isinstance(x, bool): return int(x)
    if isinstance(x, (int, float)): return x
    if isinstance(x, str):
        try: return float(x)
        except ValueError: return 0
    return 0


def _replace_word(s: str, word: str, replacement: str) -> str:
    import re
    return re.sub(rf"\b{re.escape(word)}\b", replacement, s)


# ---------------------------------------------------------------------------
# Sub-workflow node
# ---------------------------------------------------------------------------
@node("logic_subworkflow")
class SubWorkflowNode(BaseExecutor):
    """Synchronously invoke another FlowAgent workflow.

    cfg:
      target_workflow  — the name of the FlowAgent Workflow to invoke
      payload          — optional JSON string defining the payload passed
                         to the child. Defaults to the current context
                         serialised as JSON. Templated via Jinja before
                         being parsed.
      output           — variable name to bind the child's final context
                         under in the parent's context (default: 'result')

    Output: a dict with {child_run, child_context} that the parent can
    branch on.

    Guards:
      - Max nesting depth of 5 (configurable in FlowAgent Settings later).
        Each child run inherits a `_subworkflow_depth` marker bumped by 1.
      - Won't call a disabled workflow unless we're in dry-run.
    """

    MAX_DEPTH = 5

    def run(self, *, node, cfg, context, runner):
        from ..runner import Runner, PAUSE

        target = (cfg.get("target_workflow") or "").strip()
        if not target:
            frappe.throw("logic_subworkflow: target_workflow is required")

        # Cycle / depth guard. We piggyback on the context — the seed
        # passed to each child Runner carries the depth marker forward.
        depth = int(context.data.get("_subworkflow_depth") or 0) + 1
        if depth > self.MAX_DEPTH:
            frappe.throw(
                f"logic_subworkflow: max nesting depth ({self.MAX_DEPTH}) "
                f"exceeded — refusing to call '{target}' to prevent runaway "
                "recursion."
            )

        # Build the payload. Default: pass the parent's context whole.
        payload: dict
        raw_payload = cfg.get("payload")
        if raw_payload:
            try:
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                if not isinstance(payload, dict):
                    payload = {"value": payload}
            except Exception as e:
                frappe.throw(
                    f"logic_subworkflow: payload is not valid JSON ({e}). "
                    "Tip: use the | tojson Jinja filter when interpolating "
                    "dicts into the payload field."
                )
        else:
            # Pass a snapshot of the parent context. Exclude internal markers.
            payload = {
                k: v for k, v in context.data.items()
                if not str(k).startswith("$") and not str(k).startswith("_")
            }
        # Carry the depth + provenance markers forward
        payload["_subworkflow_depth"] = depth
        payload["_parent_run"] = runner.run_doc.name if runner.run_doc else None
        payload["_parent_workflow"] = runner.workflow_name

        # Dry-run path: don't actually invoke; return a stub so the
        # parent can preview the call.
        if runner.dry_run:
            return {
                "_dry_run": True,
                "would_invoke_workflow": target,
                "would_send_payload": payload,
            }

        # Sync invocation. We adopt no existing run — a fresh one is
        # created. The child runner is fully independent (own steps,
        # own AI metrics, own retries) and links back via parent_run.
        child = Runner(
            workflow_name=target,
            trigger_source=f"subworkflow:{runner.workflow_name}",
            payload=payload,
            user=runner.user,
            dry_run=False,
        )
        child_run_name = child.execute()

        # Fetch the child's final state so we can return useful info.
        child_doc = frappe.get_doc("FlowAgent Workflow Run", child_run_name)
        # Set parent_run on the child so the parent/child relationship is
        # discoverable from either direction.
        if child_doc.parent_run != (runner.run_doc.name if runner.run_doc else None):
            frappe.db.set_value(
                "FlowAgent Workflow Run", child_run_name,
                "parent_run", runner.run_doc.name if runner.run_doc else None,
                update_modified=False,
            )

        # If the child failed, fail the parent step too. The parent
        # workflow's on_error policy decides whether the whole run
        # halts or continues.
        if child_doc.status not in ("Success", "Waiting"):
            err = (child_doc.error_message or "child workflow failed")[:500]
            frappe.throw(
                f"logic_subworkflow: child '{target}' "
                f"({child_run_name}) ended with status {child_doc.status}. "
                f"Error: {err}"
            )

        # Parse the child's final context to return it to the parent
        try:
            child_ctx = json.loads(child_doc.final_context or "{}")
        except Exception:
            child_ctx = {}

        return {
            "child_run": child_run_name,
            "child_status": child_doc.status,
            "child_duration_ms": child_doc.duration_ms,
            "context": child_ctx,
        }


# ---------------------------------------------------------------------------
# Approval node (human-in-the-loop)
# ---------------------------------------------------------------------------
@node("logic_approval")
class ApprovalNode(BaseExecutor):
    """Pause the run, send an approval request, wait for a decision.

    cfg:
      approvers         — comma-separated email addresses to notify
      subject           — email subject (Jinja-templated)
      message           — email body (Jinja-templated, supports HTML)
      timeout_hours     — auto-decide after this many hours (default 24)
      on_timeout        — 'approve' | 'reject' | 'fail' (default 'reject')

    Outputs are port-specific:
      out-approve — taken when the approver clicks Approve
      out-reject  — taken when the approver clicks Reject (or on timeout
                    if on_timeout='reject', which is the default)

    Persistence:
      The node writes waiting_at_node, waiting_token, waiting_expires_at,
      and waiting_decision_port onto the run doc, then returns PAUSE so
      the runner exits with status=Waiting. The flowagent.api.approval
      endpoint receives the callback and calls
      flowagent.engine.resume_run(run_name, decision) to continue.
    """

    def run(self, *, node, cfg, context, runner):
        from ..runner import PAUSE
        import secrets

        if runner.dry_run:
            # In dry-run we don't actually pause — we'd never resume.
            # Pretend we got an approval and continue.
            return ("out-approve", {"_dry_run": True, "decision": "approve"})

        approvers_raw = (cfg.get("approvers") or "").strip()
        if not approvers_raw:
            frappe.throw("logic_approval: at least one approver email is required")
        approvers = [a.strip() for a in approvers_raw.split(",") if a.strip()]

        try:
            timeout_hours = float(cfg.get("timeout_hours") or 24)
        except (TypeError, ValueError):
            timeout_hours = 24.0
        timeout_hours = max(0.05, min(timeout_hours, 24 * 30))  # 3 min .. 30d

        # Generate a non-guessable token. Stored on the run; the resume
        # endpoint matches it to identify which run to resume.
        token = secrets.token_urlsafe(32)

        # Persist waiting state on the run doc. This must happen BEFORE
        # we send the email — otherwise an approver clicking the link
        # immediately could race with our save and not find the token.
        run = runner.run_doc
        run.status = "Waiting"
        run.waiting_at_node = runner.current_node_id
        run.waiting_token = token
        run.waiting_expires_at = frappe.utils.add_to_date(
            frappe.utils.now_datetime(), hours=timeout_hours
        )
        # Persist the current context too, so resume can restore it.
        run.final_context = json.dumps(context.snapshot(), default=str)[:140000]
        run.flags.ignore_permissions = True
        run.save(ignore_permissions=True)
        frappe.db.commit()  # nosemgrep: frappe-manual-commit  # Cross-process visibility: the approval node persists waiting state then returns PAUSE. The external HTTP callback endpoint must immediately be able to look up the run by waiting_token, so we commit before the email goes out.

        # Build callback URLs. We use frappe.utils.get_url so it works
        # behind reverse proxies / custom domains.
        site_url = frappe.utils.get_url()
        approve_url = (
            f"{site_url}/api/method/flowagent.api.approval.decide"
            f"?token={token}&decision=approve"
        )
        reject_url = (
            f"{site_url}/api/method/flowagent.api.approval.decide"
            f"?token={token}&decision=reject"
        )

        # Subject + body, both Jinja-rendered against the current context
        from ..context import render as _render
        try:
            subject = _render(
                cfg.get("subject") or f"Approval needed: {runner.workflow_name}",
                context.data,
            )
        except Exception:
            subject = f"Approval needed: {runner.workflow_name}"

        try:
            user_message = _render(
                cfg.get("message") or "Please review and approve.",
                context.data,
            )
        except Exception:
            user_message = "Please review and approve."

        # Compose the HTML email. Inline-styled buttons so it renders
        # consistently across mail clients.
        run_url = f"{site_url}/app/flowagent-workflow-run/{run.name}"
        html = f"""
            <div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:600px;
                        margin:0 auto;padding:24px;color:#1f2937">
              <h2 style="margin:0 0 16px 0;color:#1f2937">Approval requested</h2>
              <p style="margin:0 0 24px 0;white-space:pre-wrap">{frappe.utils.escape_html(user_message)}</p>
              <p style="margin:0 0 24px 0">
                <a href="{approve_url}"
                   style="display:inline-block;padding:12px 24px;background:#10B981;
                          color:white;text-decoration:none;border-radius:6px;
                          font-weight:600;margin-right:12px">Approve</a>
                <a href="{reject_url}"
                   style="display:inline-block;padding:12px 24px;background:#EF4444;
                          color:white;text-decoration:none;border-radius:6px;
                          font-weight:600">Reject</a>
              </p>
              <p style="margin:24px 0 0 0;font-size:12px;color:#6b7280">
                Workflow: <a href="{run_url}" style="color:#6b7280">
                  {frappe.utils.escape_html(runner.workflow_name)} / {run.name}
                </a><br>
                Expires {timeout_hours:g}h from now.
              </p>
            </div>
        """

        try:
            frappe.sendmail(
                recipients=approvers,
                subject=subject,
                message=html,
                delayed=False,
            )
        except Exception as e:
            # If email failed, undo the Waiting state so the run fails
            # cleanly rather than getting stuck forever.
            run.status = "Failed"
            run.waiting_token = None
            run.save(ignore_permissions=True)
            frappe.throw(
                f"logic_approval: failed to send approval email: {e}"
            )

        # Returning PAUSE signals the runner to exit cleanly. The next
        # action on this run comes from flowagent.api.approval.decide.
        return PAUSE
