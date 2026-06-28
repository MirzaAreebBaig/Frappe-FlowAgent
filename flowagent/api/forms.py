# Copyright (c) 2026, FlowAgent
# For license information, please see license.txt
"""
Public form submission endpoint.

A hosted form at /f/<slug> POSTs to
/api/method/flowagent.api.forms.submit (slug in body or query),
which:
  1. Validates the slug → resolves to a FlowAgent Form
  2. Validates the submission against the form's schema
  3. Applies IP-based rate limiting
  4. Creates a Workflow Run for the configured workflow
  5. Returns success / redirect URL / errors as JSON

The hosted form template at flowagent/www/flowagent_form.html
calls this endpoint via fetch().
"""
from __future__ import annotations

import json

import frappe
from frappe.utils import cint, now_datetime


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit(slug: str = None, **data):
    """Accept a form submission, trigger the configured workflow.

    `data` is whatever the form POSTed minus the slug parameter. We
    validate against the form's schema before enqueuing the workflow.
    """
    if not slug:
        # Sometimes the slug comes via the URL path rewrite, sometimes
        # as a body field. Try frappe.form_dict as a fallback.
        slug = frappe.form_dict.get("slug")
    if not slug:
        return {"ok": False, "error": "Missing slug parameter"}

    # Resolve the form
    forms = frappe.get_all(
        "FlowAgent Form",
        filters={"slug": slug, "enabled": 1},
        fields=["name"],
        limit=1,
        ignore_permissions=True,
    )
    if not forms:
        return {"ok": False, "error": "Form not found or disabled"}

    form = frappe.get_doc("FlowAgent Form", forms[0]["name"])

    # Rate limit per IP
    if form.rate_limit_per_hour and form.rate_limit_per_hour > 0:
        ip = _client_ip()
        if not _rate_limit_ok(form.name, ip, form.rate_limit_per_hour):
            return {
                "ok": False,
                "error": "Rate limit exceeded — please try again later",
            }

    # Validate submission against schema
    try:
        schema = json.loads(form.schema or "[]")
    except Exception:
        return {"ok": False, "error": "Form is misconfigured (invalid schema)"}

    cleaned, errors = _validate_against_schema(data, schema)
    if errors:
        return {"ok": False, "error": "Validation failed", "field_errors": errors}

    # Build the payload passed to the workflow runner. We pass both the
    # raw submission dict and a `form` namespace with metadata.
    payload = {
        "doc": cleaned,             # flat field-by-field access ({{ email }})
        **cleaned,                  # also flat at top level for convenience
        "form": {
            "name": form.name,
            "slug": form.slug,
            "submitted_at": str(now_datetime()),
            "ip": _client_ip(),
        },
    }

    # Enqueue the workflow run. We create the run doc first so we can
    # return its name immediately (useful for redirect_url templating).
    try:
        run = frappe.new_doc("FlowAgent Workflow Run")
        run.workflow = form.workflow
        run.status = "Queued"
        run.trigger_source = f"form:{form.slug}"
        run.trigger_payload = json.dumps(payload, default=str)[:140000]
        run.flags.ignore_permissions = True
        run.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.enqueue(
            "flowagent.engine.run_workflow_background",
            workflow_name=form.workflow,
            trigger_source=f"form:{form.slug}",
            payload=payload,
            existing_run_name=run.name,
            queue="default",
            timeout=600,
        )
    except Exception as e:
        frappe.log_error(
            title=f"FlowAgent form '{form.slug}' submission failed",
            message=f"{type(e).__name__}: {e}",
        )
        return {"ok": False, "error": "Submission could not be processed"}

    # Build response. If a redirect URL is configured, expand {{ run_name }}.
    response = {
        "ok": True,
        "message": form.success_message or "Thanks!",
        "run": run.name,
    }
    if form.redirect_url:
        redirect = form.redirect_url.replace("{{ run_name }}", run.name)
        redirect = redirect.replace("{{run_name}}", run.name)
        response["redirect"] = redirect
    return response


def _validate_against_schema(submission: dict, schema: list) -> tuple[dict, dict]:
    """Filter the submission to declared fields, coerce types, surface errors.

    Returns (cleaned_data, field_errors_dict).
    """
    cleaned: dict = {}
    errors: dict = {}

    declared_names = {f.get("name") for f in schema if f.get("name")}

    for field in schema:
        name = field.get("name")
        if not name:
            continue
        ftype = field.get("type", "text")
        required = bool(field.get("required"))
        raw = submission.get(name)

        # Required check first
        if required and (raw is None or (isinstance(raw, str) and not raw.strip())):
            errors[name] = "Required"
            continue
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            cleaned[name] = "" if ftype != "checkbox" else False
            continue

        # Type coercion / validation
        if ftype == "number":
            try:
                cleaned[name] = float(raw)
            except (TypeError, ValueError):
                errors[name] = "Must be a number"
                continue
            if "min" in field and cleaned[name] < field["min"]:
                errors[name] = f"Must be at least {field['min']}"
            if "max" in field and cleaned[name] > field["max"]:
                errors[name] = f"Must be at most {field['max']}"
        elif ftype == "email":
            value = str(raw).strip()
            if "@" not in value or "." not in value:
                errors[name] = "Must be a valid email address"
                continue
            cleaned[name] = value
        elif ftype == "url":
            value = str(raw).strip()
            if not (value.startswith("http://") or value.startswith("https://")):
                errors[name] = "Must start with http:// or https://"
                continue
            cleaned[name] = value
        elif ftype == "select":
            allowed = field.get("options") or []
            if str(raw) not in [str(o) for o in allowed]:
                errors[name] = "Not one of the allowed options"
                continue
            cleaned[name] = str(raw)
        elif ftype == "checkbox":
            cleaned[name] = str(raw).lower() in ("true", "1", "yes", "on", "checked")
        else:
            # text, textarea, date, tel — accept as string, length-cap
            cleaned[name] = str(raw)[:10000]

    return cleaned, errors


def _client_ip() -> str:
    """Best-effort client IP, honouring X-Forwarded-For for reverse proxies."""
    req = frappe.local.request
    if not req:
        return ""
    xff = req.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return req.remote_addr or ""


def _rate_limit_ok(form_name: str, ip: str, limit_per_hour: int) -> bool:
    """Sliding-window check against the Workflow Run table.

    We don't have a dedicated rate-limit cache, but the run's
    trigger_source carries the form slug, so we can count recent
    form submissions per IP. This isn't bulletproof against
    distributed abuse — for that, put a real WAF in front. It's
    good enough for casual spam.
    """
    if not ip:
        return True  # Can't rate-limit anonymous; allow
    from frappe.utils import add_to_date
    cutoff = add_to_date(now_datetime(), hours=-1)
    # Count recent runs with this form's slug and IP in trigger_payload.
    # LIKE on JSON is gross but the alternative is a dedicated table —
    # not worth it for this scale. We escape LIKE metacharacters in the
    # IP before interpolating so a malformed X-Forwarded-For header
    # can't widen the search.
    safe_ip = ip.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    slug = frappe.db.get_value("FlowAgent Form", form_name, "slug") or ""
    count = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabFlowAgent Workflow Run`
        WHERE trigger_source = %s
          AND creation > %s
          AND trigger_payload LIKE %s ESCAPE '\\\\'
        """,
        (
            f"form:{slug}",
            cutoff,
            f'%"ip": "{safe_ip}"%',
        ),
    )[0][0]
    return count < limit_per_hour
