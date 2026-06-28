# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
AI nodes — the differentiator.

These wrap the Anthropic API with task-specific shapes:

* ai_llm        — open-ended prompt → text
* ai_extract    — JSON extraction with a declared schema
* ai_classify   — pick one label from a fixed set
* ai_sentiment  — short-cut classifier with predefined labels
* ai_vision     — image / PDF OCR + understanding
* ai_agent      — ReAct loop: LLM with tool use, can call Frappe DocType
                  reads/writes until it produces a final answer

All nodes share the same client helper which respects the configured
model and key from FlowAgent Settings.
"""

from __future__ import annotations

import base64
import json
import re

import frappe

from . import BaseExecutor, node


# -------------------------------------------------------------------------
# Anthropic client helper
# -------------------------------------------------------------------------
def _client():
    from flowagent.flowagent_core.doctype.flowagent_settings.flowagent_settings import (
        get_anthropic_key,
    )
    try:
        from anthropic import Anthropic
    except ImportError:
        frappe.throw(
            "The 'anthropic' Python package is not installed. "
            "Run: pip install anthropic"
        )
    key = get_anthropic_key()
    if not key:
        frappe.throw(
            "No Anthropic API key configured. Set it in FlowAgent Settings, "
            "or via site_config 'anthropic_api_key', or env ANTHROPIC_API_KEY."
        )
    return Anthropic(api_key=key)


def _model(cfg: dict) -> str:
    from flowagent.flowagent_core.doctype.flowagent_settings.flowagent_settings import (
        get_default_model,
    )
    return cfg.get("model") or get_default_model()


def _extract_text(response) -> str:
    """Pull text out of an Anthropic Message response."""
    parts = []
    for block in (response.content or []):
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


# Approximate per-million-token prices for the standard Anthropic models.
# We store these client-side too so they update without a release, but
# this is a safe fallback. Prices are in USD per million tokens.
_MODEL_PRICES = {
    # Claude Sonnet 4.x
    "claude-sonnet-4":         {"in": 3.0,  "out": 15.0},
    "claude-sonnet-4-5":       {"in": 3.0,  "out": 15.0},
    "claude-sonnet-4-20250514": {"in": 3.0, "out": 15.0},
    # Claude Opus 4.x
    "claude-opus-4":           {"in": 15.0, "out": 75.0},
    "claude-opus-4-5":         {"in": 15.0, "out": 75.0},
    # Claude Haiku
    "claude-haiku-4-5":        {"in": 1.0,  "out": 5.0},
    "claude-haiku-3-5":        {"in": 0.8,  "out": 4.0},
}


def _record_usage(runner, model: str, response) -> None:
    """Read input_tokens / output_tokens from an Anthropic response and
    accumulate onto the runner. Best-effort — Anthropic libraries have
    used slightly different shapes over time, so we try a few paths.
    """
    if not runner:
        return
    usage = getattr(response, "usage", None)
    if not usage:
        return
    in_tok = getattr(usage, "input_tokens", 0) or 0
    out_tok = getattr(usage, "output_tokens", 0) or 0
    # Initialise on first call
    if not hasattr(runner, "_token_usage"):
        runner._token_usage = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
    runner._token_usage["input"]  += in_tok
    runner._token_usage["output"] += out_tok
    runner._token_usage["calls"]  += 1
    # Estimate cost using whatever prefix of the model name we match
    # (Anthropic appends date suffixes that change over time).
    price = None
    if model in _MODEL_PRICES:
        price = _MODEL_PRICES[model]
    else:
        for k, p in _MODEL_PRICES.items():
            if model.startswith(k):
                price = p
                break
    if price:
        runner._token_usage["cost_usd"] += (
            in_tok  * price["in"]  / 1_000_000 +
            out_tok * price["out"] / 1_000_000
        )


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


# -------------------------------------------------------------------------
# 1. Open-ended LLM prompt
# -------------------------------------------------------------------------
@node("ai_llm")
class LLMPromptNode(BaseExecutor):
    """Plain prompt → text response.

    cfg:
      prompt        — the (rendered) prompt string
      system        — optional system prompt
      model         — optional model override
      max_tokens    — default 1024
      output        — variable name to store the text under
    """

    def run(self, *, node, cfg, context, runner):
        client = _client()
        model = _model(cfg)
        kwargs = {
            "model": model,
            "max_tokens": int(cfg.get("max_tokens") or 1024),
            "messages": [{"role": "user", "content": cfg.get("prompt", "")}],
        }
        sys_prompt = cfg.get("system")
        if sys_prompt:
            kwargs["system"] = sys_prompt
        response = client.messages.create(**kwargs)
        _record_usage(runner, model, response)
        text = _extract_text(response)
        return text


# -------------------------------------------------------------------------
# 2. Structured extraction
# -------------------------------------------------------------------------
@node("ai_extract")
class ExtractNode(BaseExecutor):
    """Extract structured fields from arbitrary text.

    cfg:
      source     — the text to extract from (Jinja-rendered)
      fields     — comma-separated field names, or a JSON object describing
                   field name → description
      output     — variable name to store the result dict under
    """

    def run(self, *, node, cfg, context, runner):
        source = cfg.get("source") or cfg.get("text") or ""
        if not source:
            # Default to most recent output if no source given
            source = json.dumps(context.get("$last"), default=str)

        fields_raw = cfg.get("fields") or ""
        schema = self._build_schema(fields_raw)
        if not schema:
            frappe.throw("ai_extract needs at least one field to extract")

        client = _client()
        field_lines = "\n".join(f"  - {k}: {desc}" for k, desc in schema.items())
        prompt = (
            "Extract the following fields from the source text. "
            "Return ONLY a JSON object with these keys, no prose, no markdown.\n\n"
            f"Fields to extract:\n{field_lines}\n\n"
            f"Source text:\n{source}\n\n"
            "JSON:"
        )
        model = _model(cfg)
        response = client.messages.create(
            model=model,
            max_tokens=int(cfg.get("max_tokens") or 1024),
            messages=[{"role": "user", "content": prompt}],
        )
        _record_usage(runner, model, response)
        text = _strip_code_fences(_extract_text(response))
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find a JSON object embedded in the response
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            frappe.throw(f"ai_extract: model returned non-JSON: {text[:300]}")

    def _build_schema(self, fields_raw: str) -> dict:
        fields_raw = (fields_raw or "").strip()
        if fields_raw.startswith("{"):
            try:
                return json.loads(fields_raw)
            except json.JSONDecodeError:
                pass
        # Comma-separated bare field names
        return {f.strip(): f.strip() for f in fields_raw.split(",") if f.strip()}


# -------------------------------------------------------------------------
# 3. Classifier
# -------------------------------------------------------------------------
@node("ai_classify")
class ClassifyNode(BaseExecutor):
    """Pick one category from a fixed set.

    cfg:
      text        — input text
      categories  — comma-separated category labels
      instructions — optional extra steering
      output      — variable to store the chosen category
    """

    def run(self, *, node, cfg, context, runner):
        text = cfg.get("text") or json.dumps(context.get("$last"), default=str)
        cats = [c.strip() for c in (cfg.get("categories") or "").split(",") if c.strip()]
        if not cats:
            frappe.throw("ai_classify requires non-empty 'categories'")
        instructions = cfg.get("instructions") or ""

        prompt = (
            f"Classify the input into exactly one of these categories: {', '.join(cats)}.\n"
            f"{instructions}\n\n"
            f"Input:\n{text}\n\n"
            "Reply with ONLY the chosen category label, nothing else."
        )
        client = _client()
        model = _model(cfg)
        response = client.messages.create(
            model=model,
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        _record_usage(runner, model, response)
        chosen = _extract_text(response).strip().strip(".\"'")
        # Sanity-check the response — if the model returned junk, fall back to closest match
        for c in cats:
            if c.lower() == chosen.lower():
                return c
        # Substring / partial match
        for c in cats:
            if c.lower() in chosen.lower():
                return c
        # Last resort: return the raw response (caller can decide what to do)
        return chosen or cats[0]


# -------------------------------------------------------------------------
# 4. Sentiment (specialised classifier)
# -------------------------------------------------------------------------
@node("ai_sentiment")
class SentimentNode(BaseExecutor):
    """positive / negative / neutral / mixed."""

    LABELS = ["positive", "negative", "neutral", "mixed"]

    def run(self, *, node, cfg, context, runner):
        text = cfg.get("text") or ""
        client = _client()
        model = _model(cfg)
        response = client.messages.create(
            model=model,
            max_tokens=80,
            messages=[{"role": "user", "content": (
                "Classify the sentiment of the following text. Reply with a JSON "
                f"object: {{\"sentiment\": one of {self.LABELS}, \"score\": float in [-1, 1]}}\n\n"
                f"Text:\n{text}\n\nJSON:"
            )}],
        )
        _record_usage(runner, model, response)
        raw = _strip_code_fences(_extract_text(response))
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"sentiment": "neutral", "score": 0.0, "raw": raw}
        return parsed


# -------------------------------------------------------------------------
# 5. Vision / OCR
# -------------------------------------------------------------------------
@node("ai_vision")
class VisionNode(BaseExecutor):
    """Send an image (URL or Frappe File doc) to Claude for OCR / understanding.

    cfg:
      file_url    — public or private Frappe file URL
      prompt      — what to do with the image
      output      — variable name
    """

    def run(self, *, node, cfg, context, runner):
        file_url = cfg.get("file_url", "")
        prompt = cfg.get("prompt") or "Extract all text from this image."

        if not file_url:
            frappe.throw("ai_vision requires file_url")

        image_block = self._build_image_block(file_url)

        client = _client()
        model = _model(cfg)
        response = client.messages.create(
            model=model,
            max_tokens=int(cfg.get("max_tokens") or 1500),
            messages=[{
                "role": "user",
                "content": [image_block, {"type": "text", "text": prompt}],
            }],
        )
        _record_usage(runner, model, response)
        return _extract_text(response)

    def _build_image_block(self, file_url: str) -> dict:
        # Two paths: external URL → pass through as URL; Frappe file → read
        # bytes off disk and embed as base64.
        if file_url.startswith("http://") or file_url.startswith("https://"):
            return {"type": "image", "source": {"type": "url", "url": file_url}}

        # Frappe private/public file path → resolve to bytes.
        # Defence in depth: even though workflow configs are admin-authored,
        # the file_url is typically a Jinja template like {{ trigger.doc.attachment }}
        # so a malicious document could feed an arbitrary path. We validate
        # the resolved path is within Frappe's files directory before opening.
        from frappe.utils.file_manager import get_file_path
        import os
        path = get_file_path(file_url)
        resolved = os.path.realpath(path)
        allowed_roots = [
            os.path.realpath(frappe.get_site_path("public", "files")),
            os.path.realpath(frappe.get_site_path("private", "files")),
        ]
        if not any(resolved.startswith(root + os.sep) or resolved == root
                   for root in allowed_roots):
            frappe.throw(
                f"ai_vision: refusing to read file outside Frappe's files "
                f"directory: {file_url}"
            )

        with open(resolved, "rb") as fh:  # nosemgrep: frappe-security-file-traversal
            raw = fh.read()
        media_type = "image/jpeg"
        if file_url.lower().endswith(".png"): media_type = "image/png"
        elif file_url.lower().endswith(".webp"): media_type = "image/webp"
        elif file_url.lower().endswith(".gif"): media_type = "image/gif"
        b64 = base64.b64encode(raw).decode("ascii")
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }


# -------------------------------------------------------------------------
# 6. Auto Agent — the marquee node
# -------------------------------------------------------------------------
@node("ai_agent")
class AgentNode(BaseExecutor):
    """ReAct-style agent loop with Frappe DocType tools.

    The LLM is given:
      - a system prompt describing its task
      - a set of tools, each backed by a Frappe operation
        (read doc, list docs, update doc, search)
      - a maximum iteration budget (from settings)

    The loop:
      1. Send messages to Claude
      2. If response is text only → done, return text
      3. If response contains tool_use blocks → execute each one,
         append tool_result(s) to messages, go to 1
      4. If we exceed max iterations → return whatever we have

    cfg:
      task         — natural-language description of what to do
      allowed_doctypes — comma-separated list of DocTypes the agent can touch
                         (whitelist; defaults to none for safety)
      max_iters    — override the settings default
      can_write    — bool; if false, only read tools are exposed
    """

    def run(self, *, node, cfg, context, runner):
        client = _client()
        settings = runner.settings
        max_iters = int(cfg.get("max_iters") or settings.max_agent_iterations or 8)

        allowed = [d.strip() for d in (cfg.get("allowed_doctypes") or "").split(",") if d.strip()]
        can_write = bool(cfg.get("can_write") in (True, "true", "True", "1", 1))

        tools = _build_agent_tools(allowed, can_write)
        system = (
            "You are a workflow automation agent inside a Frappe ERP system. "
            "You complete the user's task by calling tools to read or modify "
            "data, then summarise what you did in plain language. "
            "Prefer the smallest number of tool calls. When you're done, "
            "respond with a final text message describing the outcome."
        )
        if cfg.get("system"):
            system = cfg["system"]

        task = cfg.get("task", "")
        # Include the current context as background so the agent has something to chew on
        ctx_summary = json.dumps(context.snapshot(), default=str)[:8000]
        initial = f"Task: {task}\n\nCurrent workflow context:\n{ctx_summary}"

        messages = [{"role": "user", "content": initial}]
        final_text = ""
        tool_log = []

        for iteration in range(max_iters):
            agent_model = _model(cfg)
            response = client.messages.create(
                model=agent_model,
                max_tokens=int(cfg.get("max_tokens") or 1500),
                system=system,
                tools=tools,
                messages=messages,
            )
            _record_usage(runner, agent_model, response)

            # Collect text + tool calls from this turn
            messages.append({"role": "assistant", "content": response.content})

            tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]

            if not tool_use_blocks:
                # Pure text → we're done
                final_text = "".join(b.text for b in text_blocks).strip()
                break

            # Execute each tool call and append a tool_result message
            tool_results = []
            for tb in tool_use_blocks:
                try:
                    result = _execute_agent_tool(tb.name, tb.input, allowed, can_write)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tb.id,
                        "content": json.dumps(result, default=str)[:30000],
                    })
                    tool_log.append({"tool": tb.name, "input": tb.input, "result": result})
                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tb.id,
                        "is_error": True,
                        "content": f"Error: {type(e).__name__}: {e}",
                    })
                    tool_log.append({"tool": tb.name, "input": tb.input, "error": str(e)})

            messages.append({"role": "user", "content": tool_results})

            if response.stop_reason == "end_turn":
                final_text = "".join(b.text for b in text_blocks).strip()
                break
        else:
            # Loop completed without break — hit max_iters
            final_text = final_text or "[Agent hit max iterations without producing a final answer]"

        return {
            "text": final_text,
            "iterations": iteration + 1,
            "tool_calls": tool_log,
        }


# -------------------------------------------------------------------------
# Agent tool definitions
# -------------------------------------------------------------------------
def _build_agent_tools(allowed_doctypes: list, can_write: bool) -> list[dict]:
    """Construct the Anthropic tool schema list for the agent.

    Each tool is a thin wrapper over a frappe DB operation. Doctype access
    is gated by the allowed_doctypes whitelist — the agent literally
    cannot read a doctype that wasn't whitelisted.
    """
    doctype_enum = allowed_doctypes if allowed_doctypes else ["__none__"]
    tools = [
        {
            "name": "list_documents",
            "description": (
                "List documents of a given DocType with optional filters. "
                "Returns up to 20 records with their name and key fields. "
                f"Allowed doctypes: {', '.join(allowed_doctypes) or 'NONE — ask user to whitelist'}"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "doctype": {"type": "string", "enum": doctype_enum},
                    "filters": {
                        "type": "object",
                        "description": "Filter dict, e.g. {\"status\": \"Open\"}",
                    },
                    "limit": {"type": "integer", "default": 20, "maximum": 50},
                },
                "required": ["doctype"],
            },
        },
        {
            "name": "get_document",
            "description": "Fetch a single document by name (primary key) with all its fields.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "doctype": {"type": "string", "enum": doctype_enum},
                    "name": {"type": "string"},
                },
                "required": ["doctype", "name"],
            },
        },
        {
            "name": "count_documents",
            "description": "Count documents matching filters.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "doctype": {"type": "string", "enum": doctype_enum},
                    "filters": {"type": "object"},
                },
                "required": ["doctype"],
            },
        },
    ]

    if can_write:
        tools.extend([
            {
                "name": "update_document",
                "description": "Update fields on an existing document.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string", "enum": doctype_enum},
                        "name": {"type": "string"},
                        "updates": {"type": "object", "description": "Field name → new value"},
                    },
                    "required": ["doctype", "name", "updates"],
                },
            },
            {
                "name": "create_document",
                "description": "Create a new document.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "doctype": {"type": "string", "enum": doctype_enum},
                        "values": {"type": "object"},
                    },
                    "required": ["doctype", "values"],
                },
            },
        ])

    return tools


def _execute_agent_tool(tool_name: str, tool_input: dict, allowed: list, can_write: bool):
    """Run a tool the agent invoked. Strictly validated."""
    doctype = tool_input.get("doctype")
    if doctype and doctype not in allowed:
        return {"error": f"DocType '{doctype}' is not in the allowed list: {allowed}"}

    if tool_name == "list_documents":
        limit = min(int(tool_input.get("limit") or 20), 50)
        filters = tool_input.get("filters") or {}
        return frappe.get_all(doctype, filters=filters, limit=limit, fields=["name"])

    if tool_name == "get_document":
        doc = frappe.get_doc(doctype, tool_input.get("name"))
        return doc.as_dict()

    if tool_name == "count_documents":
        return {"count": frappe.db.count(doctype, filters=tool_input.get("filters") or {})}

    if tool_name == "update_document":
        if not can_write:
            return {"error": "Write tools disabled — set can_write=true on the node"}
        doc = frappe.get_doc(doctype, tool_input["name"])
        for k, v in (tool_input.get("updates") or {}).items():
            doc.set(k, v)
        doc.save()
        return {"updated": doc.name}

    if tool_name == "create_document":
        if not can_write:
            return {"error": "Write tools disabled — set can_write=true on the node"}
        doc = frappe.get_doc({"doctype": doctype, **(tool_input.get("values") or {})})
        doc.insert()
        return {"created": doc.name}

    return {"error": f"Unknown tool '{tool_name}'"}
