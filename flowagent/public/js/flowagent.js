// Copyright (c) 2026, FlowAgent and contributors
// For license information, please see license.txt
//
// FlowAgent Studio client-side bundle.
//
// This file is loaded on every Desk page via `app_include_js` in hooks.py.
// It's a no-op outside the Studio page; on that page it provides:
//   * the HTML scaffolding (window.flowagent_studio_html)
//   * the canvas + interactions  (window.flowagent_studio_init)
//
// We deliberately keep this in plain ES, no framework, so it works in
// vanilla Frappe Desk without a build step.

(function () {
'use strict';

// ============================================================
// Node definitions — mirror your canvas mockup
// ============================================================
const NODE_DEFS = {
    // ----- triggers -----
    trigger_doctype: {
        label: 'DocType Event', icon: 'ti-bolt', color: '#EEEDFE', iconColor: '#F59E0B',
        category: 'trigger', fields: [
            { k: 'doctype', l: 'DocType', t: 'link', options: 'DocType', v: 'Sales Invoice' },
            { k: 'event', l: 'Event', t: 'select',
              opts: ['After Insert', 'After Save', 'After Submit', 'After Cancel', 'After Delete', 'On Change'],
              v: 'After Submit' },
        ],
    },
    trigger_webhook: {
        label: 'Webhook', icon: 'ti-webhook', color: '#EEEDFE', iconColor: '#F59E0B',
        category: 'trigger', fields: [
            { k: 'path', l: 'Path (auto)', t: 'text', v: '', readonly: true },
        ],
    },
    trigger_schedule: {
        label: 'Schedule', icon: 'ti-clock', color: '#EEEDFE', iconColor: '#F59E0B',
        category: 'trigger', fields: [
            { k: 'cron', l: 'Cron expression', t: 'text', v: '0 9 * * *' },
        ],
    },
    trigger_manual: {
        label: 'Manual', icon: 'ti-hand-click', color: '#EEEDFE', iconColor: '#F59E0B',
        category: 'trigger', fields: [],
    },

    // ----- AI -----
    ai_llm: {
        label: 'LLM Prompt', icon: 'ti-sparkles', color: '#EAF3DE', iconColor: '#10B981',
        category: 'ai', fields: [
            { k: 'prompt', l: 'Prompt', t: 'textarea', v: 'Summarize: {{trigger.doc}}' },
            { k: 'system', l: 'System prompt (optional)', t: 'textarea', v: '' },
            { k: 'model', l: 'Model (optional)', t: 'text', v: '' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'llm_output' },
        ],
    },
    ai_extract: {
        label: 'AI Extractor', icon: 'ti-list-search', color: '#EAF3DE', iconColor: '#10B981',
        category: 'ai', fields: [
            { k: 'source', l: 'Source text', t: 'textarea', v: '{{trigger.doc}}' },
            { k: 'fields', l: 'Fields (csv or JSON map)', t: 'textarea',
              v: 'amount, customer, line_items' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'extracted' },
        ],
    },
    ai_classify: {
        label: 'Classifier', icon: 'ti-category', color: '#EAF3DE', iconColor: '#10B981',
        category: 'ai', fields: [
            { k: 'text', l: 'Input text', t: 'textarea', v: '{{trigger.doc}}' },
            { k: 'categories', l: 'Categories (csv)', t: 'text', v: 'hot, warm, cold' },
            { k: 'instructions', l: 'Extra instructions', t: 'textarea', v: '' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'category' },
        ],
    },
    ai_sentiment: {
        label: 'Sentiment', icon: 'ti-mood-smile', color: '#EAF3DE', iconColor: '#10B981',
        category: 'ai', fields: [
            { k: 'text', l: 'Input text', t: 'textarea', v: '' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'sentiment' },
        ],
    },
    ai_agent: {
        label: 'Auto Agent', icon: 'ti-robot', color: '#EAF3DE', iconColor: '#10B981',
        category: 'ai', fields: [
            { k: 'task', l: 'Task (natural language)', t: 'textarea',
              v: 'Find all open Sales Invoices for customer {{customer}} and summarise them.' },
            { k: 'allowed_doctypes', l: 'Allowed DocTypes (csv)', t: 'text',
              v: 'Sales Invoice, Customer' },
            { k: 'can_write', l: 'Allow writes', t: 'select', opts: ['false', 'true'], v: 'false' },
            { k: 'max_iters', l: 'Max iterations', t: 'text', v: '8' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'agent_result' },
        ],
    },
    ai_vision: {
        label: 'Vision/OCR', icon: 'ti-eye', color: '#EAF3DE', iconColor: '#10B981',
        category: 'ai', fields: [
            { k: 'file_url', l: 'File URL', t: 'text', v: '{{trigger.doc.file_url}}' },
            { k: 'prompt', l: 'Instruction', t: 'textarea',
              v: 'Extract all text and key fields from this image.' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'vision_result' },
        ],
    },

    // ----- logic -----
    logic_condition: {
        label: 'Condition', icon: 'ti-git-fork', color: '#FAEEDA', iconColor: '#FB923C',
        category: 'logic', hasBranch: true, fields: [
            { k: 'expr', l: 'Expression', t: 'textarea', v: '{{extracted.amount}} > 50000' },
        ],
    },
    logic_loop: {
        label: 'Loop', icon: 'ti-refresh', color: '#FAEEDA', iconColor: '#FB923C',
        category: 'logic', fields: [
            { k: 'items', l: 'Items (Jinja → list)', t: 'text', v: '{{ items_list }}' },
            { k: 'item_var', l: 'Item variable', t: 'text', v: 'item' },
            { k: 'max_items', l: 'Max items', t: 'text', v: '100' },
        ],
    },
    logic_wait: {
        label: 'Wait / Delay', icon: 'ti-hourglass', color: '#FAEEDA', iconColor: '#FB923C',
        category: 'logic', fields: [
            { k: 'seconds', l: 'Seconds (≤60 for sync runs)', t: 'text', v: '5' },
        ],
    },
    logic_parallel: {
        label: 'Parallel', icon: 'ti-arrows-split', color: '#FAEEDA', iconColor: '#FB923C',
        category: 'logic', fields: [],
    },

    // ----- frappe -----
    frappe_create: {
        label: 'Create Doc', icon: 'ti-file-plus', color: '#E6F1FB', iconColor: '#38BDF8',
        category: 'frappe', fields: [
            { k: 'doctype', l: 'DocType', t: 'link', options: 'DocType', v: 'ToDo' },
            { k: 'values', l: 'Values (JSON)', t: 'textarea',
              v: '{"description": "Review {{trigger.doc.name}}"}' },
        ],
    },
    frappe_update: {
        label: 'Update Doc', icon: 'ti-edit', color: '#E6F1FB', iconColor: '#38BDF8',
        category: 'frappe', fields: [
            { k: 'doctype', l: 'DocType', t: 'link', options: 'DocType', v: 'Sales Invoice' },
            { k: 'name', l: 'Document name', t: 'text', v: '{{trigger.doc.name}}' },
            { k: 'fields', l: 'Fields (JSON)', t: 'textarea',
              v: '{"custom_ai_status": "Processed"}' },
        ],
    },
    frappe_fetch: {
        label: 'Fetch Doc', icon: 'ti-database-search', color: '#E6F1FB', iconColor: '#38BDF8',
        category: 'frappe', fields: [
            { k: 'doctype', l: 'DocType', t: 'link', options: 'DocType', v: 'Sales Invoice' },
            { k: 'name', l: 'Single name (optional)', t: 'text', v: '' },
            { k: 'filters', l: 'Filters (JSON)', t: 'textarea',
              v: '{"docstatus": 1, "status": "Overdue"}' },
            { k: 'fields', l: 'Fields (csv)', t: 'text', v: 'name, customer, grand_total' },
            { k: 'limit', l: 'Limit', t: 'text', v: '20' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'rows' },
        ],
    },
    frappe_submit: {
        label: 'Submit Doc', icon: 'ti-file-check', color: '#E6F1FB', iconColor: '#38BDF8',
        category: 'frappe', fields: [
            { k: 'doctype', l: 'DocType', t: 'link', options: 'DocType', v: 'Purchase Invoice' },
            { k: 'name', l: 'Document name', t: 'text', v: '{{doc_name}}' },
        ],
    },
    frappe_script: {
        label: 'Server Script', icon: 'ti-code', color: '#E6F1FB', iconColor: '#38BDF8',
        category: 'frappe', fields: [
            { k: 'script', l: 'Python', t: 'textarea',
              v: 'result = frappe.db.get_value("Customer", "Acme", "credit_limit")' },
        ],
    },

    // ----- integrations -----
    int_email: {
        label: 'Send Email', icon: 'ti-mail', color: '#FAECE7', iconColor: '#F472B6',
        category: 'integration', fields: [
            { k: 'to', l: 'To', t: 'text', v: '{{trigger.doc.contact_email}}' },
            { k: 'subject', l: 'Subject', t: 'text', v: 'Invoice {{trigger.doc.name}}' },
            { k: 'body', l: 'Body (HTML / Jinja)', t: 'textarea',
              v: 'Dear {{trigger.doc.customer_name}},\n\n{{llm_output}}' },
        ],
    },
    int_whatsapp: {
        label: 'WhatsApp', icon: 'ti-brand-whatsapp', color: '#FAECE7', iconColor: '#F472B6',
        category: 'integration', fields: [
            { k: 'to', l: 'Phone number', t: 'text', v: '{{trigger.doc.mobile_no}}' },
            { k: 'message', l: 'Message', t: 'textarea',
              v: 'Hi {{trigger.doc.customer_name}}, invoice {{trigger.doc.name}} requires approval.' },
        ],
    },
    int_http: {
        label: 'HTTP Request', icon: 'ti-api', color: '#FAECE7', iconColor: '#F472B6',
        category: 'integration', fields: [
            { k: 'url', l: 'URL', t: 'text', v: 'https://api.example.com/notify' },
            { k: 'method', l: 'Method', t: 'select', opts: ['POST', 'GET', 'PUT', 'PATCH', 'DELETE'], v: 'POST' },
            { k: 'headers', l: 'Headers (JSON)', t: 'textarea', v: '{}' },
            { k: 'body', l: 'Body (JSON / Jinja)', t: 'textarea',
              v: '{"ref": "{{trigger.doc.name}}"}' },
        ],
    },
    int_slack: {
        label: 'Slack', icon: 'ti-brand-slack', color: '#FAECE7', iconColor: '#F472B6',
        category: 'integration', fields: [
            { k: 'channel', l: 'Channel', t: 'text', v: '#sales-alerts' },
            { k: 'message', l: 'Message', t: 'textarea',
              v: 'New lead *{{lead_name}}* classified as *{{category}}*' },
        ],
    },
    int_sheets: {
        label: 'Google Sheets', icon: 'ti-table', color: '#FAECE7', iconColor: '#F472B6',
        category: 'integration', fields: [
            { k: 'sheet_id', l: 'Sheet ID', t: 'text', v: '' },
            { k: 'range', l: 'Range', t: 'text', v: 'Sheet1!A:Z' },
            { k: 'action', l: 'Action', t: 'select',
              opts: ['Append row', 'Update row', 'Read range'], v: 'Append row' },
            { k: 'values', l: 'Row values (JSON array)', t: 'textarea',
              v: '["{{trigger.doc.name}}", "{{trigger.doc.customer_name}}"]' },
        ],
    },
    int_razorpay: {
        label: 'Razorpay', icon: 'ti-credit-card', color: '#FAECE7', iconColor: '#F472B6',
        category: 'integration', fields: [
            { k: 'action', l: 'Action', t: 'select',
              opts: ['Create order', 'Fetch payment', 'Create link'], v: 'Create order' },
            { k: 'amount', l: 'Amount (paise)', t: 'text', v: '{{trigger.doc.grand_total * 100}}' },
            { k: 'currency', l: 'Currency', t: 'text', v: 'INR' },
            { k: 'receipt', l: 'Receipt', t: 'text', v: '{{trigger.doc.name}}' },
        ],
    },

    // ----- transforms -----
    tf_mapper: {
        label: 'Field Mapper', icon: 'ti-arrows-exchange', color: '#F1EFE8', iconColor: '#94A3B8',
        category: 'transform', fields: [
            { k: 'mapping', l: 'Mapping (JSON of templates)', t: 'textarea',
              v: '{"out_field": "{{in_field}}"}' },
        ],
    },
    tf_jinja: {
        label: 'Jinja Template', icon: 'ti-braces', color: '#F1EFE8', iconColor: '#94A3B8',
        category: 'transform', fields: [
            { k: 'template', l: 'Template', t: 'textarea',
              v: 'Hello {{ customer_name }}, your order {{ order_id }} is ready.' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'rendered' },
        ],
    },
    tf_code: {
        label: 'Python Code', icon: 'ti-brand-python', color: '#F1EFE8', iconColor: '#94A3B8',
        category: 'transform', fields: [
            { k: 'code', l: 'Python', t: 'textarea',
              v: 'output = {k: v for k, v in input.items() if v}' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'output' },
        ],
    },
};

const SIDEBAR_GROUPS = [
    { label: 'Triggers',         types: ['trigger_doctype', 'trigger_webhook', 'trigger_schedule', 'trigger_manual'] },
    { label: 'AI Agents',        types: ['ai_llm', 'ai_extract', 'ai_classify', 'ai_sentiment', 'ai_agent', 'ai_vision'] },
    { label: 'Logic',            types: ['logic_condition', 'logic_loop', 'logic_wait', 'logic_parallel'] },
    { label: 'Frappe Actions',   types: ['frappe_create', 'frappe_update', 'frappe_fetch', 'frappe_submit', 'frappe_script'] },
    { label: 'Integrations',     types: ['int_email', 'int_whatsapp', 'int_http', 'int_slack', 'int_sheets', 'int_razorpay'] },
    { label: 'Transform',        types: ['tf_mapper', 'tf_jinja', 'tf_code'] },
];

const CATEGORY_DOT = {
    trigger: '#F59E0B', ai: '#10B981', logic: '#FB923C',
    frappe: '#38BDF8', integration: '#F472B6', transform: '#94A3B8',
};

// ============================================================
// Templates — AI-powered workflows for ERPNext, ready to drop on the canvas
// ============================================================
const TEMPLATES = {
    invoice_approval: {
        name: 'AI Invoice Approval',
        category: 'Sales',
        icon: 'ti-receipt-2',
        accent: '#38BDF8',
        description: 'Auto-route high-value Sales Invoices for approval via WhatsApp and mark the doc as processed.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Sales Invoice', event: 'After Submit' } },
            { t: 'logic_condition',  cfg: { expr: '{{trigger.doc.grand_total}} > 50000' } },
            { t: 'int_whatsapp',     cfg: { to: '{{trigger.doc.contact_mobile}}', message: 'Approval needed for invoice {{trigger.doc.name}} — ₹{{trigger.doc.grand_total}} from {{trigger.doc.customer_name}}.' } },
            { t: 'frappe_update',    cfg: { doctype: 'Sales Invoice', name: '{{trigger.doc.name}}', fields: '{"custom_ai_status":"Approval Sent"}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Sales Invoice', event: 'After Submit' },
    },

    lead_qualify: {
        name: 'AI Lead Qualifier',
        category: 'CRM',
        icon: 'ti-flame',
        accent: '#F472B6',
        description: 'When a new Lead is captured, classify it as hot / warm / cold using AI and route to the right channel.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Lead', event: 'After Insert' } },
            { t: 'ai_classify',     cfg: { text: 'Lead: {{trigger.doc.lead_name}} from {{trigger.doc.company_name}}. Industry: {{trigger.doc.industry}}. Notes: {{trigger.doc.notes}}', categories: 'hot, warm, cold', instructions: 'Hot = budget confirmed, decision-maker reached. Warm = expressed interest. Cold = generic enquiry.', output: 'lead_temp' } },
            { t: 'frappe_update',   cfg: { doctype: 'Lead', name: '{{trigger.doc.name}}', fields: '{"custom_ai_score": "{{lead_temp}}"}' } },
            { t: 'int_slack',       cfg: { channel: '#sales', message: '🔥 *{{lead_temp}}* lead: {{trigger.doc.lead_name}} ({{trigger.doc.company_name}})' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Lead', event: 'After Insert' },
    },

    overdue_digest: {
        name: 'Daily Overdue Digest',
        category: 'Accounts',
        icon: 'ti-clock-exclamation',
        accent: '#F59E0B',
        description: 'Every morning, fetch overdue Sales Invoices, summarise with AI, and email the accounts team.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 9 * * 1-5' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Sales Invoice', filters: '{"status": "Overdue", "docstatus": 1}', fields: 'name, customer, grand_total, due_date', limit: '50', output: 'invoices' } },
            { t: 'ai_llm',           cfg: { prompt: 'Write a concise 4-line summary of these overdue invoices, calling out the largest amount and oldest due date:\n\n{% for inv in invoices %}- {{inv.name}}: {{inv.customer}} ₹{{inv.grand_total}}, due {{inv.due_date}}\n{% endfor %}', output: 'summary' } },
            { t: 'int_email',        cfg: { to: 'accounts@example.com', subject: 'Overdue Invoices — {{ frappe.utils.now() }}', body: '<p>{{summary}}</p>' } },
        ],
        trigger: { type: 'Schedule', cron: '0 9 * * 1-5' },
    },

    candidate_screening: {
        name: 'AI Candidate Screener',
        category: 'HR',
        icon: 'ti-user-search',
        accent: '#10B981',
        description: 'When a Job Applicant is added, score their resume against the job description with AI and tag them.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Job Applicant', event: 'After Insert' } },
            { t: 'ai_llm',          cfg: { prompt: 'Score this candidate from 1-10 against the job. Reply with just the number then a one-line reason.\n\nJob: {{trigger.doc.job_title}}\nCandidate: {{trigger.doc.applicant_name}}\nResume:\n{{trigger.doc.resume_attachment}}\nCover letter:\n{{trigger.doc.cover_letter}}', output: 'screening' } },
            { t: 'frappe_update',   cfg: { doctype: 'Job Applicant', name: '{{trigger.doc.name}}', fields: '{"custom_ai_screening": "{{screening}}"}' } },
            { t: 'int_email',       cfg: { to: '{{trigger.doc.email_id}}', subject: 'We received your application for {{trigger.doc.job_title}}', body: 'Hi {{trigger.doc.applicant_name}},<br><br>Thanks for applying. Our team will review and get back to you within 5 business days.' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Job Applicant', event: 'After Insert' },
    },

    expense_review: {
        name: 'AI Expense Categorizer',
        category: 'Accounts',
        icon: 'ti-wallet',
        accent: '#FB923C',
        description: 'When an Expense Claim is submitted, use AI to categorize items and flag anything unusual for manager review.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Expense Claim', event: 'After Submit' } },
            { t: 'ai_extract',      cfg: { source: '{% for item in trigger.doc.expenses %}- {{item.description}}: ₹{{item.amount}}\n{% endfor %}', fields: '{"is_unusual": "boolean — true if any item is over budget or non-policy", "summary": "one sentence summary"}', output: 'review' } },
            { t: 'logic_condition', cfg: { expr: '{{review.is_unusual}} == true' } },
            { t: 'int_email',       cfg: { to: '{{trigger.doc.expense_approver}}', subject: 'Review needed: {{trigger.doc.name}}', body: '{{review.summary}}<br><br>Total: ₹{{trigger.doc.total_claimed_amount}}<br>Employee: {{trigger.doc.employee_name}}' } },
            { t: 'frappe_update',   cfg: { doctype: 'Expense Claim', name: '{{trigger.doc.name}}', fields: '{"custom_ai_notes": "{{review.summary}}"}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Expense Claim', event: 'After Submit' },
    },

    support_triage: {
        name: 'AI Support Ticket Triage',
        category: 'Support',
        icon: 'ti-headset',
        accent: '#F472B6',
        description: 'Classify new support Issues by urgency and topic, auto-assign to the right team.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Issue', event: 'After Insert' } },
            { t: 'ai_extract',      cfg: { source: 'Subject: {{trigger.doc.subject}}\n\nDescription: {{trigger.doc.description}}', fields: '{"priority": "Low | Medium | High | Urgent", "team": "Engineering | Billing | General", "sentiment": "positive | neutral | negative | angry"}', output: 'triage' } },
            { t: 'frappe_update',   cfg: { doctype: 'Issue', name: '{{trigger.doc.name}}', fields: '{"priority": "{{triage.priority}}", "custom_team": "{{triage.team}}", "custom_sentiment": "{{triage.sentiment}}"}' } },
            { t: 'logic_condition', cfg: { expr: '"{{triage.priority}}" == "Urgent" or "{{triage.sentiment}}" == "angry"' } },
            { t: 'int_slack',       cfg: { channel: '#support-urgent', message: '🚨 Urgent: <{{trigger.doc.name}}|{{trigger.doc.subject}}> from {{trigger.doc.raised_by}} (sentiment: {{triage.sentiment}})' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Issue', event: 'After Insert' },
    },

    po_anomaly: {
        name: 'PO Anomaly Detector',
        category: 'Purchase',
        icon: 'ti-alert-triangle',
        accent: '#F59E0B',
        description: 'On every Purchase Order, use an AI agent to check unit rates against history and flag anomalies.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Purchase Order', event: 'After Submit' } },
            { t: 'ai_agent',        cfg: { task: 'Inspect the items on Purchase Order {{trigger.doc.name}}. For each item, compare its unit rate to the average of the last 5 Purchase Invoices for the same item_code. Flag items where the rate is more than 20% above the average. Reply with a short report.', allowed_doctypes: 'Purchase Order, Purchase Invoice, Item', can_write: 'false', max_iters: '8', output: 'anomaly_report' } },
            { t: 'frappe_update',   cfg: { doctype: 'Purchase Order', name: '{{trigger.doc.name}}', fields: '{"custom_anomaly_report": "{{anomaly_report.text}}"}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Purchase Order', event: 'After Submit' },
    },

    item_description: {
        name: 'AI Item Description Writer',
        category: 'Inventory',
        icon: 'ti-package',
        accent: '#10B981',
        description: 'When a new Item is created without a description, generate a polished product description using AI.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Item', event: 'After Insert' } },
            { t: 'ai_llm',          cfg: { prompt: 'Write a clean 2-3 sentence product description for: {{trigger.doc.item_name}} ({{trigger.doc.item_group}}). Focus on what it does and who it\'s for. No fluff.', system: 'You write concise B2B product copy. No marketing-speak.', output: 'description' } },
            { t: 'frappe_update',   cfg: { doctype: 'Item', name: '{{trigger.doc.name}}', fields: '{"description": "{{description}}"}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Item', event: 'After Insert' },
    },

    weekly_report: {
        name: 'Weekly AI Sales Report',
        category: 'Sales',
        icon: 'ti-chart-arrows',
        accent: '#38BDF8',
        description: 'Every Monday at 8am, fetch last week\'s Sales Invoices, generate an AI executive summary, and email leadership.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 8 * * 1' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Sales Invoice', filters: '{"docstatus": 1, "posting_date": [">", "{{ frappe.utils.add_days(frappe.utils.nowdate(), -7) }}"]}', fields: 'name, customer, grand_total, posting_date', limit: '500', output: 'invoices' } },
            { t: 'ai_llm',           cfg: { prompt: 'You are a sales analyst. Given last week\'s invoices below, write an executive summary covering: 1) total revenue, 2) top 3 customers by amount, 3) any unusual patterns. Be concise — 5 bullet points max.\n\n{% for inv in invoices %}- {{inv.name}} | {{inv.customer}} | ₹{{inv.grand_total}} | {{inv.posting_date}}\n{% endfor %}', output: 'weekly_summary' } },
            { t: 'int_email',        cfg: { to: 'leadership@example.com', subject: 'Weekly Sales Summary — Week of {{ frappe.utils.nowdate() }}', body: '<div style="font-family:sans-serif">{{weekly_summary}}</div>' } },
        ],
        trigger: { type: 'Schedule', cron: '0 8 * * 1' },
    },

    delivery_confirm: {
        name: 'Delivery WhatsApp Confirmation',
        category: 'Logistics',
        icon: 'ti-truck-delivery',
        accent: '#10B981',
        description: 'When a Delivery Note is submitted, send the customer a WhatsApp confirmation with order details.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Delivery Note', event: 'After Submit' } },
            { t: 'ai_llm',          cfg: { prompt: 'Compose a short, friendly WhatsApp delivery confirmation for {{trigger.doc.customer_name}}. Their order {{trigger.doc.name}} contains {{trigger.doc.total_qty}} items totalling ₹{{trigger.doc.grand_total}}. Keep it under 220 characters.', output: 'wa_message' } },
            { t: 'int_whatsapp',    cfg: { to: '{{trigger.doc.contact_mobile}}', message: '{{wa_message}}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Delivery Note', event: 'After Submit' },
    },

    quotation_followup: {
        name: 'Quotation Follow-up Bot',
        category: 'CRM',
        icon: 'ti-mail-forward',
        accent: '#F472B6',
        description: 'Three days after a Quotation is sent, AI checks if it\'s still open and sends a personalised follow-up email.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 10 * * *' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Quotation', filters: '{"status": "Open", "transaction_date": "{{ frappe.utils.add_days(frappe.utils.nowdate(), -3) }}"}', fields: 'name, customer_name, contact_email, grand_total, items', limit: '50', output: 'stale_quotes' } },
            { t: 'logic_loop',       cfg: { items: '{{stale_quotes}}', item_var: 'quote', max_items: '50' } },
            { t: 'ai_llm',           cfg: { prompt: 'Write a friendly 3-line follow-up email to {{quote.customer_name}} about their open quotation {{quote.name}} for ₹{{quote.grand_total}}. Be helpful, not pushy.', output: 'followup_body' } },
            { t: 'int_email',        cfg: { to: '{{quote.contact_email}}', subject: 'Following up on {{quote.name}}', body: '{{followup_body}}' } },
        ],
        trigger: { type: 'Schedule', cron: '0 10 * * *' },
    },

    review_response: {
        name: 'AI Review Responder',
        category: 'Support',
        icon: 'ti-message-circle',
        accent: '#10B981',
        description: 'Analyse the sentiment of new customer feedback / reviews and auto-draft a reply for human review.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Communication', event: 'After Insert' } },
            { t: 'ai_sentiment',    cfg: { text: '{{trigger.doc.content}}', output: 'sentiment' } },
            { t: 'logic_condition', cfg: { expr: '"{{sentiment.sentiment}}" == "negative"' } },
            { t: 'ai_llm',          cfg: { prompt: 'A customer left negative feedback. Draft a sincere 4-line response acknowledging the issue and offering next steps. Do not over-apologise.\n\nFeedback:\n{{trigger.doc.content}}', output: 'draft_reply' } },
            { t: 'frappe_create',   cfg: { doctype: 'ToDo', values: '{"description": "Negative feedback from {{trigger.doc.sender}} — draft ready", "reference_type": "Communication", "reference_name": "{{trigger.doc.name}}", "priority": "High"}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Communication', event: 'After Insert' },
    },
};

