# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
AI Build: natural language → workflow graph.

Called from the Studio's "AI Build" sidebar. The user types something
like "When a Sales Invoice is submitted, extract key data with AI, check
if amount > 50000, then send a WhatsApp approval request" and we return
a workflow JSON that the canvas drops directly onto the screen.

This is server-side rather than browser-side because the API key cannot
leak to the client. The Anthropic call carries a strict system prompt
listing valid node types and a JSON schema for the response.
"""

from __future__ import annotations

import json
import re

import frappe


# Keep this list in sync with engine/nodes/__init__.py - all_node_types()
VALID_NODE_TYPES = [
    "trigger_doctype", "trigger_webhook", "trigger_schedule", "trigger_manual", "trigger_form",
    "ai_llm", "ai_extract", "ai_classify", "ai_sentiment", "ai_agent", "ai_vision",
    "logic_condition", "logic_loop", "logic_wait", "logic_parallel",
    "logic_subworkflow", "logic_approval",
    "frappe_create", "frappe_update", "frappe_fetch", "frappe_query",
    "frappe_submit", "frappe_script",
    "int_email", "int_whatsapp", "int_http", "int_slack", "int_sheets", "int_razorpay",
    "tf_mapper", "tf_jinja", "tf_code",
]


SYSTEM_PROMPT = f"""You are a workflow builder for FlowAgent, a visual automation tool for Frappe / ERPNext. The user describes a workflow in plain English. You translate that into a JSON workflow graph.

OUTPUT FORMAT — return ONLY valid JSON, no markdown fences, no prose:

{{
  "workflow_name": "Short Title Case Name",
  "description": "one sentence",
  "trigger": {{
    "type": "DocType Event" | "Schedule" | "Webhook" | "Manual",
    "doctype": "Sales Invoice",       // if DocType Event
    "event": "After Submit",          // if DocType Event: After Insert | After Save | After Submit | After Cancel | After Delete | On Change
    "cron": "0 9 * * *"               // if Schedule
  }},
  "nodes": [
    {{
      "id": "n1",
      "type": "trigger_doctype",
      "x": 30, "y": 120,
      "cfg": {{ "doctype": "Sales Invoice", "event": "After Submit" }}
    }},
    ...
  ],
  "edges": [
    {{ "from": "n1", "to": "n2" }},
    {{ "from": "n3", "to": "n4", "fromPort": "out-yes" }},
    {{ "from": "n3", "to": "n5", "fromPort": "out-no" }}
  ]
}}

VALID NODE TYPES:
{', '.join(VALID_NODE_TYPES)}

LAYOUT RULES:
- Place nodes left-to-right: x starts at 30, increment by ~200 per column
- y centered around 150; stagger to ~80 and ~220 for parallel branches
- Use string IDs like "n1", "n2", ...

CONFIG GUIDANCE (cfg fields per node type):
- trigger_doctype: doctype, event
- trigger_schedule: cron
- trigger_form: form_slug (informational)
- ai_llm: prompt, output (variable name)
- ai_extract: source (Jinja, defaults to last output), fields (comma list or JSON), output
- ai_classify: text, categories (csv), output
- ai_agent: task, allowed_doctypes (csv), can_write (bool), output
- logic_condition: expr (e.g. "amount > 50000" or "{{{{extracted.score}}}} == 'hot'")
- logic_wait: seconds
- logic_subworkflow: target_workflow, payload (JSON, optional), output
- logic_approval: approvers (csv emails), subject, message, timeout_hours, on_timeout (approve/reject/fail)
- frappe_create: doctype, values (JSON string)
- frappe_update: doctype, name, fields (JSON string)
- frappe_fetch: doctype, filters (JSON), fields, limit, output
- frappe_query: doctype, filters (dict or list of [field, op, value]), fields (csv - supports "count(name) as c", "sum(x) as t"), group_by, order_by, limit, output
- int_email: to, subject, body
- int_whatsapp: to, message
- int_slack: channel, message
- int_http: url, method, body
- tf_jinja: template, output

