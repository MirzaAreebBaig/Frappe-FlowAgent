# Copyright (c) 2026, FlowAgent and contributors
# For license information, please see license.txt
"""
External integrations.

Where Frappe has a built-in mechanism (email queue, the requests
library) we use it. Slack / WhatsApp / Sheets / Razorpay all use the
generic HTTP path with provider-specific credentials read from
respective settings doctypes if present, otherwise from this app's
settings or site_config.
"""

from __future__ import annotations

import json

import frappe
import requests

from . import BaseExecutor, node


# -------------------------------------------------------------------------
# Email
# -------------------------------------------------------------------------
@node("int_email")
class EmailNode(BaseExecutor):
    """Send an email via Frappe's email queue."""

    def run(self, *, node, cfg, context, runner):
        recipients = cfg.get("to")
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(",") if r.strip()]
        if not recipients:
            frappe.throw("int_email requires 'to'")
        if runner.dry_run:
            return {
                "_dry_run": True,
                "would_email": {
                    "to": recipients,
                    "subject": cfg.get("subject"),
                    "body_preview": (cfg.get("body") or "")[:200],
                },
            }
        frappe.sendmail(
            recipients=recipients,
            subject=cfg.get("subject") or "(no subject)",
            message=cfg.get("body") or "",
            now=bool(cfg.get("send_now")),
            reference_doctype=cfg.get("reference_doctype"),
            reference_name=cfg.get("reference_name"),
        )
        return {"sent_to": recipients, "subject": cfg.get("subject")}


# -------------------------------------------------------------------------
# WhatsApp (via Meta Cloud API)
# -------------------------------------------------------------------------
@node("int_whatsapp")
class WhatsAppNode(BaseExecutor):
    """Send a WhatsApp message via the Meta Cloud API.

    Reads credentials from FlowAgent Settings or site_config:
      whatsapp_phone_id, whatsapp_access_token
    """

    def run(self, *, node, cfg, context, runner):
        to = cfg.get("to")
        message = cfg.get("message")
        if not (to and message):
            frappe.throw("int_whatsapp requires 'to' and 'message'")
        if runner.dry_run:
            return {
                "_dry_run": True,
                "would_whatsapp": {"to": to, "message": message[:200]},
            }

        phone_id = frappe.conf.get("whatsapp_phone_id")
        token = frappe.conf.get("whatsapp_access_token")
        if not (phone_id and token):
            frappe.throw(
                "WhatsApp credentials missing. Set whatsapp_phone_id and "
                "whatsapp_access_token in site_config.json."
            )

        url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"body": message},
        }
        resp = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


# -------------------------------------------------------------------------
# Generic HTTP
# -------------------------------------------------------------------------
@node("int_http")
class HTTPNode(BaseExecutor):
    """Make an arbitrary HTTP request."""

    def run(self, *, node, cfg, context, runner):
        url = cfg.get("url")
        if not url:
            frappe.throw("int_http requires 'url'")
        method = (cfg.get("method") or "POST").upper()
        # Bound the timeout for the Engineer's test phase: even a "GET"
        # against a made-up URL can hang for the default TCP connect
        # window otherwise. Cap at 15s per request unless explicit.
        timeout = min(int(cfg.get("timeout") or 15), 30)

        body_raw = cfg.get("body")
        body = None
        if body_raw:
            try:
                body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
            except json.JSONDecodeError:
                body = body_raw  # raw string body

        # Dry-run: skip EVERY method, including GET. Claude often designs
        # workflows pointing at made-up URLs; a GET against those will
        # hang until timeout and produce nothing useful for the test.
        if runner.dry_run:
            return {
                "_dry_run": True,
                "would_http": {"method": method, "url": url, "body_preview": str(body)[:200]},
                "status_code": 200,   # so downstream branches don't die on missing key
                "ok": True,
                "body": {},
            }

        headers_raw = cfg.get("headers")
        headers = {}
        if headers_raw:
            try:
                headers = json.loads(headers_raw) if isinstance(headers_raw, str) else headers_raw
            except json.JSONDecodeError:
                pass

        kwargs = {"timeout": timeout, "headers": headers or None}
        if method in ("POST", "PUT", "PATCH"):
            if isinstance(body, (dict, list)):
                kwargs["json"] = body
            else:
                kwargs["data"] = body
        elif method == "GET" and isinstance(body, dict):
            kwargs["params"] = body

        resp = requests.request(method, url, **kwargs)
        # Don't raise on 4xx/5xx — let the workflow decide via a condition node.
        out = {
            "status_code": resp.status_code,
            "ok": resp.ok,
            "headers": dict(resp.headers),
        }
        ct = resp.headers.get("Content-Type", "")
        if "application/json" in ct:
            try:
                out["body"] = resp.json()
            except json.JSONDecodeError:
                out["body"] = resp.text
        else:
            out["body"] = resp.text[:50000]
        return out


# -------------------------------------------------------------------------
# Slack
# -------------------------------------------------------------------------
@node("int_slack")
class SlackNode(BaseExecutor):
    """Post to Slack via incoming webhook.

    Reads `slack_webhook_url` from site_config, or use cfg.webhook_url
    to override per-node.
    """

    def run(self, *, node, cfg, context, runner):
        webhook = cfg.get("webhook_url") or frappe.conf.get("slack_webhook_url")
        if not webhook:
            frappe.throw(
                "Slack webhook URL missing. Set slack_webhook_url in "
                "site_config.json or supply 'webhook_url' on the node."
            )
        message = cfg.get("message") or "(empty message)"
        if runner.dry_run:
            return {
                "_dry_run": True,
                "would_slack": {"channel": cfg.get("channel"), "message": message[:200]},
            }
        payload = {"text": message}
        if cfg.get("channel"):
            payload["channel"] = cfg["channel"]
        if cfg.get("username"):
            payload["username"] = cfg["username"]
        resp = requests.post(webhook, json=payload, timeout=20)
        resp.raise_for_status()
        return {"posted": True, "channel": cfg.get("channel")}


