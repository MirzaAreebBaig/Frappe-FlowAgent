# Copyright (c) 2026, FlowAgent
# For license information, please see license.txt
"""
FlowAgent Engineer — an agentic workflow builder.

The user describes what they want. The Engineer:
  1. DESIGNS a workflow (Claude → JSON graph + a synthetic test payload)
  2. BUILDS it (saves as FlowAgent Workflow)
  3. TESTS it (dry-run against the test payload)
  4. ANALYZES the outcome (Claude reads the run + steps, decides
     success / needs-fix / stuck)
  5. Loops back to step 1 with the failure context until success
     or max_iterations is reached.

Job state is kept in Frappe's cache (Redis) keyed by a random job_id.
The Studio polls `get_status(job_id)` at ~1Hz and renders each
iteration as it happens.

Rationale for cache-over-doctype: an engineering job is ephemeral
progress state; if the worker dies mid-loop, restarting from scratch
is cheaper than reconciling half-persisted DB state. The final
workflow is persisted as a normal FlowAgent Workflow doc — that's
the durable output.
"""
from __future__ import annotations

import json
import re
import time
import traceback

import frappe
from frappe.utils import now_datetime


# ---------------------------------------------------------------------------
# Cache-backed job store
# ---------------------------------------------------------------------------
_CACHE_PREFIX = "flowagent:engineer:"
_JOB_TTL_SECONDS = 60 * 60 * 6  # 6h — plenty for polling after completion


def _job_key(job_id: str) -> str:
    return _CACHE_PREFIX + job_id


def _get_job(job_id: str) -> dict | None:
    raw = frappe.cache().get_value(_job_key(job_id))
    if not raw:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    # Frappe's cache sometimes returns the decoded dict already
    return raw if isinstance(raw, dict) else None


def _save_job(job_id: str, job: dict) -> None:
    frappe.cache().set_value(
        _job_key(job_id), json.dumps(job, default=str),
        expires_in_sec=_JOB_TTL_SECONDS,
    )


def _update_job(job_id: str, **updates) -> dict:
    """Merge updates into the job dict and persist."""
    job = _get_job(job_id) or {}
    job.update(updates)
    job["updated_at"] = str(now_datetime())
    _save_job(job_id, job)
    return job


def _append_iteration(job_id: str, iteration: dict) -> None:
    """Add an iteration record to the job's history."""
    job = _get_job(job_id) or {}
    job.setdefault("iterations", []).append(iteration)
    job["current_iteration"] = len(job["iterations"])
    job["updated_at"] = str(now_datetime())
    _save_job(job_id, job)


def _append_log(job_id: str, message: str, level: str = "info") -> None:
    """Push a log line onto the job's log tape."""
    job = _get_job(job_id) or {}
    job.setdefault("logs", []).append({
        "ts": str(now_datetime()),
        "level": level,
        "message": message,
    })
    # Cap logs to last 500 lines so the payload stays reasonable
    if len(job["logs"]) > 500:
        job["logs"] = job["logs"][-500:]
    job["updated_at"] = str(now_datetime())
    _save_job(job_id, job)


# ---------------------------------------------------------------------------
# Whitelisted endpoints
# ---------------------------------------------------------------------------
@frappe.whitelist()
def start(goal: str, max_iterations: int = 5, workflow_name: str | None = None,
          test_mode: str = "dry_run") -> dict:
    """Kick off an engineering job. Returns {job_id} for polling.

    Args:
        goal: Natural-language description of what the workflow should do.
        max_iterations: Cap on the design→test→fix loop (default 5).
        workflow_name: If set, iterates on this existing workflow instead
                       of creating a new one.
        test_mode: 'dry_run' (safe — no side effects) or 'live' (actually
                   runs the workflow, may create docs / send emails).
    """
    if not _has_permission():
        frappe.throw("Not permitted", frappe.PermissionError)

    goal = (goal or "").strip()
    if not goal:
        frappe.throw("goal is required")
    if len(goal) > 8000:
        frappe.throw("goal is too long (max 8000 chars)")

    try:
        max_iterations = int(max_iterations)
    except (TypeError, ValueError):
        max_iterations = 5
    max_iterations = max(1, min(max_iterations, 10))

    if test_mode not in ("dry_run", "live"):
        test_mode = "dry_run"

    job_id = frappe.generate_hash(length=12)
    _save_job(job_id, {
        "job_id": job_id,
        "status": "queued",
        "goal": goal,
        "workflow_name": workflow_name,
        "max_iterations": max_iterations,
        "test_mode": test_mode,
        "iterations": [],
        "logs": [],
        "current_iteration": 0,
        "started_at": str(now_datetime()),
        "started_by": frappe.session.user,
    })

    frappe.enqueue(
        "flowagent.api.engineer._run_loop",
        job_id=job_id,
        queue="long",
        timeout=1800,   # 30 min hard cap — a runaway loop shouldn't tie up a worker forever
        now=False,
    )
    return {"job_id": job_id, "status": "queued"}