// ============================================================
// Module state — survives across the lifecycle of the Studio page
// ============================================================
let state = {
    page: null,
    wrapper: null,
    currentWorkflow: null,   // server name
    workflowName: 'Untitled workflow',
    enabled: false,
    trigger: { type: 'Manual' },
    runtime: { on_error: 'Stop', max_retries: 0, log_level: 'Info' },
    nodes: [],
    edges: [],
    selectedNodeId: null,
    connectingFrom: null,
    draggingType: null,
    nodeCounter: 0,
    currentTab: 'config',
    lastRun: null,
};

const uuid = () => 'n' + (++state.nodeCounter);

// ============================================================
// HTML scaffold
// ============================================================
window.flowagent_studio_html = function () {
    let sidebarHtml = '';
    SIDEBAR_GROUPS.forEach(g => {
        sidebarHtml += `<div class="fa-side-section">
            <div class="fa-side-label">${g.label}</div>`;
        g.types.forEach(t => {
            const def = NODE_DEFS[t];
            if (!def) return;
            const dot = CATEGORY_DOT[def.category] || '#888';
            sidebarHtml += `
                <div class="fa-node-chip" draggable="true" data-type="${t}">
                    <span class="fa-dot" style="background:${dot}"></span>${def.label}
                </div>`;
        });
        sidebarHtml += `</div>`;
    });

    return `
    <div id="fa-app">
      <div class="fa-topbar">
        <div class="fa-brand">
            <span class="fa-brand-mark"><i class="ti ti-bolt"></i></span>
            <span>FlowAgent</span>
            <span class="fa-brand-tag">studio</span>
        </div>
        <div class="fa-tb-sep"></div>
        <button class="fa-tb-btn" data-action="open">
            <i class="ti ti-folder-open"></i> Open</button>
        <button class="fa-tb-btn" data-action="new">
            <i class="ti ti-plus"></i> New</button>
        <button class="fa-tb-btn" data-action="templates">
            <i class="ti ti-template"></i> Templates</button>
        <button class="fa-tb-btn" data-action="clear" title="Clear canvas">
            <i class="ti ti-trash"></i></button>
        <div class="fa-tb-sep"></div>
        <label class="fa-tb-toggle">
            <input type="checkbox" id="fa-enabled-toggle">
            <span>Enabled</span>
        </label>
        <span id="fa-trigger-indicator" class="fa-trigger-pill" title="Trigger status"></span>
        <div class="fa-spacer"></div>
        <span id="fa-wf-name" title="Click to rename">Untitled workflow</span>
        <button class="fa-tb-btn" data-action="diagnose" title="Diagnose trigger issues">
            <i class="ti ti-stethoscope"></i></button>
        <button class="fa-tb-btn" data-action="save">
            <i class="ti ti-device-floppy"></i> Save</button>
        <button class="fa-tb-btn fa-run" data-action="run">
            <i class="ti ti-player-play"></i> Run</button>
      </div>

      <div class="fa-main">
        <div class="fa-sidebar">${sidebarHtml}</div>

        <div class="fa-canvas-wrap" id="fa-canvas-wrap">
            <div class="fa-canvas-grid"></div>
            <svg class="fa-edges" id="fa-edges"></svg>
            <div id="fa-canvas"></div>
            <div class="fa-empty" id="fa-empty">
                <div class="fa-empty-mark"><i class="ti ti-bolt"></i></div>
                <h2>Build an AI workflow</h2>
                <p>Drag nodes from the palette, start from a template, or describe what you want and let AI scaffold it for you.</p>
                <div class="fa-empty-actions">
                    <button class="fa-empty-btn fa-primary" data-action="templates">
                        <i class="ti ti-template"></i> Browse templates</button>
                    <button class="fa-empty-btn" data-action="open-ai-tab">
                        <i class="ti ti-sparkles"></i> AI Build</button>
                </div>
            </div>
        </div>

        <div class="fa-panel" id="fa-panel">
            <div class="fa-tabs">
                <div class="fa-tab fa-tab-active" data-tab="config">Config</div>
                <div class="fa-tab" data-tab="ai">AI Build</div>
                <div class="fa-tab" data-tab="runs">Runs</div>
                <div class="fa-tab" data-tab="stats">Stats</div>
            </div>

            <div class="fa-panel-pane" id="fa-pane-config">
                <div class="fa-panel-header"><i class="ti ti-adjustments-horizontal"></i> Node config</div>
                <div class="fa-panel-body" id="fa-config-body">
                    <p class="fa-muted">Select a node to configure it</p>
                </div>
            </div>

            <div class="fa-panel-pane fa-ai-pane" id="fa-pane-ai" style="display:none">
                <div class="fa-panel-header"><i class="ti ti-sparkles"></i> AI workflow builder</div>
                <div class="fa-ai-messages" id="fa-ai-messages"></div>
                <div class="fa-ai-help">
                    <div class="fa-ai-help-label">Try one of these</div>
                    <a href="#" data-aip="When a Sales Invoice is submitted, extract key fields with AI, and if grand_total > 50000 send a WhatsApp approval request to the manager">→ Invoice approval flow</a>
                    <a href="#" data-aip="When a new Lead is created, classify it as hot/warm/cold with AI and update the lead score">→ Lead auto-qualify</a>
                    <a href="#" data-aip="Every weekday at 9am, fetch overdue invoices, summarize with AI, and email the accounts team">→ Daily digest</a>
                </div>
                <div class="fa-ai-input">
                    <input type="text" id="fa-ai-input" placeholder="Describe a workflow…">
                    <button data-action="ai-send">↗</button>
                </div>
            </div>

            <div class="fa-panel-pane" id="fa-pane-runs" style="display:none">
                <div class="fa-panel-header"><i class="ti ti-list-details"></i> Recent runs</div>
                <div class="fa-panel-body" id="fa-runs-body">
                    <p class="fa-muted">Save the workflow first to see runs</p>
                </div>
            </div>

            <div class="fa-panel-pane" id="fa-pane-stats" style="display:none">
                <div class="fa-panel-header"><i class="ti ti-chart-bar"></i> Performance</div>
                <div class="fa-panel-body">
                    <div class="fa-stats-grid">
                        <div class="fa-stat"><div class="fa-sv" id="fa-stat-runs">0</div><div class="fa-sl">total runs</div></div>
                        <div class="fa-stat"><div class="fa-sv" id="fa-stat-ok" style="color:var(--fa-success)">0</div><div class="fa-sl">success</div></div>
                        <div class="fa-stat"><div class="fa-sv" id="fa-stat-err" style="color:var(--fa-danger)">0</div><div class="fa-sl">errors</div></div>
                        <div class="fa-stat"><div class="fa-sv" id="fa-stat-ms">—</div><div class="fa-sl">avg ms</div></div>
                    </div>
                </div>
            </div>

            <div class="fa-runlog">
                <div class="fa-runlog-label">Run log</div>
                <div id="fa-runlog-body"></div>
            </div>
        </div>
      </div>
    </div>`;
};