# -------------------------------------------------------------------------
# Google Sheets (via service account JSON)
# -------------------------------------------------------------------------
@node("int_sheets")
class SheetsNode(BaseExecutor):
    """Append / read Google Sheets rows.

    Auth: service account JSON in site_config as `google_sa_json`
    (the full JSON, not a path). cfg.sheet_id, cfg.range, cfg.action.
    """

    def run(self, *, node, cfg, context, runner):
        action = cfg.get("action") or "Append row"
        sheet_id = cfg.get("sheet_id")
        rng = cfg.get("range") or "Sheet1!A:Z"
        if not sheet_id:
            frappe.throw("int_sheets requires 'sheet_id'")

        # Dry-run: stub ALL actions including Read. Google Sheets auth
        # can hang for many seconds if credentials aren't configured on
        # this bench, and the Engineer's test phase shouldn't hit real
        # external APIs at all — that's what live mode is for.
        if runner.dry_run:
            return {
                "_dry_run": True,
                "would_sheets": {"action": action, "sheet_id": sheet_id, "range": rng},
                "values": [],  # realistic-shaped stub for downstream nodes
            }

        token = self._get_access_token()
        base = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{rng}"
        headers = {"Authorization": f"Bearer {token}"}

        if action == "Read range":
            resp = requests.get(base, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()

        # Append / update both take a values payload
        values_raw = cfg.get("values") or cfg.get("row")
        try:
            values = json.loads(values_raw) if isinstance(values_raw, str) else values_raw
        except (TypeError, json.JSONDecodeError):
            values = [str(values_raw)] if values_raw else []
        if values and not isinstance(values[0], list):
            values = [values]  # wrap into 2D

        if action == "Append row":
            resp = requests.post(
                base + ":append?valueInputOption=USER_ENTERED",
                json={"values": values},
                headers=headers,
                timeout=30,
            )
        else:  # Update row
            resp = requests.put(
                base + "?valueInputOption=USER_ENTERED",
                json={"values": values},
                headers=headers,
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json()

    def _get_access_token(self) -> str:
        """Exchange the service account JWT for a Sheets access token."""
        sa = frappe.conf.get("google_sa_json")
        if not sa:
            frappe.throw("Set google_sa_json in site_config.json (service-account JSON)")
        if isinstance(sa, str):
            sa = json.loads(sa)

        # We try google-auth if available (it handles everything), else
        # fall back to a hand-rolled JWT signed with PyJWT.
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request as GRequest
            creds = service_account.Credentials.from_service_account_info(
                sa, scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            creds.refresh(GRequest())
            return creds.token
        except ImportError:
            return _manual_google_token(sa, ["https://www.googleapis.com/auth/spreadsheets"])


def _manual_google_token(sa: dict, scopes: list) -> str:
    """Fallback path if google-auth isn't installed."""
    import time as _time
    try:
        import jwt as _jwt
    except ImportError:
        frappe.throw(
            "Install either 'google-auth' or 'pyjwt' + 'cryptography' for "
            "Google Sheets integration: pip install google-auth"
        )
    now = int(_time.time())
    claim = {
        "iss": sa["client_email"],
        "scope": " ".join(scopes),
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }
    signed = _jwt.encode(claim, sa["private_key"], algorithm="RS256")
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# -------------------------------------------------------------------------
# Razorpay
# -------------------------------------------------------------------------
@node("int_razorpay")
class RazorpayNode(BaseExecutor):
    """Razorpay orders / payment links / payment fetches.

    Reads razorpay_key_id and razorpay_key_secret from site_config.
    """

    def run(self, *, node, cfg, context, runner):
        action = cfg.get("action") or "Create order"

        # Dry-run: stub ALL actions. Don't even check credentials — the
        # test phase shouldn't require Razorpay setup on the dev bench.
        if runner.dry_run:
            return {
                "_dry_run": True,
                "would_razorpay": {"action": action, "amount": cfg.get("amount")},
                "id": "order_stub_" + frappe.generate_hash(length=6),
                "status": "created",
            }

        key = frappe.conf.get("razorpay_key_id")
        secret = frappe.conf.get("razorpay_key_secret")
        if not (key and secret):
            frappe.throw(
                "Razorpay credentials missing. Set razorpay_key_id and "
                "razorpay_key_secret in site_config.json."
            )
        auth = (key, secret)

        if action == "Create order":
            amount = int(float(cfg.get("amount") or 0))
            currency = cfg.get("currency") or "INR"
            payload = {"amount": amount, "currency": currency}
            if cfg.get("receipt"):
                payload["receipt"] = cfg["receipt"]
            resp = requests.post(
                "https://api.razorpay.com/v1/orders",
                auth=auth, json=payload, timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

        if action == "Fetch payment":
            pid = cfg.get("payment_id")
            resp = requests.get(
                f"https://api.razorpay.com/v1/payments/{pid}",
                auth=auth, timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

        if action == "Create link":
            payload = {
                "amount": int(float(cfg.get("amount") or 0)),
                "currency": cfg.get("currency") or "INR",
                "accept_partial": False,
                "description": cfg.get("description") or "FlowAgent payment",
            }
            if cfg.get("customer_name"):
                payload["customer"] = {
                    "name": cfg["customer_name"],
                    "email": cfg.get("customer_email"),
                    "contact": cfg.get("customer_phone"),
                }
            resp = requests.post(
                "https://api.razorpay.com/v1/payment_links",
                auth=auth, json=payload, timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

        frappe.throw(f"Unknown Razorpay action: {action}")