@frappe.whitelist()
def get_status(job_id: str, since_iteration: int = 0,
               since_log: int = 0) -> dict:
    """Polling endpoint. Returns the current job state.

    Args:
        job_id: The id returned by start().
        since_iteration: Only return iterations after this index
                         (client-side incremental diffing).
        since_log: Only return logs after this index.
    """
    if not _has_permission():
        frappe.throw("Not permitted", frappe.PermissionError)

    job = _get_job(job_id)
    if not job:
        frappe.throw(f"Engineering job '{job_id}' not found (may have expired)")

    try:
        since_iteration = int(since_iteration)
    except (TypeError, ValueError):
        since_iteration = 0
    try:
        since_log = int(since_log)
    except (TypeError, ValueError):
        since_log = 0

    iterations = job.get("iterations", [])
    logs = job.get("logs", [])
    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "goal": job.get("goal"),
        "workflow_name": job.get("workflow_name"),
        "max_iterations": job.get("max_iterations"),
        "current_iteration": job.get("current_iteration"),
        "test_mode": job.get("test_mode"),
        "started_at": job.get("started_at"),
        "ended_at": job.get("ended_at"),
        "final_status": job.get("final_status"),
        "final_reason": job.get("final_reason"),
        # Incremental slices for polling clients
        "iterations": iterations[since_iteration:],
        "total_iterations": len(iterations),
        "logs": logs[since_log:],
        "total_logs": len(logs),
    }


@frappe.whitelist()
def cancel(job_id: str) -> dict:
    """Signal a running job to stop. It'll finish the current iteration
    then exit — we don't hard-kill the worker."""
    if not _has_permission():
        frappe.throw("Not permitted", frappe.PermissionError)
    job = _get_job(job_id)
    if not job:
        frappe.throw(f"Job '{job_id}' not found")
    _update_job(job_id, cancel_requested=True)
    _append_log(job_id, "Cancel requested — will stop after current iteration.", "warn")
    return {"ok": True}