// ============================================================
// Init
// ============================================================
window.flowagent_studio_init = function (page, wrapper) {
    state.page = page;
    state.wrapper = wrapper;
    bindEvents();
    refreshStats();
    refreshTriggerIndicator();
    addLog('Studio ready', 'info');

    // Check for handoff from "Open in Studio" button on a workflow form
    try {
        const pending = sessionStorage.getItem('flowagent.openWorkflow');
        if (pending) {
            sessionStorage.removeItem('flowagent.openWorkflow');
            loadWorkflow(pending);
        }
    } catch (_) {}
};

function bindEvents() {
    const root = document.getElementById('fa-app');
    if (!root) return;

    // Toolbar buttons
    root.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            handleAction(btn.dataset.action);
        });
    });

    // Tab switching
    root.querySelectorAll('.fa-tab').forEach(t => {
        t.addEventListener('click', () => switchTab(t.dataset.tab));
    });

    // Sidebar chips → drag start
    root.querySelectorAll('.fa-node-chip').forEach(chip => {
        chip.addEventListener('dragstart', e => {
            state.draggingType = chip.dataset.type;
            e.dataTransfer.effectAllowed = 'copy';
        });
    });

    // Canvas drop zone
    const wrap = document.getElementById('fa-canvas-wrap');
    wrap.addEventListener('dragover', e => e.preventDefault());
    wrap.addEventListener('drop', handleDrop);
    wrap.addEventListener('click', e => {
        if (e.target === wrap || e.target.classList.contains('fa-canvas-grid')) {
            deselectAll();
            state.connectingFrom = null;
        }
    });

    // Workflow name rename
    document.getElementById('fa-wf-name').addEventListener('click', () => {
        const n = prompt('Workflow name:', state.workflowName);
        if (n) {
            state.workflowName = n;
            document.getElementById('fa-wf-name').textContent = n;
        }
    });

    // Enabled toggle
    document.getElementById('fa-enabled-toggle').addEventListener('change', e => {
        state.enabled = e.target.checked;
        refreshTriggerIndicator();
    });

    // AI sample prompts
    root.querySelectorAll('[data-aip]').forEach(a => {
        a.addEventListener('click', e => {
            e.preventDefault();
            document.getElementById('fa-ai-input').value = a.dataset.aip;
            handleAction('ai-send');
        });
    });

    // Enter key on AI input
    document.getElementById('fa-ai-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') handleAction('ai-send');
    });
}