JINJA: Reference upstream node outputs via {{{{output_var}}}} or {{{{trigger.field}}}}. Anything saved under an "output" cfg key is available downstream.

WIRING:
- Branching nodes (logic_condition) must have TWO outgoing edges with fromPort="out-yes" and "out-no"
- logic_approval has TWO outgoing edges with fromPort="out-approve" and "out-reject"
- All other nodes have a single outgoing edge (no fromPort needed)
- The trigger node must be node 0 / "n1"

Return only the JSON object. Nothing before, nothing after."""


MODIFY_PROMPT_ADDENDUM = """

YOU ARE MODIFYING AN EXISTING WORKFLOW.

Below is the user's current workflow as JSON. Apply the user's requested change and return the COMPLETE updated workflow in the same output format. Important rules:

1. Preserve nodes the user didn't ask to change. Keep their id, x, y, type, and cfg as-is.
2. Only add, remove, or modify nodes the change clearly requires.
3. If you add new nodes, pick fresh ids that don't collide (e.g. n100, n101, ...) and place them at sensible x/y coordinates relative to the existing layout.
4. If you remove a node, also remove every edge referencing it.
5. Preserve the existing trigger unless the user's change explicitly asks to alter it.
6. Return the full graph, not a diff.

CURRENT WORKFLOW:
{current_workflow_json}

USER'S REQUESTED CHANGE:"""


@frappe.whitelist()
def build_from_prompt(prompt: str, model: str | None = None,
                      mode: str = "create", current_workflow: str | None = None):
    """Convert a NL workflow description into a graph JSON.

    Args:
        prompt: User's natural-language description.
        model: Override the default Anthropic model.
        mode: "create" (default) or "modify".
        current_workflow: JSON string of the current workflow when mode="modify".
                          Shape: {"workflow_name", "trigger", "nodes", "edges"}.
    """
    if not (
        "System Manager" in frappe.get_roles()
        or "FlowAgent Manager" in frappe.get_roles()
    ):
        frappe.throw("Not permitted", frappe.PermissionError)

    from ..flowagent_core.doctype.flowagent_settings.flowagent_settings import (
        get_anthropic_key, get_default_model,
    )
    try:
        from anthropic import Anthropic
    except ImportError:
        frappe.throw("Install the anthropic package: pip install anthropic")

    key = get_anthropic_key()
    if not key:
        frappe.throw("Set the Anthropic API key in FlowAgent Settings before using AI Build")

    # Compose the system prompt — base + (optional) modify addendum carrying
    # the current workflow.
    system_prompt = SYSTEM_PROMPT
    user_message = prompt
    if mode == "modify":
        if not current_workflow:
            frappe.throw("modify mode requires current_workflow")
        try:
            current = json.loads(current_workflow) if isinstance(current_workflow, str) else current_workflow
        except json.JSONDecodeError:
            frappe.throw("current_workflow must be valid JSON")
        # Trim down to just what the model needs
        trimmed = {
            "workflow_name": current.get("workflow_name", ""),
            "trigger": current.get("trigger", {}),
            "nodes": current.get("nodes", []),
            "edges": current.get("edges", []),
        }
        system_prompt = SYSTEM_PROMPT + MODIFY_PROMPT_ADDENDUM.format(
            current_workflow_json=json.dumps(trimmed, indent=2)
        )

    client = Anthropic(api_key=key)
    response = client.messages.create(
        model=model or get_default_model(),
        max_tokens=4000,  # modify mode returns the whole graph, so give it room
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()

    # Strip code fences if the model produced them despite instructions
    cleaned = _strip_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Last-ditch: find the first {...} balanced block
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            frappe.throw(f"AI returned non-JSON: {raw[:300]}")
        parsed = json.loads(m.group(0))

    # Light validation — drop unknown node types so the canvas doesn't blow up
    parsed["nodes"] = [n for n in parsed.get("nodes", []) if n.get("type") in VALID_NODE_TYPES]
    # Tell the frontend which mode we used so the canvas can react accordingly
    parsed["_mode"] = mode
    return parsed


def _strip_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()