# ---------------------------------------------------------------------------
# The main loop (runs in background worker)
# ---------------------------------------------------------------------------
def _run_loop(job_id: str) -> None:
    """The agent loop. Called via frappe.enqueue from start()."""
    job = _get_job(job_id)
    if not job:
        return

    try:
        _update_job(job_id, status="running")
        _append_log(job_id, f"Starting engineer with goal: {job['goal'][:200]}", "info")

        prior_workflow: dict | None = None
        prior_error: str | None = None
        prior_run_summary: dict | None = None
        workflow_name = job.get("workflow_name")

        for i in range(job["max_iterations"]):
            # Check cancellation before each iteration
            fresh = _get_job(job_id)
            if fresh and fresh.get("cancel_requested"):
                _finalize(job_id, "cancelled", "User cancelled")
                return

            iter_num = i + 1
            _update_job(job_id, status=f"designing (iteration {iter_num})")
            _append_log(job_id, f"── Iteration {iter_num}/{job['max_iterations']} ──", "info")

            # Step 1: Design
            try:
                design = _design(
                    goal=job["goal"],
                    iteration=iter_num,
                    prior_workflow=prior_workflow,
                    prior_error=prior_error,
                    prior_run_summary=prior_run_summary,
                    workflow_name_hint=workflow_name,
                )
            except Exception as e:
                _append_log(job_id, f"Design failed: {type(e).__name__}: {e}", "error")
                _finalize(job_id, "failed", f"Design error: {e}")
                return

            _append_log(job_id,
                        f"Designed: {design.get('workflow_name', 'unnamed')} "
                        f"({len(design.get('nodes', []))} nodes)",
                        "info")

            # Step 2: Build (save workflow)
            _update_job(job_id, status=f"building (iteration {iter_num})")
            try:
                saved_name = _build(design, workflow_name)
                workflow_name = saved_name
            except Exception as e:
                _append_log(job_id, f"Build failed: {type(e).__name__}: {e}", "error")
                # Feed the build error back into the next iteration
                prior_workflow = design
                prior_error = f"Save failed: {e}"
                prior_run_summary = None
                _append_iteration(job_id, {
                    "iteration": iter_num,
                    "phase": "build",
                    "workflow": design,
                    "error": str(e),
                    "verdict": {"success": False, "issue": f"Could not save: {e}"},
                })
                continue

            _append_log(job_id, f"Saved as {workflow_name}", "info")

            # Step 3: Test
            _update_job(job_id, status=f"testing (iteration {iter_num})")
            try:
                run_summary = _test(
                    workflow_name=workflow_name,
                    test_payload=design.get("test_payload", {}),
                    test_mode=job.get("test_mode", "dry_run"),
                )
            except Exception as e:
                _append_log(job_id, f"Test setup failed: {e}", "error")
                run_summary = {
                    "status": "Failed",
                    "error_message": f"Test setup failed: {e}",
                    "steps": [],
                }

            _append_log(job_id,
                        f"Test run finished: {run_summary.get('status')} "
                        f"({len(run_summary.get('steps', []))} steps)",
                        "info" if run_summary.get("status") == "Success" else "warn")

            # Step 4: Analyze
            _update_job(job_id, status=f"analyzing (iteration {iter_num})")
            try:
                verdict = _analyze(
                    goal=job["goal"],
                    workflow=design,
                    run_summary=run_summary,
                )
            except Exception as e:
                _append_log(job_id, f"Analysis failed: {e} — assuming iterate", "warn")
                verdict = {
                    "success": False,
                    "issue": f"Analysis error: {e}",
                    "reasoning": "",
                }

            _append_iteration(job_id, {
                "iteration": iter_num,
                "phase": "complete",
                "workflow": design,
                "run_name": run_summary.get("name"),
                "run_status": run_summary.get("status"),
                "run_error": run_summary.get("error_message"),
                "run_steps_count": len(run_summary.get("steps", [])),
                "verdict": verdict,
            })

            if verdict.get("success"):
                _append_log(job_id, f"✓ Goal achieved on iteration {iter_num}", "success")
                _finalize(job_id, "success", verdict.get("reasoning") or "Objective achieved", workflow_name)
                return

            # Continue: feed forward into the next iteration
            issue = verdict.get("issue") or run_summary.get("error_message") or "Unknown issue"
            _append_log(job_id, f"Not done: {issue[:200]}", "warn")

            prior_workflow = design
            prior_error = issue
            prior_run_summary = _summarize_run_for_feedback(run_summary)

        _append_log(job_id, "Max iterations reached without success", "warn")
        _finalize(job_id, "max_iterations",
                  "Ran out of iterations. Latest workflow saved — inspect the run history and refine manually.",
                  workflow_name)

    except Exception as e:
        _append_log(job_id, f"Fatal error: {type(e).__name__}: {e}", "error")
        frappe.log_error(
            title=f"FlowAgent Engineer: fatal error in job {job_id}",
            message=f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}",
        )
        _finalize(job_id, "failed", str(e))


def _finalize(job_id: str, final_status: str, reason: str,
              workflow_name: str | None = None) -> None:
    """Terminal state for a job."""
    updates = {
        "status": "finished",
        "final_status": final_status,
        "final_reason": reason,
        "ended_at": str(now_datetime()),
    }
    if workflow_name:
        updates["workflow_name"] = workflow_name
    _update_job(job_id, **updates)