function handleAction(name) {
    switch (name) {
        case 'open':         return openDialog();
        case 'new':          return newWorkflow();
        case 'templates':    return templatesDialog();
        case 'clear':        return clearCanvas(true);
        case 'save':         return saveWorkflow();
        case 'run':          return runWorkflow();
        case 'ai-send':      return aiSend();
        case 'diagnose':     return runDiagnose();
        case 'open-ai-tab':  return switchTab('ai');
    }
}

function runDiagnose() {
    frappe.call({
        method: 'flowagent.api.studio.diagnose',
        args: state.currentWorkflow ? { workflow: state.currentWorkflow } : {},
        callback: r => {
            const report = r.message;
            if (!report) return;
            const items = (report.checks || []).map(c => {
                const icon = c.ok
                    ? '<i class="ti ti-circle-check" style="color:#1D9E75"></i>'
                    : '<i class="ti ti-alert-circle" style="color:#E24B4A"></i>';
                const detail = c.detail
                    ? `<div style="font-size:11px;color:#666;margin-left:18px">${frappe.utils.escape_html(c.detail)}</div>`
                    : '';
                return `<div style="padding:4px 0;display:flex;align-items:flex-start;gap:6px">
                    <span style="margin-top:2px">${icon}</span>
                    <div style="flex:1">${frappe.utils.escape_html(c.name)}${detail}</div>
                </div>`;
            }).join('');
            const header = report.ok
                ? '<div style="color:#1D9E75;font-weight:500;margin-bottom:8px">All checks passed ✓</div>'
                : '<div style="color:#E24B4A;font-weight:500;margin-bottom:8px">Some checks failed — see details below</div>';
            frappe.msgprint({
                title: 'FlowAgent diagnostics',
                message: header + items,
                wide: true,
            });
        },
    });
}

