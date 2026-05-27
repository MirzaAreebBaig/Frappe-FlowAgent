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


def render(template: str, data: dict) -> str:
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
    """
    if not template or not isinstance(template, str):
        return template

    # If the string has no Jinja markers, fast-path return it.
    if "{{" not in template and "{%" not in template:
        return template

    try:
        return frappe.render_template(template, data)
    except Exception as e:
        # Don't break the workflow on a render error — log it and return
        # the literal template so the user can see what failed. The runner
        # surfaces this in the step trace.
        frappe.log_error(
            title="FlowAgent: template render error",
            message=f"{type(e).__name__}: {e}\n\nTemplate:\n{template[:1000]}",
        )
        return f"[render error: {e}]"


def _json_safe(value: Any) -> Any:
    """Convert to something json.dumps can definitely handle."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