# ---------------------------------------------------------------------------
# Design (Claude → JSON workflow + test payload)
# ---------------------------------------------------------------------------
def _design(goal: str, iteration: int, prior_workflow: dict | None,
            prior_error: str | None, prior_run_summary: dict | None,
            workflow_name_hint: str | None) -> dict:
    """Ask Claude to design (or fix) the workflow.

    Returns a dict shaped like:
        {
          "workflow_name": "...",
          "description": "...",
          "trigger": {...},
          "nodes": [...],
          "edges": [...],
          "test_payload": {...},
          "reasoning": "..."
        }
    """
    from .ai_build import SYSTEM_PROMPT, VALID_NODE_TYPES, _strip_fences
    from ..flowagent_core.doctype.flowagent_settings.flowagent_settings import (
        get_anthropic_key, get_default_model,
    )
    try:
        from anthropic import Anthropic
    except ImportError:
        frappe.throw("Install the anthropic package to use the Engineer")

    key = get_anthropic_key()
    if not key:
        frappe.throw("Set the Anthropic API key in FlowAgent Settings")

    # Compose the user message. First iteration = plain goal. Later
    # iterations include what was tried and what went wrong.
    if iteration == 1:
        user_msg = (
            f"Design a workflow for this goal:\n\n{goal}\n\n"
            "Additionally, include a `test_payload` field: a synthetic "
            "trigger payload we can use to dry-run this workflow and "
            "verify it wires up correctly. For a DocType trigger, the "
            "payload should be shaped like "
            "{\"doc\": {...doctype fields...}, \"doctype\": \"...\", "
            "\"event\": \"...\"}. For a Manual trigger, an empty object "
            "is fine.\n\n"
            "Include a brief `reasoning` field (1-3 sentences) "
            "explaining the design approach."
        )
    else:
        prior_graph = json.dumps({
            "trigger": prior_workflow.get("trigger"),
            "nodes":   prior_workflow.get("nodes"),
            "edges":   prior_workflow.get("edges"),
        }, indent=2)[:6000]
        user_msg = (
            f"GOAL: {goal}\n\n"
            f"PREVIOUS ATTEMPT (iteration {iteration - 1}):\n"
            f"{prior_graph}\n\n"
            f"WHAT HAPPENED WHEN TESTED:\n{prior_error or 'Unknown'}\n\n"
        )
        if prior_run_summary:
            user_msg += (
                f"RUN DETAILS:\n{json.dumps(prior_run_summary, indent=2)[:3000]}\n\n"
            )
        user_msg += (
            "Fix the workflow so the goal is achieved. Return the FULL "
            "corrected workflow JSON (not just the delta), plus an "
            "updated `test_payload` and a short `reasoning` field "
            "explaining what you changed and why."
        )

    engineer_system = SYSTEM_PROMPT + "\n\n" + (
        "You are operating in ENGINEER mode: your JSON output MUST also "
        "include a `test_payload` object (a synthetic input to dry-run "
        "against) and a `reasoning` string (1-3 sentences about your "
        "design choices). All other rules from the base prompt apply."
    )

    client = Anthropic(api_key=key)
    response = client.messages.create(
        model=get_default_model(),
        max_tokens=6000,
        system=engineer_system,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ).strip()

    cleaned = _strip_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            raise RuntimeError(f"Design returned non-JSON: {raw[:300]}")
        parsed = json.loads(m.group(0))

    # Filter unknown node types (avoid canvas explosions)
    parsed["nodes"] = [
        n for n in parsed.get("nodes", []) if n.get("type") in VALID_NODE_TYPES
    ]
    if workflow_name_hint:
        parsed["workflow_name"] = workflow_name_hint
    if not parsed.get("workflow_name"):
        parsed["workflow_name"] = f"Engineer-{frappe.generate_hash(length=6)}"
    parsed.setdefault("test_payload", {})
    parsed.setdefault("reasoning", "")
    return parsed


# ---------------------------------------------------------------------------
# Build (persist the workflow)
# ---------------------------------------------------------------------------
def _build(design: dict, existing_name: str | None) -> str:
    """Save the designed workflow as a FlowAgent Workflow doc.

    Reuses the studio save endpoint's logic so we get the same
    trigger-index rebuild and version snapshot behaviour.
    """
    from .studio import save_workflow

    trigger = design.get("trigger") or {}
    payload = {
        "workflow_name": design.get("workflow_name") or existing_name or "Engineer Workflow",
        "description": design.get("description") or "",
        "enabled": 1,
        "trigger": {
            "type": trigger.get("type", "Manual"),
            "doctype": trigger.get("doctype"),
            "event": trigger.get("event"),
            "cron": trigger.get("cron"),
        },
        "nodes": design.get("nodes", []),
        "edges": design.get("edges", []),
    }
    result = save_workflow(json.dumps(payload))
    return result.get("name") or payload["workflow_name"]