// ============================================================
// Workflow open / new / save / load
// ============================================================
function openDialog() {
    frappe.call({
        method: 'flowagent.api.studio.list_workflows',
        callback: r => {
            const list = r.message || [];
            const d = new frappe.ui.Dialog({
                title: 'Open Workflow',
                fields: [{
                    fieldname: 'pick', fieldtype: 'Select', label: 'Workflow',
                    options: list.map(w => w.name).join('\n'),
                    reqd: 1,
                }],
                primary_action_label: 'Open',
                primary_action: vals => {
                    d.hide();
                    loadWorkflow(vals.pick);
                },
            });
            d.show();
        },
    });
}

function newWorkflow() {
    const n = prompt('Name for the new workflow:', 'New Workflow');
    if (!n) return;
    state.currentWorkflow = null;
    state.workflowName = n;
    state.enabled = false;
    state.trigger = { type: 'Manual' };
    state.runtime = { on_error: 'Stop', max_retries: 0, log_level: 'Info' };
    state.nodes = [];
    state.edges = [];
    state.nodeCounter = 0;
    document.getElementById('fa-wf-name').textContent = n;
    document.getElementById('fa-enabled-toggle').checked = false;
    renderAll();
    renderConfigPanel();
    document.getElementById('fa-empty').style.display = '';
    addLog('New workflow', 'info');
}

function loadWorkflow(name) {
    frappe.call({
        method: 'flowagent.api.studio.load_workflow',
        args: { name },
        callback: r => {
            const w = r.message;
            if (!w) return;
            state.currentWorkflow = w.name;
            state.workflowName = w.workflow_name || w.name;
            state.enabled = !!w.enabled;
            state.trigger = w.trigger || { type: 'Manual' };
            state.runtime = w.runtime || { on_error: 'Stop' };
            state.nodes = (w.nodes || []).map(n => {
                const def = NODE_DEFS[n.type];
                return { ...n, def };
            });
            state.edges = w.edges || [];
            state.nodeCounter = Math.max(0, ...state.nodes
                .map(n => parseInt((n.id || 'n0').replace(/\D/g, ''), 10) || 0));
            document.getElementById('fa-wf-name').textContent = state.workflowName;
            document.getElementById('fa-enabled-toggle').checked = state.enabled;
            document.getElementById('fa-empty').style.display = state.nodes.length ? 'none' : '';
            renderAll();
            renderConfigPanel();
            refreshRuns();
            refreshStats();
            addLog(`Loaded "${state.workflowName}"`, 'info');
        },
    });
}

function inferTriggerFromCanvas() {
    const triggerNode = state.nodes.find(n => n.type && n.type.startsWith('trigger_'));
    if (!triggerNode) return { type: 'Manual' };
    if (triggerNode.type === 'trigger_doctype') {
        return {
            type: 'DocType Event',
            doctype: triggerNode.cfg.doctype,
            event: triggerNode.cfg.event,
        };
    }
    if (triggerNode.type === 'trigger_schedule') {
        return { type: 'Schedule', cron: triggerNode.cfg.cron };
    }
    if (triggerNode.type === 'trigger_webhook') {
        return { type: 'Webhook' };
    }
    return { type: 'Manual' };
}

function validateForEnabled(trigger) {
    if (trigger.type === 'DocType Event' && (!trigger.doctype || !trigger.event)) {
        return 'A DocType-triggered workflow needs both DocType and Event set on the trigger node.';
    }
    if (trigger.type === 'Schedule' && !trigger.cron) {
        return 'A scheduled workflow needs a cron expression on the trigger node.';
    }
    return null;
}

function saveWorkflow() {
    if (!state.workflowName || state.workflowName === 'Untitled workflow') {
        const n = prompt('Name this workflow:', '');
        if (!n) return;
        state.workflowName = n;
        document.getElementById('fa-wf-name').textContent = n;
    }
    syncAllControls();  // ensure latest Link-control values are written back
    state.trigger = inferTriggerFromCanvas();

    // If user wants this enabled, make sure the trigger is well-formed —
    // otherwise the workflow will save but no doctype event listener gets
    // registered, and the user will be very confused about why nothing fires.
    if (state.enabled) {
        const err = validateForEnabled(state.trigger);
        if (err) {
            frappe.msgprint({
                title: 'Cannot enable workflow',
                message: err,
                indicator: 'red',
            });
            // Save it as disabled instead of silently breaking
            state.enabled = false;
            document.getElementById('fa-enabled-toggle').checked = false;
        }
    }

    const payload = {
        name: state.currentWorkflow,
        workflow_name: state.workflowName,
        enabled: state.enabled,
        trigger: state.trigger,
        runtime: state.runtime,
        nodes: state.nodes.map(n => ({
            id: n.id, type: n.type, x: n.x, y: n.y, cfg: n.cfg,
        })),
        edges: state.edges.map(e => ({ from: e.from, to: e.to, fromPort: e.fromPort })),
    };
    frappe.call({
        method: 'flowagent.api.studio.save_workflow',
        args: { payload: JSON.stringify(payload) },
        callback: r => {
            if (r.message) {
                state.currentWorkflow = r.message.name;
                addLog(`Saved "${state.workflowName}"`, 'ok');
                refreshTriggerIndicator();
                // Surface trigger-registration status so the user knows
                // whether the workflow is actually listening.
                const idx = r.message.index_status || {};
                if (idx.ok && idx.registered) {
                    frappe.show_alert({
                        message: `Saved — ${idx.reason}`,
                        indicator: 'green',
                    }, 5);
                    addLog(idx.reason, 'ok');
                } else if (idx.ok && !idx.registered) {
                    frappe.show_alert({
                        message: `Saved — ${idx.reason}`,
                        indicator: 'orange',
                    }, 5);
                    addLog(idx.reason, 'warn');
                } else {
                    frappe.show_alert({
                        message: `⚠ ${idx.reason || 'Trigger not registered'}`,
                        indicator: 'red',
                    }, 8);
                    addLog(idx.reason || 'Trigger not registered', 'err');
                }
            }
        },
        error: err => addLog('Save failed: ' + (err.message || err), 'err'),
    });
}

function clearCanvas(askConfirm) {
    if (askConfirm && state.nodes.length && !confirm('Clear the canvas?')) return;
    state.nodes = [];
    state.edges = [];
    state.selectedNodeId = null;
    state.connectingFrom = null;
    renderAll();
    renderConfigPanel();
    document.getElementById('fa-empty').style.display = '';
}

// ============================================================
// Canvas: drag, drop, render, wire
// ============================================================
function handleDrop(e) {
    if (!state.draggingType) return;
    const wrap = document.getElementById('fa-canvas-wrap');
    const rect = wrap.getBoundingClientRect();
    addNode(state.draggingType,
            e.clientX - rect.left - 85,
            e.clientY - rect.top - 40);
    state.draggingType = null;
    document.getElementById('fa-empty').style.display = 'none';
}

function addNode(type, x, y, overrides = {}) {
    const def = NODE_DEFS[type];
    if (!def) return;
    const id = uuid();
    const cfg = {};
    def.fields.forEach(f => { cfg[f.k] = (overrides[f.k] !== undefined) ? overrides[f.k] : f.v; });
    const n = { id, type, x: Math.max(0, x), y: Math.max(0, y), cfg, def };
    state.nodes.push(n);
    renderNode(n);
    renderEdges();
    if (type.startsWith('trigger_')) refreshTriggerIndicator();
    return id;
}

function renderAll() {
    document.getElementById('fa-canvas').innerHTML = '';
    state.nodes.forEach(renderNode);
    renderEdges();
    refreshTriggerIndicator();
}

function renderNode(n) {
    const def = n.def || (n.def = NODE_DEFS[n.type]);
    if (!def) return;
    const canvas = document.getElementById('fa-canvas');
    let el = document.getElementById('fa-node-' + n.id);
    if (!el) {
        el = document.createElement('div');
        el.id = 'fa-node-' + n.id;
        el.className = 'fa-wf-node';
        canvas.appendChild(el);
    }
    el.style.left = n.x + 'px';
    el.style.top = n.y + 'px';
    const preview = nodePreviewText(n);
    const isTrigger = (n.type || '').startsWith('trigger_');
    const branch = def.hasBranch;

    el.innerHTML = `
        <div class="fa-node-head" style="color:${def.iconColor}">
            <div class="fa-node-icon" style="background:${def.iconColor}22;color:${def.iconColor}">
                <i class="ti ${def.icon}"></i>
            </div>
            <span class="fa-node-name">${frappe.utils.escape_html(def.label)}</span>
            <span class="fa-node-status" id="fa-ns-${n.id}"></span>
        </div>
        <div class="fa-node-body">${preview}</div>
        ${!isTrigger ? `<div class="fa-port fa-port-in" data-node="${n.id}" data-port="in"></div>` : ''}
        ${branch
            ? `<div class="fa-port fa-port-yes" data-node="${n.id}" data-port="out-yes"></div>
               <div class="fa-port fa-port-no"  data-node="${n.id}" data-port="out-no"></div>
               <span class="fa-port-label fa-port-label-yes">Y</span>
               <span class="fa-port-label fa-port-label-no">N</span>`
            : `<div class="fa-port fa-port-out" data-node="${n.id}" data-port="out"></div>`}
    `;

    el.addEventListener('mousedown', e => startNodeDrag(e, n.id));
    el.addEventListener('click', e => { e.stopPropagation(); selectNode(n.id); });

    // Wiring: mousedown on an output port begins a drag; mouseup on an
    // input port completes it. Clicking inputs does nothing.
    el.querySelectorAll('.fa-port').forEach(p => {
        const port = p.dataset.port;
        if (port === 'in') {
            // Input ports just need to *receive* a drop — handled in startWireDrag
            // via document mouseup. Nothing to bind here.
            return;
        }
        p.addEventListener('mousedown', e => {
            e.stopPropagation();
            e.preventDefault();
            startWireDrag(p.dataset.node, port, e);
        });
    });
}

