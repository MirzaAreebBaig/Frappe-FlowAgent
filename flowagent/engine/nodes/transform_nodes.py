# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Transform nodes — data shaping.
"""

from __future__ import annotations

import json

import frappe

from . import BaseExecutor, node
from ..context import render


@node("tf_mapper")
class FieldMapperNode(BaseExecutor):
    """Map context variables into a new shape.

    cfg.mapping is a JSON object where values are Jinja templates resolved
    against the context, producing a dict output.
    """

    def run(self, *, node, cfg, context, runner):
        raw = cfg.get("mapping") or "{}"
        if isinstance(raw, str):
            try:
                mapping = json.loads(raw)
            except json.JSONDecodeError:
                frappe.throw(f"tf_mapper: invalid JSON mapping: {raw[:120]}")
        else:
            mapping = raw

        out = {}
        for k, v in mapping.items():
            if isinstance(v, str):
                out[k] = render(v, context.data)
            else:
                out[k] = v
        return out


@node("tf_jinja")
class JinjaNode(BaseExecutor):
    """Render a full Jinja template using Frappe's renderer (more powerful
    than the inline {{var}} interpolation — supports loops, conditionals,
    filters)."""

    def run(self, *, node, cfg, context, runner):
        template = cfg.get("template") or ""
        try:
            # SAFETY: `template` comes from cfg.template which is set in
            # the workflow node configuration by a FlowAgent Manager / System
            # Manager (same trust level as Frappe Server Scripts and
            # Notification templates). Sandboxed Jinja blocks dangerous
            # attribute access. End-user input lives in context.data
            # which is interpolated via the data dict argument.
            return frappe.render_template(template, context.data)  # nosemgrep: frappe-ssti
        except Exception as e:
            frappe.throw(f"tf_jinja render error: {e}")


@node("tf_code")
class PythonCodeNode(BaseExecutor):
    """Run sandboxed Python. The snippet has access to `input` (the
    context dict) and should assign to `output`."""

    def run(self, *, node, cfg, context, runner):
        from frappe.utils.safe_exec import safe_exec

        code = cfg.get("code") or ""
        if not code:
            return None
        local = {"input": context.data, "context": context.data, "output": None}
        # SAFETY: `code` is authored by a FlowAgent Manager / System Manager —
        # the same role required to write Frappe Server Scripts. safe_exec
        # uses RestrictedPython (no __import__, no file I/O, no exec, no
        # eval, attribute access gated through Frappe's allowlist). This
        # node is the documented "escape hatch" for advanced users; the
        # sandbox restrictions are the security boundary.
        safe_exec(code, _locals=local)  # nosemgrep: frappe-codeinjection-eval
        return local.get("output")
