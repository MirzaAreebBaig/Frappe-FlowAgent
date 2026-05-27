<div align="center">

# ⚡ FlowAgent

### Visual AI Workflow Automation for Frappe / ERPNext

Build complex automations by dragging nodes onto a canvas, connecting them, and hitting Save.
Native to Frappe — no external service, no separate runtime, no monthly bill.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](license.txt)
[![Frappe](https://img.shields.io/badge/Frappe-v15-orange.svg)](https://frappeframework.com)
[![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)](https://www.python.org)

</div>

---

## What it does

FlowAgent gives you a visual builder inside Frappe Desk for automating anything that touches a DocType. Drop a trigger node, connect it to AI nodes, business logic, integrations — and you've got a workflow that fires on every Sales Invoice, every new Lead, every scheduled time.

It's the kind of tool you'd reach for n8n or Zapier for, except:
- Workflows run **inside your Frappe site** with full doctype permissions
- AI nodes call Claude directly — no MCP server to host, no agent proxy in between
- Every run is auditable as a regular Frappe document with step-level traces

---

## Highlights

**27 node types across 6 categories**

- **Triggers** — DocType events, webhooks, cron schedules, manual
- **AI** — LLM prompts, structured extraction, classification, sentiment, vision/OCR, and a tool-use **Auto Agent** that can read & optionally write any DocType you whitelist
- **Logic** — conditional branching, loops, waits, parallel fan-out
- **Frappe** — create / update / fetch / submit any doc, plus sandboxed server scripts
- **Integrations** — Email, WhatsApp, Slack, Google Sheets, Razorpay, generic HTTP
- **Transforms** — field mappers, full Jinja templates, sandboxed Python

**Production-grade infrastructure**

- **Loop guard with three layers of defense** — a workflow can never trigger itself, the same `(workflow, doc)` can't re-fire within 10 seconds, and a hard 60/minute rate cap protects against runaway scenarios
- **Full Jinja in every config field** — `{{trigger.doc.field}}`, `{% for %}` loops, `{% if %}` conditionals, all Frappe utility helpers
- **Background execution with inline fallback** — workflows run via `frappe.enqueue` for non-blocking saves; if Redis is unavailable, they run inline
- **AI Build** — describe a workflow in English, get a fully-wired graph dropped on your canvas
- **12 production-ready templates** spanning Sales, CRM, HR, Accounts, Support, Purchase, Inventory, Logistics
- **Step-by-step run traces** — every node's input, output, duration, and any undefined-variable warnings saved as a regular doc

---

## Install

```bash
cd ~/frappe-bench
bench get-app https://github.com/MirzaAreebBaig/Frappe-FlowAgent
bench --site <yoursite> install-app flowagent
bench --site <yoursite> migrate
bench restart    # required — the doc_events hook only loads after worker restart
```

Then in Frappe Desk:
1. Open **FlowAgent Settings** and paste your Anthropic API key
2. Open **FlowAgent → Open Studio** from the sidebar
3. Hit **Templates** and pick one to start from, or click **AI Build** and describe what you want

If a workflow doesn't fire after enabling, click the **stethoscope** icon in the Studio toolbar — it tells you exactly what's wrong.

---

## Quick example — AI Invoice Approval in 60 seconds

1. Open the Studio, click **Templates**, pick **AI Invoice Approval**
2. The canvas loads with: `Sales Invoice (On Submit) → Condition (amount > 50000) → WhatsApp → Update Doc`
3. Edit the WhatsApp message and the threshold to match your business
4. Toggle **Enabled** in the toolbar and hit **Save** — the trigger indicator turns green
5. Submit any Sales Invoice in ERPNext — the workflow fires automatically

You can also build it from scratch using **AI Build**: just type *"When a Sales Invoice is submitted with grand_total above 50000, send a WhatsApp approval to the manager"* and FlowAgent generates the workflow for you.

---

## Variable interpolation

Every text field is a Jinja template. The run context is seeded with:

```jinja
{{trigger.doc.name}}            — the document name
{{trigger.doc.grand_total}}     — any doc field
{{trigger.doc.items}}           — child tables (lists of dicts)
{{trigger.doctype}}             — "Sales Invoice"
{{trigger.event}}               — "After Submit"
{{trigger.user}}                — user who triggered it

{{extracted.amount}}            — output of an upstream ai_extract with output="extracted"
{{lead_score}}                  — any node's output variable

{# Loops, conditionals, filters all work #}
{% for item in trigger.doc.items %}
- {{item.item_code}}: {{item.qty}} × ₹{{item.rate}}
{% endfor %}

{{ frappe.utils.fmt_money(trigger.doc.grand_total) }}
{{ frappe.utils.add_days(frappe.utils.nowdate(), 7) }}
```

Anything saved under a node's `output` field becomes addressable downstream by that name.

---

## Auto Agent

The `ai_agent` node runs a ReAct loop. Give it:
- A **task** in plain English
- A list of **allowed DocTypes** the agent can read
- An optional `can_write: true` flag to let it create/update docs

It will iteratively call DocType tools (`list_documents`, `get_document`, `count_documents`, optionally `update_document`, `create_document`) until it solves the task or hits `max_iters`.

Example task:

> *"Find all overdue Sales Invoices for customer Acme Inc, total them up, and tell me which one is the largest."*

With `allowed_doctypes: Sales Invoice, Customer` the agent will issue `list_documents` and `get_document` calls and return a summary. The agent **cannot touch any doctype not in the allowed list** — this is a hard whitelist.

---

## Templates included

| Template | Trigger | What it does |
| -------- | ------- | ------------ |
| **AI Invoice Approval** | Sales Invoice / On Submit | Routes high-value invoices to managers via WhatsApp |
| **AI Lead Qualifier** | Lead / On Insert | Classifies new leads as hot/warm/cold using AI |
| **Daily Overdue Digest** | Schedule 9am weekdays | AI-summarised overdue invoice digest emailed to accounts |
| **AI Candidate Screener** | Job Applicant / On Insert | Scores candidates 1-10 against the job, auto-replies |
| **AI Expense Categorizer** | Expense Claim / On Submit | Flags unusual expense items for manager review |
| **AI Support Ticket Triage** | Issue / On Insert | Sets priority, team, sentiment — escalates urgent / angry tickets |
| **PO Anomaly Detector** | Purchase Order / On Submit | AI agent compares unit rates against history, flags outliers |
| **AI Item Description Writer** | Item / On Insert | Generates polished product descriptions for new items |
| **Weekly AI Sales Report** | Schedule Monday 8am | Executive summary of last week's invoices, emailed to leadership |
| **Delivery WhatsApp Confirmation** | Delivery Note / On Submit | Sends personalised delivery confirmation to customer |
| **Quotation Follow-up Bot** | Schedule daily 10am | AI-drafted follow-ups for stale open quotations |
| **AI Review Responder** | Communication / On Insert | Drafts replies to negative feedback, creates a ToDo for human review |

Each template is a starting point — load it, edit the doctype names, field references, and recipient details, then save.

---

## Webhook triggers

Set a workflow's trigger to **Webhook** and FlowAgent generates a path. The webhook URL is:

```
POST {site}/api/method/flowagent.api.webhook.handle?path={webhook_path}&token={webhook_secret}
```

Or send the token as `X-FlowAgent-Token` header. The full request body becomes `{{body}}` in the workflow context.

Rotate the secret in **FlowAgent Settings → Regenerate Secret** (invalidates all existing webhook URLs).

---

## Scheduled workflows

Set trigger type to **Schedule** with a standard 5-field cron. The scheduler ticks every minute and fires workflows whose previous cron tick falls in the past 60s.

```
0 9 * * *          — every day at 9am
*/15 * * * *       — every 15 minutes
0 0 1 * *          — first of every month at midnight
0 9 * * 1-5        — weekdays only at 9am
```

---

## Loop protection

The classic foot-gun: a workflow listens for "On Save" of Sales Invoice, the workflow updates a Sales Invoice → infinite loop. FlowAgent has **three layers of defense** against this:

1. **In-process running set** — a workflow already executing in the current process cannot trigger itself, regardless of which doc is being saved
2. **Cross-process cooldown** — the same `(workflow, doctype, doc_name)` triple cannot fire more than once per 10 seconds (via Redis)
3. **Global rate cap** — a single workflow cannot fire more than 60 times per minute system-wide

All suppressions are logged. Watch `bench logs -f` to see the guard in action:

```
[FlowAgent] SUPPRESSED Update Lead Score for Lead/CRM-LEAD-001: loop guard: Update Lead Score is already running in this process
```

---

## Architecture

```
DocType save        ▼
  hooks.doc_events ─┐
Schedule tick       │
  scheduler_events ─┼─► triggers/*.py (with loop guard)
Webhook POST        │       │
  api/webhook.py ───┘       ▼
                       frappe.enqueue(...)
                            │
                            ▼
                  engine.run_workflow_background
                            │
                            ▼
                       engine.Runner
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          context     node executors    Workflow Run + Steps
                            │
                            ▼
                  engine/nodes/*.py
                  (ai, logic, frappe, integration, transform)
```

- Workflow nodes & edges stored as JSON on the Workflow doctype for fast canvas round-trips
- `FlowAgent Workflow Trigger Index` is a flat lookup table maintained on save; the wildcard `doc_events` dispatcher does a single indexed query per event (no overhead for unwatched DocTypes)
- The engine is event-driven, not topo-sorted: branch nodes enqueue one of two children, loops re-enter the body subgraph synchronously
- AI nodes call Anthropic's Messages API directly; the Auto Agent uses native tool-use with DocType-scoped tools

---

## Permissions

Two roles can use FlowAgent:

- **System Manager** — full access (auto-granted)
- **FlowAgent Manager** — created on install; assign to power-users who should build/run workflows without full sysadmin rights

Workflow Runs respect the user who triggered them. Webhooks and schedules run as Administrator.

---

## Settings

| Setting | Default | Purpose |
| ------- | ------- | ------- |
| `anthropic_api_key` | — | Required for all AI nodes |
| `default_model` | `claude-sonnet-4-5` | Used when a node doesn't override |
| `max_agent_iterations` | 8 | Hard cap on the Auto Agent's ReAct loop |
| `max_steps_per_run` | 100 | Protection against runaway loops |
| `default_timeout_seconds` | 30 | Per-HTTP-call timeout |
| `run_retention_days` | 30 | Workflow Run history auto-purged after N days (0 = keep forever) |
| `webhook_secret` | auto-generated | Shared secret for webhook URLs |
| `verbose_logging` | off | Logs every doc-event dispatch decision to bench logs |

Per-integration credentials in `site_config.json`:

```json
{
  "whatsapp_phone_id": "...",
  "whatsapp_access_token": "...",
  "slack_webhook_url": "https://hooks.slack.com/...",
  "razorpay_key_id": "...",
  "razorpay_key_secret": "...",
  "google_sa_json": { ... full service account JSON ... }
}
```

---

## Extending

Adding a new node type takes 5 minutes:

1. Drop an executor in `flowagent/engine/nodes/`:
   ```python
   from . import BaseExecutor, node

   @node("my_new_node")
   class MyExecutor(BaseExecutor):
       def run(self, *, node, cfg, context, runner):
           return {"hello": cfg.get("name")}
   ```

2. Add a definition in `flowagent/public/js/flowagent.js` under `NODE_DEFS`:
   ```js
   my_new_node: {
       label: 'My Node', icon: 'ti-star',
       iconColor: '#10B981',
       category: 'integration',
       fields: [
           { k: 'name', l: 'Name', t: 'text', v: 'default' },
       ],
   },
   ```

3. Add it to `SIDEBAR_GROUPS` in the same file
4. Add the type string to `VALID_NODE_TYPES` in `flowagent/api/ai_build.py` so AI Build can generate it
5. `bench build && bench restart`

---

## Roadmap

`v0.1.x` is the current functional release. On deck for `v0.2`:
- Per-node timeouts (currently global only)
- Workflow versioning & rollback
- Visual diff and undo on the canvas
- Test runs with mock payloads
- Bulk re-trigger of past doc events

---

## License

MIT — see [license.txt](license.txt)