function nodePreviewText(n) {
    const f = (n.def && n.def.fields && n.def.fields[0]);
    if (!f) return '<span class="fa-muted">no config</span>';
    const v = (n.cfg[f.k] || '').toString().substring(0, 60);
    return `<span class="fa-field-key">${frappe.utils.escape_html(f.l)}:</span> ${frappe.utils.escape_html(v)}`;
}

function startNodeDrag(e, id) {
    if (e.target.classList.contains('fa-port')) return;
    const n = state.nodes.find(x => x.id === id);
    if (!n) return;
    e.preventDefault();
    const wrap = document.getElementById('fa-canvas-wrap').getBoundingClientRect();
    const ox = e.clientX - wrap.left - n.x;
    const oy = e.clientY - wrap.top - n.y;
    function move(e2) {
        n.x = Math.max(0, e2.clientX - wrap.left - ox);
        n.y = Math.max(0, e2.clientY - wrap.top - oy);
        const el = document.getElementById('fa-node-' + id);
        if (el) { el.style.left = n.x + 'px'; el.style.top = n.y + 'px'; }
        renderEdges();
    }
    function up() {
        document.removeEventListener('mousemove', move);
        document.removeEventListener('mouseup', up);
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
}

function selectNode(id) {
    deselectAll();
    state.selectedNodeId = id;
    const el = document.getElementById('fa-node-' + id);
    if (el) el.classList.add('fa-selected');
    renderConfigPanel();
    switchTab('config');
}

function deselectAll() {
    state.selectedNodeId = null;
    document.querySelectorAll('.fa-wf-node').forEach(e => e.classList.remove('fa-selected'));
}

// ============================================================
// Wiring (edges) — drag from output port, drop on input port
// ============================================================
function startWireDrag(fromNodeId, fromPort, mdEvent) {
    const wrap = document.getElementById('fa-canvas-wrap');
    const wrapRect = wrap.getBoundingClientRect();
    const fromNode = state.nodes.find(n => n.id === fromNodeId);
    if (!fromNode) return;

    // Highlight the source port so the user knows wire-drag mode is active
    flashPort(fromNodeId, fromPort, true);

    // Add a live preview path to the edges SVG
    const svg = document.getElementById('fa-edges');
    const previewPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    previewPath.setAttribute('class', 'fa-edge-path fa-edge-preview');
    previewPath.setAttribute('stroke-dasharray', '5,4');
    svg.appendChild(previewPath);

    function onMove(e) {
        const fp = portXY(fromNode, fromPort);
        const cx = e.clientX - wrapRect.left;
        const cy = e.clientY - wrapRect.top;
        const dx = (cx - fp.x) / 2;
        previewPath.setAttribute('d',
            `M${fp.x},${fp.y} C${fp.x + dx},${fp.y} ${cx - dx},${cy} ${cx},${cy}`);
    }

    function onUp(e) {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        previewPath.remove();
        flashPort(fromNodeId, fromPort, false);

        // What did we drop on?
        const target = document.elementFromPoint(e.clientX, e.clientY);
        if (!target || !target.classList.contains('fa-port')) {
            return; // cancelled
        }
        const toNodeId = target.dataset.node;
        const toPort = target.dataset.port;
        if (toPort !== 'in') return; // must drop on an input
        if (toNodeId === fromNodeId) return; // no self-loops

        // Replace any existing edge from this same source+port (only one
        // wire per output port — out-yes / out-no behave correctly).
        state.edges = state.edges.filter(
            ed => !(ed.from === fromNodeId && (ed.fromPort || 'out') === fromPort)
        );
        state.edges.push({ from: fromNodeId, to: toNodeId, fromPort });
        renderEdges();
        addLog(`Wired ${fromNodeId}/${fromPort} → ${toNodeId}`, 'info');
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    // Kick once so the preview line shows at the click point
    onMove(mdEvent);
}

function flashPort(nodeId, port, sticky) {
    const portEl = document.querySelector(
        `.fa-port[data-node='${nodeId}'][data-port='${port}']`);
    if (!portEl) return;
    portEl.classList.add('fa-port-flash');
    if (!sticky) {
        setTimeout(() => portEl.classList.remove('fa-port-flash'), 800);
    }
}

function renderEdges() {
    const svg = document.getElementById('fa-edges');
    const wrap = document.getElementById('fa-canvas-wrap');
    if (!svg || !wrap) return;
    svg.setAttribute('width', wrap.clientWidth);
    svg.setAttribute('height', wrap.clientHeight);
    svg.innerHTML = '';
    state.edges.forEach(e => {
        const from = state.nodes.find(n => n.id === e.from);
        const to = state.nodes.find(n => n.id === e.to);
        if (!from || !to) return;
        const fp = portXY(from, e.fromPort || 'out');
        const tp = portXY(to, 'in');
        const dx = (tp.x - fp.x) / 2;
        const d = `M${fp.x},${fp.y} C${fp.x + dx},${fp.y} ${tp.x - dx},${tp.y} ${tp.x},${tp.y}`;
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', d);
        path.setAttribute('class', 'fa-edge-path');
        if (e.runHighlight) path.classList.add('fa-edge-active');
        svg.appendChild(path);
    });
}

function portXY(node, port) {
    // Node is 170px wide, head ~36px high. Approximate.
    const W = 170, H = 80;
    if (port === 'in')      return { x: node.x,       y: node.y + H / 2 };
    if (port === 'out')     return { x: node.x + W,   y: node.y + H / 2 };
    if (port === 'out-yes') return { x: node.x + W,   y: node.y + H * 0.35 };
    if (port === 'out-no')  return { x: node.x + W,   y: node.y + H * 0.65 };
    return { x: node.x + W, y: node.y + H / 2 };
}

// ============================================================
// Right-side config panel
// ============================================================
function renderConfigPanel() {
    const body = document.getElementById('fa-config-body');
    if (!state.selectedNodeId) {
        body.innerHTML = '<p class="fa-muted">Select a node to configure it</p>';
        return;
    }
    const n = state.nodes.find(x => x.id === state.selectedNodeId);
    if (!n) return;
    const def = n.def;
    let html = `
        <div class="fa-cfg-title">
            <i class="ti ${def.icon}" style="color:${def.iconColor}"></i>
            ${frappe.utils.escape_html(def.label)}
            <button class="fa-cfg-delete" data-action="delete-node" title="Delete node">
                <i class="ti ti-trash"></i>
            </button>
        </div>
        <div class="fa-cfg-id">${n.id} · ${n.type}</div>
    `;
    def.fields.forEach(f => {
        html += renderField(n.id, f, n.cfg[f.k]);
    });
    body.innerHTML = html;

    // Plain inputs / textareas / selects — bind change handlers
    body.querySelectorAll('[data-cfg-key]').forEach(inp => {
        inp.addEventListener('input', e => {
            const key = inp.dataset.cfgKey;
            n.cfg[key] = inp.value;
            renderNode(n);
        });
        if (inp.tagName === 'SELECT') {
            inp.addEventListener('change', e => {
                const key = inp.dataset.cfgKey;
                n.cfg[key] = inp.value;
                renderNode(n);
            });
        }
    });

    // Link fields — mount real Frappe Link controls with autocomplete.
    // We keep refs to each control on the node so saveWorkflow() can
    // force-read their current values (Frappe's Link controls fire 'change'
    // on blur, which may not have happened by the time the user clicks Save).
    n._linkControls = n._linkControls || {};
    def.fields.filter(f => f.t === 'link').forEach(f => {
        const slot = body.querySelector(`[data-link-slot="${f.k}"]`);
        if (!slot) return;
        const ctrl = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                fieldname: f.k,
                options: f.options,
                label: '',
                placeholder: 'Search ' + f.options + '…',
            },
            parent: slot,
            render_input: true,
        });
        ctrl.set_value(n.cfg[f.k] || '');
        n._linkControls[f.k] = ctrl;

        // Multiple events to catch every value-change moment Frappe might emit
        const sync = () => {
            n.cfg[f.k] = ctrl.get_value() || '';
            renderNode(n);
            if (n.type === 'trigger_doctype' || n.type === 'frappe_create' ||
                n.type === 'frappe_update' || n.type === 'frappe_fetch' ||
                n.type === 'frappe_submit') {
                refreshTriggerIndicator();
            }
        };
        ctrl.$input.on('change blur awesomplete-selectcomplete awesomplete-close', sync);
        // Also sync on every keystroke so partial values aren't lost
        ctrl.$input.on('input', () => {
            n.cfg[f.k] = ctrl.$input.val() || '';
        });
    });

    const delBtn = body.querySelector('[data-action="delete-node"]');
    if (delBtn) delBtn.addEventListener('click', () => deleteNode(n.id));
}

