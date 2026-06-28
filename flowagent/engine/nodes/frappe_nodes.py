# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Frappe DocType operations.
"""

from __future__ import annotations

import json

import frappe

from . import BaseExecutor, node


def _parse_dict(raw):
    """Accept either a JSON string or a dict; return dict (empty on fail).

    A common failure mode: a user writes `{"field": "{{ some_var }}"}` in the
    UI, and `some_var` resolves to a multi-line string (e.g. AI-generated
    markdown). The raw newlines inside the resulting JSON string literal
    make `json.loads` fail, which used to silently produce an empty dict.

    Now: when the strict parse fails, we attempt a tolerant pass that
    escapes raw control characters (\\n, \\r, \\t) found inside string
    literals. This recovers the common case without changing semantics
    when the input is already valid JSON.
    """
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if not isinstance(raw, str):
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        pass
    # Tolerant pass: walk the string, escape unescaped control chars that
    # appear *inside* double-quoted string literals. Backslash escapes are
    # left alone so legitimate \" and \\ stay intact.
    fixed = _escape_control_chars_in_json_strings(raw)
    try:
        return json.loads(fixed)
    except (TypeError, ValueError):
        return {}


def _escape_control_chars_in_json_strings(s: str) -> str:
    """Walk a JSON-ish string and escape any literal control characters
    (newline, CR, tab) that appear inside double-quoted string literals.

    State machine: track whether we're inside a "..." literal, and respect
    backslash escapes so \\" doesn't end the literal prematurely. Control
    chars outside literals (which JSON allows — they're whitespace) are
    left untouched.
    """
    out = []
    in_str = False
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                # Pass through any escape sequence as-is
                out.append(ch)
                out.append(s[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
                out.append(ch)
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
        i += 1
    return "".join(out)


@node("frappe_create")
class CreateDocNode(BaseExecutor):
    """Create a new document. cfg.doctype, cfg.values (JSON)."""

    def run(self, *, node, cfg, context, runner):
        doctype = cfg.get("doctype")
        if not doctype:
            frappe.throw("frappe_create requires a doctype")
        values = _parse_dict(cfg.get("values") or cfg.get("fields"))
        if runner.dry_run:
            # Don't actually insert; return a dummy doc shape so downstream
            # nodes can run normally
            return {
                "_dry_run": True,
                "name": f"DRY-RUN-{doctype}-{frappe.generate_hash(length=6)}",
                **values,
            }
        doc = frappe.get_doc({"doctype": doctype, **values})
        doc.insert()
        _mark_owned(runner, doctype, doc.name)
        return {"name": doc.name, **{k: doc.get(k) for k in values.keys() if doc.get(k) is not None}}


@node("frappe_update")
class UpdateDocNode(BaseExecutor):
    """Update fields on an existing doc. cfg.doctype, cfg.name, cfg.fields/values."""

    def run(self, *, node, cfg, context, runner):
        doctype = cfg.get("doctype")
        name = cfg.get("name") or context.get("doc_name") or context.get("doc", {}).get("name")
        if not doctype:
            frappe.throw("frappe_update: 'DocType' is empty. Set it on the node.")
        if not name:
            raw_name = (node.get("cfg") or {}).get("name") or ""
            hint = (
                f" The template was: {raw_name!r}. If it contains "
                f"{{{{trigger.doc.name}}}} or similar, the trigger context "
                f"may be empty — run this workflow against an actual record "
                f"via the 'Run' dialog or wait for it to fire from a real "
                f"DocType event."
            ) if "{{" in raw_name else ""
            frappe.throw(f"frappe_update: 'Document name' resolved to empty.{hint}")
        raw_fields = cfg.get("fields") or cfg.get("values")
        values = _parse_dict(raw_fields)
        if not values:
            # Give the user something useful to diagnose with. The most
            # common cause is a Jinja substitution that produced unquoted
            # text or unbalanced braces; second is leaving the field blank.
            preview = ""
            if raw_fields:
                preview = str(raw_fields)[:200]
                if len(str(raw_fields)) > 200:
                    preview += "…"
            tip = ""
            if raw_fields and "{{" in str(raw_fields):
                tip = (
                    " Hint: when substituting multi-line text (e.g. AI output) "
                    "into a JSON value, wrap it with the |tojson filter: "
                    '{"field": {{ your_var | tojson }}} — note no quotes '
                    "around the placeholder."
                )
            frappe.throw(
                "frappe_update: 'Fields' is empty or not valid JSON. "
                'Provide a JSON object like {"status": "Done"}.'
                + (f" Got: {preview!r}." if preview else "")
                + tip
            )
        if runner.dry_run:
            return {
                "_dry_run": True,
                "name": name,
                "would_update_fields": list(values.keys()),
                "values": values,
            }
        # Mark owned BEFORE the save — the dispatcher fires synchronously
        # during save(), so the flag must be set first.
        _mark_owned(runner, doctype, name)
        doc = frappe.get_doc(doctype, name)
        for k, v in values.items():
            doc.set(k, v)
        doc.save()
        return {"name": doc.name, "updated_fields": list(values.keys())}


@node("frappe_fetch")
class FetchDocNode(BaseExecutor):
    """Fetch documents. Two modes:
       - cfg.name set → fetch single doc, return dict
       - else → list query with cfg.filters (JSON), cfg.fields (csv), cfg.limit
    """

    def run(self, *, node, cfg, context, runner):
        doctype = cfg.get("doctype")
        if not doctype:
            frappe.throw("frappe_fetch requires a doctype")

        if cfg.get("name"):
            doc = frappe.get_doc(doctype, cfg["name"])
            return doc.as_dict()

        filters = _parse_dict(cfg.get("filters"))
        fields_csv = cfg.get("fields") or "name"
        fields = [f.strip() for f in fields_csv.split(",") if f.strip()]
        limit = int(cfg.get("limit") or 20)
        order_by = cfg.get("order_by") or "modified desc"
        return frappe.get_all(doctype, filters=filters, fields=fields, limit=limit, order_by=order_by)


@node("frappe_submit")
class SubmitDocNode(BaseExecutor):
    """Submit (docstatus → 1) a submittable doc."""

    def run(self, *, node, cfg, context, runner):
        doctype = cfg.get("doctype")
        name = cfg.get("name")
        if not (doctype and name):
            frappe.throw("frappe_submit requires doctype and name")
        if runner.dry_run:
            return {"_dry_run": True, "name": name, "would_submit": True}
        _mark_owned(runner, doctype, name)
        doc = frappe.get_doc(doctype, name)
        doc.submit()
        return {"name": doc.name, "docstatus": 1}


def _mark_owned(runner, doctype: str, name: str):
    """Record a doc as owned by the current workflow run. The dispatcher
    consults this set before firing — owned docs don't re-trigger the
    workflow that's mutating them."""
    try:
        from ...triggers.loop_guard import mark_doc_owned
        mark_doc_owned(runner.workflow_name, doctype, name)
    except Exception:
        # Loop guard is defense-in-depth; don't let it break a save.
        pass


@node("frappe_script")
class ServerScriptNode(BaseExecutor):
    """Run a sandboxed Python snippet.

    Uses Frappe's safe_exec which restricts builtins. The snippet has
    access to `context` (dict) and `frappe` (limited interface). It
    should assign to `result` for the output.
    """

    def run(self, *, node, cfg, context, runner):
        from frappe.utils.safe_exec import safe_exec

        code = cfg.get("script") or cfg.get("code") or ""
        if not code:
            return None
        if runner.dry_run:
            # We can't statically know if a script mutates, so skip in dry mode.
            return {"_dry_run": True, "would_run_script": code[:200]}
        local = {"context": context.data, "result": None, "input": context.data}
        # SAFETY: `code` is authored in the workflow node config by a
        # FlowAgent Manager / System Manager — the same role required for
        # Frappe Server Scripts. safe_exec uses RestrictedPython (no
        # __import__, file I/O, exec, eval; attribute access gated through
        # Frappe's allowlist). The frappe_script node is the documented
        # escape hatch for advanced users; the sandbox is the security
        # boundary, not the static check.
        safe_exec(code, _locals=local)  # nosemgrep: frappe-codeinjection-eval
        return local.get("result")
