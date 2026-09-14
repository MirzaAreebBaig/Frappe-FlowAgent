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
    """Push a log line onto the job's log tape.

    Wrapped defensively — if cache writes fail, the whole engineer
    loop must not die because of a log line. On failure, mirror to
    Frappe's Error Log so at least the user has a diagnostic trail
    they can see in the desk.
    """
    try:
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
    except Exception as e:
        # A broken log line MUST NOT kill the loop. Log to Frappe's
        # Error Log so it's visible in the desk if the modal doesn't
        # show it.
        try:
            frappe.log_error(
                title=f"FlowAgent Engineer: log write failed for {job_id}",
                message=f"level={level}\nmsg={message}\n\n{type(e).__name__}: {e}",
            )
        except Exception:
            pass  # last resort — swallow


def _mirror_to_error_log(job_id: str, title: str, detail: str) -> None:
    """Also write a copy to Frappe's Error Log doctype.

    So when the cached job state gets weird or the UI polling loses
    track, the user always has a durable record in Error Log > List
    filtered by 'FlowAgent Engineer'.
    """
    try:
        frappe.log_error(
            title=f"FlowAgent Engineer: {title} [{job_id[:8]}]",
            message=detail[:4000],
        )
    except Exception:
        pass


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

    # NOTE: We pass the id as `engineering_job_id`, NOT `job_id`.
    # `job_id` is a reserved kwarg of `frappe.enqueue` itself (used as
    # the RQ deduplication key) — it gets consumed by enqueue and never
    # forwarded to the target function. Using our own distinct name
    # ensures `_run_loop` actually receives the id in **kwargs.
    frappe.enqueue(
        "flowagent.api.engineer._run_loop",
        engineering_job_id=job_id,
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
        "phase":  job.get("phase"),
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
def _run_loop(engineering_job_id: str) -> None:
    """The agent loop. Called via frappe.enqueue from start().

    Parameter is named `engineering_job_id` (not `job_id`) to avoid
    colliding with frappe.enqueue's own reserved `job_id` kwarg.
    See the caller in start() for the full explanation.
    """
    # Alias locally so the rest of the function reads naturally.
    job_id = engineering_job_id
    job = _get_job(job_id)
    if not job:
        return

    try:
        _update_job(job_id, status="running", phase="starting")
        _append_log(job_id, f"🚀 Engineer starting  •  goal: {job['goal'][:180]}", "info")
        _append_log(job_id,
                    f"⚙️  Config  •  max iterations: {job['max_iterations']}  •  "
                    f"test mode: {job.get('test_mode', 'dry_run')}"
                    + (f"  •  iterating on existing workflow: {job['workflow_name']}"
                       if job.get('workflow_name') else "  •  will create a new workflow"),
                    "info")

        prior_workflow: dict | None = None
        prior_error: str | None = None
        prior_run_summary: dict | None = None
        workflow_name = job.get("workflow_name")
        # Use the enqueuer as the runner user — frappe.session.user in a
        # background worker is unreliable and can be Guest.
        runner_user = job.get("started_by") or "Administrator"

        for i in range(job["max_iterations"]):
            # Check cancellation before each iteration
            fresh = _get_job(job_id)
            if fresh and fresh.get("cancel_requested"):
                _append_log(job_id, "🛑 Cancelled by user", "warn")
                _finalize(job_id, "cancelled", "User cancelled")
                return

            iter_num = i + 1
            _update_job(job_id, status=f"iteration {iter_num}", phase="starting", current_iteration=iter_num)
            _append_log(job_id, f"━━━ Iteration {iter_num} of {job['max_iterations']} ━━━", "phase")

            # ---------------- PHASE 1: DESIGN ----------------
            _update_job(job_id, phase=f"designing (iter {iter_num})")
            if iter_num == 1:
                _append_log(job_id, "🎨 Designing initial workflow with Claude…", "info")
            else:
                _append_log(job_id,
                            f"🔧 Refining workflow with Claude "
                            f"(fixing: {(prior_error or 'unknown')[:120]}…)",
                            "info")
            t0 = time.monotonic()
            try:
                design = _design(
                    goal=job["goal"],
                    iteration=iter_num,
                    prior_workflow=prior_workflow,
                    prior_error=prior_error,
                    prior_run_summary=prior_run_summary,
                    workflow_name_hint=workflow_name,
                    job_id=job_id,
                )
            except Exception as e:
                # Mirror to Error Log so the failure is visible in the
                # desk even if the cached job state loses the log line.
                tb = traceback.format_exc()
                _mirror_to_error_log(
                    job_id,
                    f"Design failed on iteration {iter_num}",
                    f"{type(e).__name__}: {e}\n\n{tb}",
                )
                _append_log(job_id,
                            f"❌ Design failed: {type(e).__name__}: {e}",
                            "error")
                _finalize(job_id, "failed", f"Design error: {e}", workflow_name)
                return
            design_ms = int((time.monotonic() - t0) * 1000)

            nodes = design.get("nodes", []) or []
            edges = design.get("edges", []) or []
            trig = design.get("trigger") or {}
            trig_desc = trig.get("type", "?")
            if trig.get("doctype"): trig_desc += f" / {trig['doctype']}"
            if trig.get("event"):   trig_desc += f" / {trig['event']}"
            node_types = ", ".join(sorted(set((n.get("type") or "?") for n in nodes)))
            _append_log(job_id, f"   ✓ Design received in {design_ms}ms", "info")
            _append_log(job_id, f"     ├─ Workflow: {design.get('workflow_name', 'unnamed')}", "info")
            _append_log(job_id, f"     ├─ Trigger: {trig_desc}", "info")
            _append_log(job_id, f"     ├─ Structure: {len(nodes)} nodes, {len(edges)} edges", "info")
            _append_log(job_id, f"     ├─ Node types: {node_types or '(none)'}", "info")
            reasoning = (design.get("reasoning") or "").strip()
            if reasoning:
                _append_log(job_id, f"     └─ Reasoning: {reasoning[:280]}", "info")
            tp = design.get("test_payload") or {}
            _append_log(job_id, f"       Test payload: {list(tp.keys()) if tp else '(empty)'}", "info")

            # ---------------- PHASE 2: BUILD ----------------
            _update_job(job_id, phase=f"saving (iter {iter_num})")
            _append_log(job_id, "💾 Saving workflow to database…", "info")
            t0 = time.monotonic()
            try:
                saved_name = _build(design, workflow_name)
                workflow_name = saved_name
            except Exception as e:
                build_ms = int((time.monotonic() - t0) * 1000)
                _append_log(job_id, f"❌ Save failed after {build_ms}ms: {type(e).__name__}: {e}", "error")
                # Feed the build error back into the next iteration so
                # Claude can fix the invalid graph.
                prior_workflow = design
                prior_error = f"Save rejected the workflow: {e}"
                prior_run_summary = None
                _append_iteration(job_id, {
                    "iteration": iter_num,
                    "phase": "build",
                    "workflow": design,
                    "run_status": "SaveError",
                    "run_error": str(e),
                    "run_steps": [],
                    "run_steps_count": 0,
                    "design_ms": design_ms,
                    "verdict": {"success": False,
                                "issue": f"Could not save: {e}",
                                "reasoning": ""},
                })
                continue
            build_ms = int((time.monotonic() - t0) * 1000)
            _append_log(job_id, f"   ✓ Saved as '{workflow_name}' in {build_ms}ms", "success")

            # ---------------- PHASE 3: TEST ----------------
            _update_job(job_id, phase=f"testing (iter {iter_num})")
            test_mode = job.get("test_mode", "dry_run")
            _append_log(job_id, f"🧪 Testing workflow in {test_mode} mode…", "info")
            t0 = time.monotonic()
            try:
                run_summary = _test(
                    workflow_name=workflow_name,
                    test_payload=design.get("test_payload", {}),
                    test_mode=test_mode,
                    user=runner_user,
                )
            except Exception as e:
                _append_log(job_id, f"❌ Test setup crashed: {type(e).__name__}: {e}", "error")
                run_summary = {
                    "status": "Failed",
                    "error_message": f"Test setup crashed: {type(e).__name__}: {e}",
                    "steps": [],
                }
            test_ms = int((time.monotonic() - t0) * 1000)

            steps = run_summary.get("steps", []) or []
            run_status = run_summary.get("status", "?")
            run_err = (run_summary.get("error_message") or "").strip()
            status_icon = "✓" if run_status == "Success" else ("⧗" if run_status == "Waiting" else "✗")
            status_level = "success" if run_status == "Success" else ("warn" if run_status == "Waiting" else "error")
            _append_log(job_id,
                        f"   {status_icon} Test complete in {test_ms}ms  •  "
                        f"status: {run_status}  •  {len(steps)} step(s) executed",
                        status_level)

            # Per-step play-by-play (cap to keep log tape scannable)
            for step in steps[:15]:
                s_status = step.get("status", "?")
                s_icon = "✓" if s_status == "Success" else ("⋯" if s_status == "Skipped" else "✗")
                s_lvl  = "info" if s_status == "Success" else ("info" if s_status == "Skipped" else "error")
                _append_log(
                    job_id,
                    f"     {s_icon} step {step.get('index','?')}: "
                    f"{step.get('node_label') or step.get('node_type') or '?'} "
                    f"({step.get('node_type','?')}) — {s_status} in {step.get('duration_ms',0)}ms",
                    s_lvl,
                )
                s_err = (step.get("error") or "").strip()
                if s_err:
                    _append_log(job_id, f"        ↳ {s_err[:220]}", "error")
            if len(steps) > 15:
                _append_log(job_id, f"     … and {len(steps) - 15} more step(s)", "info")

            if run_err:
                _append_log(job_id, f"   Run error: {run_err[:400]}", "error")

            # ---------------- PHASE 4: ANALYZE ----------------
            _update_job(job_id, phase=f"analyzing (iter {iter_num})")
            _append_log(job_id, "🔍 Analyzing outcome…", "info")
            t0 = time.monotonic()
            try:
                verdict = _analyze(
                    goal=job["goal"],
                    workflow=design,
                    run_summary=run_summary,
                )
            except Exception as e:
                _append_log(job_id, f"⚠ Analysis crashed: {e} — treating as needs-fix", "warn")
                verdict = {
                    "success": False,
                    "issue": f"Analysis error: {e}",
                    "reasoning": "",
                }
            analyze_ms = int((time.monotonic() - t0) * 1000)

            v_icon = "✓" if verdict.get("success") else "✗"
            v_lvl  = "success" if verdict.get("success") else "warn"
            _append_log(job_id,
                        f"   {v_icon} Verdict: "
                        f"{'GOAL ACHIEVED' if verdict.get('success') else 'NEEDS REFINEMENT'} "
                        f"(analysis {analyze_ms}ms)",
                        v_lvl)
            v_reasoning = (verdict.get("reasoning") or "").strip()
            v_issue     = (verdict.get("issue") or "").strip()
            if v_reasoning:
                _append_log(job_id, f"     Reasoning: {v_reasoning[:300]}", "info")
            if v_issue and not verdict.get("success"):
                _append_log(job_id, f"     Issue: {v_issue[:300]}", "warn")

            # ---------------- Record & advance ----------------
            _append_iteration(job_id, {
                "iteration": iter_num,
                "phase": "complete",
                "workflow": design,
                "run_name": run_summary.get("name"),
                "run_status": run_status,
                "run_error": run_err,
                "run_steps": steps[:20],   # keep for UI display
                "run_steps_count": len(steps),
                "design_ms": design_ms,
                "build_ms": build_ms,
                "test_ms": test_ms,
                "analyze_ms": analyze_ms,
                "verdict": verdict,
            })

            if verdict.get("success"):
                _append_log(job_id, f"🎉 Goal achieved on iteration {iter_num}", "success")
                _finalize(job_id, "success",
                          verdict.get("reasoning") or "Objective achieved",
                          workflow_name)
                return

            # Build the refinement context for next iteration
            # ---------------------------------------------------
            # We want Claude to see: the specific step that failed, its
            # error, its input. That's what unlocks a real fix vs a
            # regenerate-with-slight-tweaks.
            failing_step = None
            for step in steps:
                if step.get("status") == "Failed":
                    failing_step = step
                    break

            issue = v_issue or run_err or "Analyzer said the workflow didn't fully meet the goal."
            if failing_step:
                issue = (
                    f"Step {failing_step.get('index','?')} "
                    f"({failing_step.get('node_label') or failing_step.get('node_type')}, "
                    f"type={failing_step.get('node_type')}) FAILED with: "
                    f"{(failing_step.get('error') or 'no error message').strip()[:300]}"
                )
                _append_log(job_id, f"   → will focus refinement on step {failing_step.get('index')}", "info")

            prior_workflow = design
            prior_error = issue
            prior_run_summary = _summarize_run_for_feedback(run_summary)

        _append_log(job_id, "⏱ Max iterations reached without success", "warn")
        _finalize(
            job_id, "max_iterations",
            "Ran out of iterations. Latest workflow saved — inspect the "
            "iteration cards above to see what went wrong, then refine manually.",
            workflow_name,
        )

    except Exception as e:
        tb = traceback.format_exc()
        _append_log(job_id, f"💥 Fatal error: {type(e).__name__}: {e}", "error")
        _mirror_to_error_log(
            job_id,
            "FATAL error in _run_loop",
            f"goal: {job.get('goal', '')[:200]}\n\n"
            f"{type(e).__name__}: {e}\n\n{tb}",
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
            workflow_name_hint: str | None, job_id: str | None = None) -> dict:
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

    `job_id` is optional but recommended — when set, we emit heartbeat
    logs during the Claude call so the user knows the API round-trip
    is in flight (not that the loop is stuck).
    """
    from .ai_build import SYSTEM_PROMPT, VALID_NODE_TYPES, _strip_fences
    from ..flowagent_core.doctype.flowagent_settings.flowagent_settings import (
        get_anthropic_key, get_default_model,
    )
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError(
            "The `anthropic` Python package is not installed on this bench. "
            "Run: bench pip install anthropic  — then bench restart."
        )

    key = get_anthropic_key()
    if not key:
        raise RuntimeError(
            "Anthropic API key is not set. Open FlowAgent Settings, "
            "paste your key, save, then run the Engineer again."
        )

    model = get_default_model() or "claude-sonnet-4-5"
    if job_id:
        _append_log(job_id, f"     • Model: {model}", "info")

    # Compose the user message. First iteration = plain goal. Later
    # iterations include what was tried and what went wrong.
    if iteration == 1:
        user_msg = (
            f"Design a workflow for this goal:\n\n{goal}\n\n"
            "REQUIREMENTS:\n"
            "1. Include a `test_payload` field with realistic sample data "
            "   we can use to dry-run the workflow. For a DocType trigger, "
            "   shape it as {\"doc\": {...doctype fields with sensible "
            "   values...}, \"doctype\": \"...\", \"event\": \"...\"}. For "
            "   a Manual trigger, an empty object is fine.\n"
            "2. Include a `reasoning` field (2-4 sentences) explaining "
            "   why this shape solves the goal.\n"
            "3. Use real DocType names and real field names that would "
            "   exist in Frappe/ERPNext — don't invent DocTypes.\n"
            "4. Every node's `cfg` fields must be populated (no empty "
            "   values for required fields like `prompt`, `to`, `subject`, "
            "   `doctype`, etc.)."
        )
    else:
        prior_graph = json.dumps({
            "trigger": prior_workflow.get("trigger"),
            "nodes":   [{"id": n.get("id"), "type": n.get("type"),
                         "label": n.get("label"),
                         "cfg": n.get("cfg", {})} for n in prior_workflow.get("nodes", [])],
            "edges":   prior_workflow.get("edges"),
        }, indent=2)[:6000]
        user_msg = (
            f"GOAL: {goal}\n\n"
            f"ITERATION {iteration} — PREVIOUS ATTEMPT FAILED.\n\n"
            f"THE WORKFLOW YOU BUILT LAST TIME:\n{prior_graph}\n\n"
            f"WHAT WENT WRONG:\n{prior_error or 'Unknown'}\n\n"
        )
        if prior_run_summary:
            user_msg += (
                "TEST RUN DETAILS (which steps ran, which failed):\n"
                f"{json.dumps(prior_run_summary, indent=2)[:3500]}\n\n"
            )
        user_msg += (
            "YOUR JOB: fix the specific issue above. Do not regenerate a "
            "similar workflow — CHANGE something concrete that addresses "
            "the failure.\n\n"
            "Common fixes to consider:\n"
            "- If a node's cfg field was empty or wrong → fill it correctly\n"
            "- If a DocType or field name didn't exist → use a real one\n"
            "- If a step's input was missing → add an upstream node to "
            "  produce that value, or change the Jinja reference to a "
            "  variable that actually exists in context\n"
            "- If the workflow was missing a whole step (e.g. goal said "
            "  'send email' but no int_email node) → add the node and "
            "  wire it up\n"
            "- If the trigger's test_payload didn't cover a field the "
            "  workflow reads → add that field to test_payload\n\n"
            "In `reasoning`, name the SPECIFIC change you made and why "
            "it fixes the failure. Don't be generic. Return the FULL "
            "corrected workflow (not a delta), plus the updated "
            "`test_payload` and `reasoning`."
        )

    engineer_system = SYSTEM_PROMPT + "\n\n" + (
        "You are operating in ENGINEER mode: your JSON output MUST also "
        "include a `test_payload` object (a synthetic input to dry-run "
        "against) and a `reasoning` string (1-3 sentences about your "
        "design choices). All other rules from the base prompt apply."
    )

    # Anthropic client with an EXPLICIT timeout. Without this, a hung
    # network connection would block the whole worker until Frappe's
    # 30-min RQ timeout fires — during which the modal shows the
    # design phase forever with no feedback.
    #
    # 180 seconds is plenty for even a slow, big-context response;
    # anything longer than that is almost certainly a stuck connection
    # and we're better off failing loudly.
    client = Anthropic(api_key=key, timeout=180.0)

    if job_id:
        _append_log(
            job_id,
            f"     • Calling Anthropic API "
            f"(prompt: {len(user_msg)} chars, max_tokens: 6000)…",
            "info",
        )

    api_t0 = time.monotonic()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=6000,
            system=engineer_system,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        # Distinguish common failure modes for a clearer log.
        api_ms = int((time.monotonic() - api_t0) * 1000)
        cls = type(e).__name__
        if "timeout" in str(e).lower() or "Timeout" in cls:
            raise RuntimeError(
                f"Anthropic API timed out after {api_ms}ms. "
                "Check the bench's outbound network access to "
                "api.anthropic.com — a firewall / proxy is the usual cause."
            ) from e
        if "401" in str(e) or "authentication" in str(e).lower():
            raise RuntimeError(
                "Anthropic authentication failed. The API key in "
                "FlowAgent Settings is invalid or revoked."
            ) from e
        if "404" in str(e) and "model" in str(e).lower():
            raise RuntimeError(
                f"Anthropic doesn't recognise model '{model}'. Update the "
                "default model in FlowAgent Settings to a current one "
                "(e.g. claude-sonnet-4-5)."
            ) from e
        raise RuntimeError(f"Anthropic API call failed after {api_ms}ms: {cls}: {e}") from e

    api_ms = int((time.monotonic() - api_t0) * 1000)
    raw = "".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ).strip()

    if job_id:
        _append_log(
            job_id,
            f"     • API responded in {api_ms}ms with {len(raw)} chars",
            "info",
        )

    if not raw:
        raise RuntimeError(
            "Anthropic returned an empty response. This usually means "
            "the model hit its output cap or safety filter. Try a "
            "shorter / simpler goal, or change the default model."
        )

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
def _test(workflow_name: str, test_payload: dict, test_mode: str,
          user: str = "Administrator") -> dict:
    """Run the workflow and return a summary of what happened.

    Uses dry_run mode by default — nodes report what they *would* do
    without side effects. `test_mode='live'` runs for real (may create
    docs, send emails, spend AI tokens).

    `user` is the identity to run under. We accept it explicitly rather
    than reading frappe.session.user because inside a background worker
    the session user can be Guest / unset.
    """
    from ..engine.runner import Runner

    runner = Runner(
        workflow_name=workflow_name,
        trigger_source=f"engineer_test:{test_mode}",
        payload=test_payload or {},
        user=user,
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