// Force-read every Link control's current value back into the node's cfg.
// Called at save time as a safety net in case a change/blur event didn't fire.
function syncAllControls() {
    state.nodes.forEach(n => {
        if (!n._linkControls) return;
        Object.entries(n._linkControls).forEach(([k, ctrl]) => {
            try {
                const v = ctrl.get_value() || ctrl.$input?.val() || '';
                if (v !== undefined) n.cfg[k] = v;
            } catch (_) {}
        });
    });
}

function renderField(nodeId, f, val) {
    const escaped = frappe.utils.escape_html(val == null ? '' : val);
    if (f.t === 'textarea') {
        return `<div class="fa-field">
            <label>${f.l}</label>
            <textarea data-cfg-key="${f.k}" rows="3">${escaped}</textarea>
        </div>`;
    }
    if (f.t === 'select') {
        const opts = (f.opts || []).map(o =>
            `<option value="${o}" ${o === val ? 'selected' : ''}>${o}</option>`).join('');
        return `<div class="fa-field">
            <label>${f.l}</label>
            <select data-cfg-key="${f.k}">${opts}</select>
        </div>`;
    }
    if (f.t === 'link') {
        return `<div class="fa-field">
            <label>${f.l}</label>
            <div data-link-slot="${f.k}" class="fa-link-slot"></div>
        </div>`;
    }
    return `<div class="fa-field">
        <label>${f.l}</label>
        <input type="text" data-cfg-key="${f.k}" value="${escaped}"/>
    </div>`;
}

function deleteNode(id) {
    state.nodes = state.nodes.filter(n => n.id !== id);
    state.edges = state.edges.filter(e => e.from !== id && e.to !== id);
    state.selectedNodeId = null;
    const el = document.getElementById('fa-node-' + id);
    if (el) el.remove();
    renderEdges();
    renderConfigPanel();
}

// ============================================================
// Tabs
// ============================================================
function switchTab(name) {
    state.currentTab = name;
    document.querySelectorAll('.fa-tab').forEach(t =>
        t.classList.toggle('fa-tab-active', t.dataset.tab === name));
    ['config', 'ai', 'runs', 'stats'].forEach(t => {
        const pane = document.getElementById('fa-pane-' + t);
        if (pane) pane.style.display = (t === name) ? '' : 'none';
    });
    if (name === 'runs') refreshRuns();
    if (name === 'stats') refreshStats();
}

// ============================================================
// AI Build
// ============================================================
function aiSend() {
    const inp = document.getElementById('fa-ai-input');
    const msg = inp.value.trim();
    if (!msg) return;
    inp.value = '';
    const msgs = document.getElementById('fa-ai-messages');
    msgs.innerHTML += `<div class="fa-ai-msg fa-ai-msg-user">${frappe.utils.escape_html(msg)}</div>`;
    const typingId = 'fa-typing-' + Date.now();
    msgs.innerHTML += `<div class="fa-ai-msg fa-ai-msg-ai" id="${typingId}">Building…</div>`;
    msgs.scrollTop = msgs.scrollHeight;

    frappe.call({
        method: 'flowagent.api.ai_build.build_from_prompt',
        args: { prompt: msg },
        callback: r => {
            document.getElementById(typingId)?.remove();
            const parsed = r.message;
            if (!parsed || !parsed.nodes) {
                msgs.innerHTML += `<div class="fa-ai-msg fa-ai-msg-ai">No workflow could be parsed from that. Try describing trigger → AI step → action.</div>`;
                return;
            }
            applyAIWorkflow(parsed);
            msgs.innerHTML += `<div class="fa-ai-msg fa-ai-msg-ai">
                <span style="color:#1D9E75">✓ Built:</span> ${parsed.nodes.length} nodes laid out.</div>`;
            msgs.scrollTop = msgs.scrollHeight;
        },
        error: err => {
            document.getElementById(typingId)?.remove();
            msgs.innerHTML += `<div class="fa-ai-msg fa-ai-msg-ai" style="color:#E24B4A">
                Build failed: ${frappe.utils.escape_html((err && err.message) || 'unknown error')}</div>`;
        },
    });
}

function applyAIWorkflow(parsed) {
    clearCanvas(false);
    if (parsed.workflow_name) {
        state.workflowName = parsed.workflow_name;
        document.getElementById('fa-wf-name').textContent = parsed.workflow_name;
    }
    if (parsed.trigger) state.trigger = parsed.trigger;
    document.getElementById('fa-empty').style.display = 'none';

    // The AI might return numeric or string IDs — normalize to internal n1, n2, …
    const idMap = {};
    (parsed.nodes || []).forEach((nd, idx) => {
        const internalId = uuid();
        idMap[nd.id || idx] = internalId;
        const def = NODE_DEFS[nd.type];
        if (!def) return;
        const cfg = {};
        def.fields.forEach(f => { cfg[f.k] = f.v; });
        Object.assign(cfg, nd.cfg || {});
        const n = {
            id: internalId,
            type: nd.type,
            x: nd.x != null ? nd.x : (30 + idx * 200),
            y: nd.y != null ? nd.y : 150,
            cfg, def,
        };
        state.nodes.push(n);
        renderNode(n);
    });
    (parsed.edges || []).forEach(e => {
        const from = idMap[e.from];
        const to = idMap[e.to];
        if (from && to) state.edges.push({ from, to, fromPort: e.fromPort });
    });
    if ((!parsed.edges || !parsed.edges.length) && state.nodes.length > 1) {
        // Auto-link as a straight chain
        for (let i = 0; i < state.nodes.length - 1; i++) {
            state.edges.push({ from: state.nodes[i].id, to: state.nodes[i + 1].id });
        }
    }
    renderEdges();
}

// ============================================================
// Templates
// ============================================================
function templatesDialog() {
    // Build the card grid HTML
    const cards = Object.entries(TEMPLATES).map(([key, tpl]) => {
        const nodeChips = tpl.nodes.map(n => {
            const def = NODE_DEFS[n.t];
            return def ? `<span class="fa-tpl-chip" style="color:${def.iconColor}">${frappe.utils.escape_html(def.label)}</span>` : '';
        }).join('');
        return `
            <div class="fa-template-card" data-tpl="${key}"
                 style="--accent:${tpl.accent};--accent-bg:${tpl.accent}22">
                <div class="fa-tpl-icon"><i class="ti ${tpl.icon}"></i></div>
                <div class="fa-tpl-title">${frappe.utils.escape_html(tpl.name)}</div>
                <div class="fa-tpl-desc">${frappe.utils.escape_html(tpl.description)}</div>
                <div class="fa-tpl-meta">
                    <span class="fa-tpl-chip">${frappe.utils.escape_html(tpl.category)}</span>
                    <span class="fa-tpl-chip">${tpl.nodes.length} nodes</span>
                </div>
            </div>`;
    }).join('');

    const d = new frappe.ui.Dialog({
        title: '<i class="ti ti-template"></i>&nbsp; Start from a template',
        size: 'extra-large',
        fields: [{
            fieldtype: 'HTML',
            fieldname: 'grid',
            options: `
                <style>
                .fa-templates-grid {
                    display: grid; grid-template-columns: repeat(3, 1fr);
                    gap: 14px; margin-top: 8px;
                }
                .fa-template-card {
                    background: var(--bg-color, #f9fafb);
                    border: 1px solid var(--border-color, #e5e7eb);
                    border-radius: 10px;
                    padding: 16px;
                    cursor: pointer;
                    transition: all 0.15s;
                    position: relative;
                    overflow: hidden;
                }
                [data-theme="dark"] .fa-template-card {
                    background: #1B1B1F;
                    border-color: #2A2A30;
                }
                .fa-template-card::before {
                    content: ''; position: absolute;
                    top: 0; left: 0; right: 0; height: 3px;
                    background: var(--accent);
                }
                .fa-template-card:hover {
                    border-color: var(--accent);
                    transform: translateY(-2px);
                    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.12);
                }
                [data-theme="dark"] .fa-template-card:hover {
                    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.4);
                }
                .fa-tpl-icon {
                    width: 36px; height: 36px; border-radius: 8px;
                    display: flex; align-items: center; justify-content: center;
                    background: var(--accent-bg); color: var(--accent);
                    font-size: 17px; margin-bottom: 10px;
                }
                .fa-tpl-title {
                    font-size: 14px; font-weight: 600;
                    margin-bottom: 5px;
                }
                .fa-tpl-desc {
                    font-size: 12px; opacity: 0.7;
                    line-height: 1.5; margin-bottom: 10px;
                }
                .fa-tpl-meta { display: flex; gap: 6px; flex-wrap: wrap; }
                .fa-tpl-chip {
                    font-size: 10px;
                    padding: 2px 8px; border-radius: 10px;
                    background: rgba(0,0,0,0.06);
                    text-transform: uppercase;
                    letter-spacing: 0.04em;
                    font-weight: 500;
                }
                [data-theme="dark"] .fa-tpl-chip { background: rgba(255,255,255,0.06); }
                </style>
                <div class="fa-templates-grid">${cards}</div>
            `,
        }],
    });
    d.show();

    // Bind click handlers after the dialog body renders
    setTimeout(() => {
        d.$wrapper.find('.fa-template-card').on('click', function () {
            const key = this.dataset.tpl;
            d.hide();
            loadTemplate(key);
        });
    }, 50);
}

