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
- **24 production-ready templates** spanning Sales, CRM, HR, Accounts, Support, Purchase, Inventory, Logistics, Manufacturing, Projects, Assets, and Knowledge

**Safe iteration**

- **Test mode (dry run)** — preview workflows without writing data or hitting external services. AI calls and reads still run for real so you see actual outputs
- **Step-by-step run trace inspector** — every node's input, output, duration, and any render warnings; click any value in the tree to copy its Jinja path
- **Live streaming during execution** — nodes light up on the canvas as each step completes; no need to wait for the full run to finish to see what's happening
- **Replay** — re-run a previous run with the same payload to debug iteratively
- **Workflow versioning** — every Save snapshots the graph; list, annotate, and restore previous versions with one click
- **Undo / redo on the canvas** — `Cmd/Ctrl + Z` works as you expect; 50-step history
- **Render warnings on the canvas** — yellow badge on any node that referenced a missing template variable
- **Bulk re-trigger** — apply a new workflow retroactively to last month's records; defaults to dry run
- **Health dashboard** — sparkline of the last 50 runs plus the top failing error messages per workflow
- **Export / import templates** — save your own workflows as templates, share them as JSON files

**Production-ready observability**

- **AI cost tracking** — every run records input/output tokens and estimated USD cost across all six AI node types; cumulative totals per workflow on the Stats tab
- **Per-node retry config** — mark flaky integrations (HTTP, Sheets, AI) as retry-3 while keeping write nodes at retry-0; configurable backoff delay
- **Webhook HMAC verification** — optional per-workflow signing secret validates `X-Signature-256` against HMAC-SHA256 of the raw body, matching GitHub/Razorpay/generic webhook conventions

**Composable workflows**

- **Sub-workflow node** (`logic_subworkflow`) — synchronously invoke another workflow as a step. Pass the parent context (default) or a custom JSON payload. Returns the child's final context to the parent. Cycle/depth guard caps recursion at 5 levels.
- **Approval node** (`logic_approval`) — pause the run, email approvers with one-click Approve/Reject buttons, resume on the chosen branch (`out-approve` / `out-reject`). Run sits in `Waiting` status until decision arrives or timeout fires. Configurable timeout policy: approve, reject, or fail.
- **Alert rules** — separate `FlowAgent Alert Rule` doctype declares notifications: "On Failure" / "On Timeout" / "Threshold (N failures in M minutes)". Per-rule cooldown prevents flooding. Channels: Email / Slack Webhook / HTTP Webhook. Custom Jinja message template per rule.
- **Hosted forms** — `FlowAgent Form` doctype defines a JSON field schema, gets a public URL at `/f/<slug>`, server-rendered with client-side validation. Submissions create a Workflow Run with the form data as the payload. Per-IP rate limiting, configurable success message or redirect URL.

**Workspace dashboard & reports**

Install the app and the **FlowAgent** workspace shows up in the desk sidebar with:

- 5 number cards across the top — runs today, failures today, average duration over the past week, AI spend this month, count of active workflows
- 4 interactive charts — daily run volume, AI cost trend (last 30 days), status breakdown donut, top workflows by run count
- 5 script reports linked from the workspace sidebar:
  - **Workflow Performance** — per-workflow rollup: total runs, success rate (colour-coded), avg/max duration, AI tokens & cost, with a stacked Success vs Failed bar chart of the top 10 workflows
  - **Run History** — filterable chronological list of every run with status, trigger, duration, AI cost, and the first line of any error; donut chart of status distribution
  - **AI Cost Analysis** — daily / per-workflow / day-by-workflow breakdown of token usage with cost trend line and "only with cost" filter
  - **Slowest Nodes** — top 100 slowest steps across the workflow library, grouped by (workflow, node), with avg/max/min ms and execution count
  - **Error Analysis** — top errors by frequency, grouped by error message first-line so the same headline collapses regardless of stack trace details
- All reports filter on date range + workflow at minimum, with report-specific filters like "step status" (slowest), "only with cost" (cost), "trigger contains" + "only with errors" (history)

---

## Install

See [INSTALL.md](./INSTALL.md) for setup instructions.

Once installed, open **FlowAgent Settings** in your desk and paste your Anthropic API key, then open **FlowAgent → Open Studio** from the sidebar. Pick a template to get started, or click **AI Build** and describe what you want — FlowAgent generates the workflow for you.

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
| **Work Order Delay Alert** | Schedule daily 8am | Flags delayed Work Orders with AI bottleneck analysis |
| **Smart Stock Reorder** | Schedule daily 7am | AI agent recommends reorder quantities from consumption history |
| **Leave Pattern Insights** | Schedule Monday 9am | Weekly summary of leave patterns, departmental clusters, repeat absentees |
| **AI Project Status Reports** | Schedule Friday 4pm | Per-project status updates sent to customers using AI |
| **New Customer Welcome** | Customer / On Insert | Personalised welcome email + onboarding ToDo for account manager |
| **Asset Maintenance Insights** | Asset Maintenance Log / On Insert | AI categorises maintenance issues and escalates critical ones |
| **Stale Lead Auto-Archive** | Schedule Monday 10am | AI decides whether to archive, cold-mark, or re-engage stale leads |
| **Attendance Anomaly Detection** | Schedule daily 9:30am | Yesterday's attendance scanned for late clusters and repeat issues |
| **Knowledge Base Auto-Tagger** | Article / On Insert | AI extracts topics + SEO description on every new KB article |
| **Payment Reminder Bot** | Schedule Tuesday 11am | Tone-aware payment reminders that escalate with days overdue |
| **Stock Reconciliation Audit** | Stock Reconciliation / On Submit | AI flags suspicious variances and creates audit ToDos |

Each template is a starting point — load it, edit the doctype names, field references, and recipient details, then save.

---

## Webhook triggers

Set a workflow's trigger to **Webhook** and FlowAgent generates a path. The webhook URL is:

```
POST {site}/api/method/flowagent.api.webhook.handle?path={webhook_path}&token={webhook_secret}
```

Or send the token as `X-FlowAgent-Token` header. The full request body becomes `{{body}}` in the workflow context.

Rotate the global secret in **FlowAgent Settings → Regenerate Secret** (invalidates all existing webhook URLs).

**HMAC signature verification (optional).** For integrations that sign their payloads — GitHub, Razorpay, generic provider webhooks — set **HMAC Secret** on the workflow. Inbound requests must then include:

```
X-Signature-256: sha256=<hex digest of HMAC-SHA256(secret, raw_body)>
```

`X-Hub-Signature-256` is also accepted (GitHub-style). Mismatched signatures get a 403; missing header gets a 401. The global token still applies in addition.

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

The current release adds live run streaming, AI cost tracking, per-node retry configuration, and webhook HMAC verification on top of the existing safe-iteration feature set (versioning, undo/redo, dry-run, replay, trace inspector, bulk re-trigger, health dashboard, exportable templates).

On deck:
- Per-node timeouts (currently global only)
- Visual diff between workflow versions
- Sub-workflows — one workflow invoking another as a reusable fragment
- Per-workflow integration credentials (override site-wide keys)
- Workflow concurrency controls (queue / single-flight / coalesce)

---

## License

MIT — see [license.txt](license.txt)