# ---------------------------------------------------------------------------
# Test (dry-run the workflow with the synthetic payload)
# ---------------------------------------------------------------------------
def _test(workflow_name: str, test_payload: dict, test_mode: str) -> dict:
    """Run the workflow and return a summary of what happened.

    Uses dry_run mode by default — nodes report what they *would* do
    without side effects. `test_mode='live'` runs for real (may create
    docs, send emails, spend AI tokens).
    """
    from ..engine.runner import Runner

    runner = Runner(
        workflow_name=workflow_name,
        trigger_source=f"engineer_test:{test_mode}",
        payload=test_payload or {},
        user=frappe.session.user,
        dry_run=(test_mode == "dry_run"),
    )
    try:
        run_name = runner.execute()
    except Exception as e:
        return {
            "status": "Failed",
            "error_message": f"{type(e).__name__}: {e}",
            "steps": [],
        }

    # Load back the persisted run
    run_doc = frappe.get_doc("FlowAgent Workflow Run", run_name)
    steps = []
    for s in (run_doc.steps or []):
        steps.append({
            "index": s.step_index,
            "node_id": s.node_id,
            "node_type": s.node_type,
            "node_label": s.node_label,
            "status": s.status,
            "duration_ms": s.duration_ms,
            "error": (s.error or "")[:400],
            "output": (s.output_snapshot or "")[:400],
        })
    try:
        final_ctx = json.loads(run_doc.final_context or "{}")
    except Exception:
        final_ctx = {}

    return {
        "name": run_name,
        "status": run_doc.status,
        "duration_ms": run_doc.duration_ms,
        "error_message": run_doc.error_message,
        "final_context": final_ctx,
        "steps": steps,
    }


def _summarize_run_for_feedback(run_summary: dict) -> dict:
    """Trim the run details to what's useful in the next design prompt."""
    steps = run_summary.get("steps", [])[:20]  # cap to keep prompt small
    return {
        "status": run_summary.get("status"),
        "error_message": (run_summary.get("error_message") or "")[:500],
        "steps": steps,
        "final_context_keys": list((run_summary.get("final_context") or {}).keys())[:30],
    }


# ---------------------------------------------------------------------------
# Analyze (verdict: success / iterate / stuck)
# ---------------------------------------------------------------------------
def _analyze(goal: str, workflow: dict, run_summary: dict) -> dict:
    """Ask Claude whether the run achieved the goal.

    Returns {success: bool, issue: str, reasoning: str}.

    Fast path: if run status was already Failed, no need to spend a
    round trip — it's clearly not success.
    """
    if run_summary.get("status") in ("Failed", "Timeout"):
        return {
            "success": False,
            "issue": (run_summary.get("error_message")
                      or "Run failed with no error message")[:400],
            "reasoning": "Run terminated with a failure status.",
        }

    from ..flowagent_core.doctype.flowagent_settings.flowagent_settings import (
        get_anthropic_key, get_default_model,
    )
    try:
        from anthropic import Anthropic
    except ImportError:
        # Fallback: without Claude, if it didn't fail, treat as success.
        return {"success": True, "issue": "",
                "reasoning": "Run completed successfully (Anthropic unavailable for deeper analysis)."}

    key = get_anthropic_key()
    if not key:
        return {"success": True, "issue": "", "reasoning": "Run completed successfully."}

    client = Anthropic(api_key=key)
    prompt = (
        "You are evaluating whether a workflow run achieved the user's goal.\n\n"
        f"USER GOAL: {goal}\n\n"
        f"WORKFLOW: {workflow.get('description') or workflow.get('workflow_name')}\n\n"
        f"RUN OUTCOME:\n{json.dumps(_summarize_run_for_feedback(run_summary), indent=2)[:4000]}\n\n"
        "Return ONLY a JSON object of this shape (no markdown, no prose):\n"
        '{"success": true/false, "issue": "short description if not success", "reasoning": "1-2 sentences"}\n\n'
        "Guidelines:\n"
        "- 'success' means the workflow completed AND the steps that ran make sense for the goal.\n"
        "- If nodes were skipped that shouldn't have been, that's not success.\n"
        "- If a step's output was clearly wrong (e.g. AI returned an error message inside its output), not success.\n"
        "- If everything looks right, return success=true."
    )
    response = client.messages.create(
        model=get_default_model(),
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ).strip()
    try:
        # Strip fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        # If Claude returned prose, be conservative
        return {"success": False,
                "issue": "Analysis output was not parseable JSON",
                "reasoning": raw[:400]}

    return {
        "success": bool(verdict.get("success")),
        "issue": (verdict.get("issue") or "")[:400],
        "reasoning": (verdict.get("reasoning") or "")[:600],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _has_permission() -> bool:
    roles = set(frappe.get_roles())
    return "System Manager" in roles or "FlowAgent Manager" in roles
