# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
Execution context: the shared variable bag a workflow run carries
between nodes, plus the renderer used to interpolate `{{var.path}}`
references in node config values.
"""

from __future__ import annotations

import json
from typing import Any

import frappe


class Context:
    """Lightweight dict-with-dotted-paths plus a few utilities."""

    def __init__(self, seed: dict | None = None):
        self.data: dict[str, Any] = dict(seed or {})

    def get(self, path: str, default: Any = None) -> Any:
        """Get a value via dotted path: 'doc.customer.name'."""
        cur: Any = self.data
        for part in path.split("."):
            if cur is None:
                return default
            if isinstance(cur, dict):
                cur = cur.get(part)
            elif isinstance(cur, (list, tuple)) and part.isdigit():
                idx = int(part)
                cur = cur[idx] if 0 <= idx < len(cur) else None
            else:
                cur = getattr(cur, part, None)
        return cur if cur is not None else default

    def set(self, key: str, value: Any):
        # Top-level assignment by convention; nodes use simple names for
        # their `output` field, no nested writes needed.
        self.data[key] = value

    def snapshot(self) -> dict:
        """Return a JSON-safe copy of the context for persisting in the Run doc."""
        return _json_safe(self.data)


def render(template: str, data: dict, warnings: list | None = None) -> str:
    """Render a Jinja template against the context dict.

    Uses ``frappe.render_template`` (Frappe's sandboxed Jinja2), so:

        {{ var }}                            — variable access
        {{ var.sub.path }}                   — dotted access
        {{ var | upper }}                    — Jinja filters (Frappe whitelisted set)
        {% for item in items %}...{% endfor %} — loops
        {% if x %}...{% else %}...{% endif %}  — conditionals
        {{ var.amount * 100 }}               — arithmetic

    Frappe sandboxes Jinja: no arbitrary imports, no filesystem access,
    no subprocess. A whitelisted set of helpers (``frappe.utils.*``) is
    exposed. For complex logic, the ``tf_code`` node remains the right
    choice.

    If ``warnings`` is provided, any top-level variable referenced in the
    template that isn't present in ``data`` is appended to it. This makes
    silent "renders to empty" cases discoverable in the step trace.
    """
    if not template or not isinstance(template, str):
        return template

    # If the string has no Jinja markers, fast-path return it.
    if "{{" not in template and "{%" not in template:
        return template

    # Pre-flight: collect undefined top-level variable references
    if warnings is not None:
        _collect_undefined_warnings(template, data, warnings)

    try:
        # SAFETY: `template` originates from workflow node configurations
        # which are authored by users with FlowAgent Manager (or System
        # Manager) role — the same trust level required to write any
        # Python/Jinja in Frappe (Server Scripts, Notification templates,
        # Print Formats, etc.). frappe.render_template uses Jinja2's
        # SandboxedEnvironment which blocks attribute access on dunders
        # and dangerous builtins. End-user form input is interpolated
        # via the `data` argument, never the template string itself.
        return frappe.render_template(template, data)  # nosemgrep: frappe-ssti
    except Exception as e:
        # Don't break the workflow on a render error — log it and return
        # the literal template so the user can see what failed. The runner
        # surfaces this in the step trace.
        frappe.log_error(
            title="FlowAgent: template render error",
            message=f"{type(e).__name__}: {e}\n\nTemplate:\n{template[:1000]}",
        )
        return f"[render error: {e}]"


def _collect_undefined_warnings(template: str, data: dict, warnings: list):
    """Scan a Jinja template for top-level identifier references and
    flag any that are missing from ``data``. Only does a shallow scan;
    we're not parsing Jinja — just catching obvious typos like
    ``{{trigger.candidate_skills}}`` when the user meant
    ``{{trigger.doc.candidate_skills}}``.
    """
    import re as _re
    # Find {{name…}} and {% for x in name… %} references
    found_names = set()
    for m in _re.finditer(r"\{\{\s*([A-Za-z_][A-Za-z_0-9]*)", template):
        found_names.add(m.group(1))
    for m in _re.finditer(r"\{%\s*(?:if|elif|for\s+\w+\s+in)\s+([A-Za-z_][A-Za-z_0-9]*)", template):
        found_names.add(m.group(1))

    # Jinja built-ins / loop helpers we should never warn about
    builtins = {"loop", "range", "true", "false", "none", "True", "False", "None",
                "self", "_", "varargs", "kwargs"}

    for name in found_names:
        if name in builtins:
            continue
        if name not in data:
            msg = f"Template references '{name}' but it's not in the run context"
            if msg not in warnings:
                warnings.append(msg)


def _json_safe(value: Any) -> Any:
    """Convert to something json.dumps can definitely handle."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