function loadTemplate(key) {
    const tpl = TEMPLATES[key];
    if (!tpl) return;
    clearCanvas(false);
    state.workflowName = tpl.name;
    document.getElementById('fa-wf-name').textContent = tpl.name;
    state.trigger = tpl.trigger || { type: 'Manual' };
    // Lay out nodes left-to-right with extra horizontal space
    tpl.nodes.forEach((nd, idx) => {
        addNode(nd.t, 40 + idx * 220, 160, nd.cfg);
    });
    // chain them — branch nodes use out-yes by default
    for (let i = 0; i < state.nodes.length - 1; i++) {
        const from = state.nodes[i], to = state.nodes[i + 1];
        if (from.def && from.def.hasBranch) {
            state.edges.push({ from: from.id, to: to.id, fromPort: 'out-yes' });
        } else {
            state.edges.push({ from: from.id, to: to.id });
        }
    }
    renderEdges();
    document.getElementById('fa-empty').style.display = 'none';
    addLog(`Loaded template "${tpl.name}"`, 'info');
    frappe.show_alert({
        message: `Loaded "${tpl.name}" — customise it and hit Save`,
        indicator: 'blue',
    }, 5);
}

// ============================================================
// Run + trace
// ============================================================
function runWorkflow() {
    if (!state.currentWorkflow) {
        if (!confirm('Save before running?')) return;
        return saveThenRun();
    }
    // Inspect the canvas's trigger node to decide what payload the run needs.
    const triggerNode = state.nodes.find(n => n.type && n.type.startsWith('trigger_'));
    if (triggerNode && triggerNode.type === 'trigger_doctype') {
        const dt = triggerNode.cfg.doctype;
        if (!dt) {
            frappe.msgprint('Pick a DocType on the trigger node first.');
            return;
        }
        // Ask which record to run against
        const d = new frappe.ui.Dialog({
            title: `Run against a ${dt}`,
            fields: [{
                fieldname: 'record', fieldtype: 'Link', options: dt,
                label: 'Select record', reqd: 1,
                description: `The selected ${dt} will be passed as trigger.doc to the workflow.`,
            }],
            primary_action_label: 'Run now',
            primary_action: vals => {
                d.hide();
                executeRun({ doctype: dt, name: vals.record });
            },
        });
        d.show();
        return;
    }
    // Webhook or schedule: optional JSON payload
    if (triggerNode && (triggerNode.type === 'trigger_webhook' || triggerNode.type === 'trigger_schedule')) {
        const d = new frappe.ui.Dialog({
            title: 'Run workflow',
            fields: [{
                fieldname: 'payload', fieldtype: 'Code', options: 'JSON',
                label: 'Mock payload (JSON, optional)',
                default: '{}',
            }],
            primary_action_label: 'Run now',
            primary_action: vals => {
                d.hide();
                let parsed = {};
                try { parsed = JSON.parse(vals.payload || '{}'); }
                catch (e) { frappe.msgprint('Payload must be valid JSON'); return; }
                executeRun(parsed);
            },
        });
        d.show();
        return;
    }
    // Manual / no trigger node: just run with empty context
    executeRun({});
}

function executeRun(payload) {
    addLog('Running…', 'info');
    document.querySelectorAll('.fa-node-status').forEach(s => s.style.background = 'var(--border-color)');
    frappe.call({
        method: 'flowagent.api.studio.run_workflow_now',
        args: {
            name: state.currentWorkflow,
            sync: 1,
            payload: JSON.stringify(payload || {}),
        },
        callback: r => {
            const run = r.message;
            if (!run) return;
            state.lastRun = run;
            paintTrace(run);
            refreshStats();
            const colour = run.status === 'Success' ? 'ok' : 'err';
            addLog(`Run ${run.name}: ${run.status} (${run.duration_ms}ms)`, colour);
        },
        error: err => addLog('Run failed: ' + (err.message || err), 'err'),
    });
}

function saveThenRun() {
    if (!state.workflowName || state.workflowName === 'Untitled workflow') {
        const n = prompt('Name this workflow:', '');
        if (!n) return;
        state.workflowName = n;
        document.getElementById('fa-wf-name').textContent = n;
    }
    syncAllControls();
    state.trigger = inferTriggerFromCanvas();
    const payload = {
        workflow_name: state.workflowName,
        enabled: state.enabled,
        trigger: state.trigger,
        runtime: state.runtime,
        nodes: state.nodes.map(n => ({ id: n.id, type: n.type, x: n.x, y: n.y, cfg: n.cfg })),
        edges: state.edges.map(e => ({ from: e.from, to: e.to, fromPort: e.fromPort })),
    };
    frappe.call({
        method: 'flowagent.api.studio.save_workflow',
        args: { payload: JSON.stringify(payload) },
        callback: r => {
            state.currentWorkflow = r.message.name;
            refreshTriggerIndicator();
            runWorkflow();
        },
    });
}

function paintTrace(run) {
    // Reset all status dots
    document.querySelectorAll('.fa-node-status').forEach(s => {
        s.removeAttribute('data-status');
        s.style.background = '';
    });
    state.edges.forEach(e => e.runHighlight = false);
    (run.steps || []).forEach(step => {
        const dot = document.getElementById('fa-ns-' + step.node_id);
        if (dot) {
            dot.setAttribute('data-status', step.status);
        }
        addLog(`#${step.step_index} ${step.node_label} → ${step.status}${step.error ? ' — ' + (step.error || '').split('\n')[0] : ''} (${step.duration_ms}ms)`,
               step.status === 'Success' ? 'ok' : step.status === 'Failed' ? 'err' : 'warn');
    });
    renderEdges();
}

// ============================================================
// Runs / Stats panels
// ============================================================
function refreshRuns() {
    if (!state.currentWorkflow) {
        document.getElementById('fa-runs-body').innerHTML =
            '<p class="fa-muted">Save the workflow first to see runs</p>';
        return;
    }
    frappe.call({
        method: 'flowagent.api.studio.recent_runs',
        args: { workflow: state.currentWorkflow, limit: 30 },
        callback: r => {
            const runs = r.message || [];
            const body = document.getElementById('fa-runs-body');
            if (!runs.length) {
                body.innerHTML = '<p class="fa-muted">No runs yet</p>';
                return;
            }
            body.innerHTML = runs.map(run => `
                <div class="fa-run-row" data-run="${run.name}">
                    <span class="fa-run-status fa-run-${(run.status || '').toLowerCase()}"></span>
                    <span class="fa-run-name">${run.name}</span>
                    <span class="fa-run-src">${frappe.utils.escape_html(run.trigger_source || '')}</span>
                    <span class="fa-run-ms">${run.duration_ms || 0}ms</span>
                </div>
            `).join('');
            body.querySelectorAll('.fa-run-row').forEach(r => {
                r.addEventListener('click', () => openRun(r.dataset.run));
            });
        },
    });
}

function openRun(name) {
    frappe.call({
        method: 'flowagent.api.studio.get_run',
        args: { run_name: name },
        callback: r => {
            const run = r.message;
            if (!run) return;
            state.lastRun = run;
            paintTrace(run);
        },
    });
}

function refreshTriggerIndicator() {
    const el = document.getElementById('fa-trigger-indicator');
    if (!el) return;
    syncAllControls();
    const trig = inferTriggerFromCanvas();
    const enabled = state.enabled;
    let txt = '';
    let cls = 'fa-trigger-pill';
    if (!enabled) {
        txt = '○ Disabled';
        cls += ' fa-trigger-off';
    } else if (trig.type === 'DocType Event' && trig.doctype && trig.event) {
        txt = `● Listening: ${trig.doctype} / ${trig.event}`;
        cls += ' fa-trigger-on';
    } else if (trig.type === 'Schedule' && trig.cron) {
        txt = `● Schedule: ${trig.cron}`;
        cls += ' fa-trigger-on';
    } else if (trig.type === 'Webhook') {
        txt = '● Webhook ready';
        cls += ' fa-trigger-on';
    } else if (trig.type === 'Manual') {
        txt = '○ Manual';
        cls += ' fa-trigger-off';
    } else {
        txt = '⚠ Trigger incomplete';
        cls += ' fa-trigger-warn';
    }
    el.textContent = txt;
    el.className = cls;
}

function refreshStats() {
    frappe.call({
        method: 'flowagent.api.studio.workflow_stats',
        args: state.currentWorkflow ? { workflow: state.currentWorkflow } : {},
        callback: r => {
            const s = r.message || {};
            document.getElementById('fa-stat-runs').textContent = s.runs || 0;
            document.getElementById('fa-stat-ok').textContent = s.ok || 0;
            document.getElementById('fa-stat-err').textContent = s.err || 0;
            document.getElementById('fa-stat-ms').textContent = s.avg_ms ? (s.avg_ms + 'ms') : '—';
        },
    });
}

// ============================================================
// Run log
// ============================================================
function addLog(msg, kind) {
    const body = document.getElementById('fa-runlog-body');
    if (!body) return;
    const time = new Date().toLocaleTimeString();
    const klass = 'fa-log-' + (kind || 'info');
    const line = document.createElement('div');
    line.className = 'fa-log-line';
    line.innerHTML = `<span class="fa-log-time">${time}</span>
                      <span class="${klass}">${frappe.utils.escape_html(msg)}</span>`;
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
    while (body.children.length > 100) body.removeChild(body.firstChild);
}

})();
