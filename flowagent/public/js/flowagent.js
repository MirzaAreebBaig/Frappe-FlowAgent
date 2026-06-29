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
    trigger_form: {
        label: 'Form Submission', icon: 'ti-forms', color: '#EEEDFE', iconColor: '#F59E0B',
        category: 'trigger', fields: [
            { k: 'form_slug', l: 'Form slug (informational)', t: 'text', v: '',
              help: 'The actual binding lives on the FlowAgent Form record. Set its workflow to this one.' },
        ],
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
    logic_subworkflow: {
        label: 'Sub-workflow', icon: 'ti-stack-2', color: '#FAEEDA', iconColor: '#FB923C',
        category: 'logic', fields: [
            { k: 'target_workflow', l: 'Target workflow', t: 'link', options: 'FlowAgent Workflow', v: '' },
            { k: 'payload', l: 'Payload (JSON, optional)', t: 'textarea', v: '',
              help: 'Optional override. If blank, the full parent context is forwarded. Use |tojson when injecting Jinja into JSON.' },
            { k: 'output', l: 'Output variable', t: 'text', v: 'subflow' },
        ],
    },
    logic_approval: {
        label: 'Approval', icon: 'ti-user-check', color: '#FAEEDA', iconColor: '#FB923C',
        category: 'logic', hasBranch: true, branchPorts: ['out-approve', 'out-reject'], fields: [
            { k: 'approvers', l: 'Approvers (emails, comma-separated)', t: 'text', v: '' },
            { k: 'subject', l: 'Email subject', t: 'text', v: 'Approval needed: {{ workflow_name }}' },
            { k: 'message', l: 'Email body (HTML or plain)', t: 'textarea',
              v: 'Please review and approve the following:\n\n{{ trigger.doc | tojson }}' },
            { k: 'timeout_hours', l: 'Timeout (hours)', t: 'text', v: '24' },
            { k: 'on_timeout', l: 'On timeout', t: 'select', opts: ['reject', 'approve', 'fail'], v: 'reject' },
        ],
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
    { label: 'Triggers',         types: ['trigger_doctype', 'trigger_webhook', 'trigger_schedule', 'trigger_manual', 'trigger_form'] },
    { label: 'AI Agents',        types: ['ai_llm', 'ai_extract', 'ai_classify', 'ai_sentiment', 'ai_agent', 'ai_vision'] },
    { label: 'Logic',            types: ['logic_condition', 'logic_loop', 'logic_wait', 'logic_parallel', 'logic_subworkflow', 'logic_approval'] },
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

    work_order_alert: {
        name: 'Work Order Delay Alert',
        category: 'Manufacturing',
        icon: 'ti-tools',
        accent: '#FB923C',
        description: 'When a Work Order is delayed past its planned end date, summarise the bottleneck with AI and notify the production manager.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 8 * * *' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Work Order', filters: '{"status": "In Process", "planned_end_date": ["<", "{{ frappe.utils.nowdate() }}"]}', fields: 'name, production_item, qty, produced_qty, planned_end_date, status', limit: '50', output: 'delayed' } },
            { t: 'logic_condition',  cfg: { expr: '{{delayed | length}} > 0' } },
            { t: 'ai_llm',           cfg: { prompt: 'You are a production analyst. Given these delayed work orders, write a 5-line summary highlighting which items are most behind schedule and likely causes (low produced qty vs planned, age of delay).\n\n{% for wo in delayed %}- {{wo.name}}: {{wo.production_item}}, {{wo.produced_qty}}/{{wo.qty}} done, planned end {{wo.planned_end_date}}\n{% endfor %}', output: 'analysis' } },
            { t: 'int_email',        cfg: { to: 'production@example.com', subject: 'Daily delayed Work Orders — {{ frappe.utils.nowdate() }}', body: '<div style="font-family:sans-serif"><h3>{{delayed | length}} Work Orders behind schedule</h3><p>{{analysis}}</p></div>' } },
        ],
        trigger: { type: 'Schedule', cron: '0 8 * * *' },
    },

    stock_reorder: {
        name: 'Smart Stock Reorder',
        category: 'Inventory',
        icon: 'ti-package-import',
        accent: '#38BDF8',
        description: 'Daily check on items below reorder level. AI agent inspects recent consumption and drafts a Material Request.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 7 * * *' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Bin', filters: '{"actual_qty": ["<", 50]}', fields: 'item_code, warehouse, actual_qty, projected_qty', limit: '100', output: 'low_stock' } },
            { t: 'logic_condition',  cfg: { expr: '{{low_stock | length}} > 0' } },
            { t: 'ai_agent',         cfg: { task: 'For each item in the list below, fetch its average monthly consumption from Stock Ledger Entry and recommend a reorder quantity. Return a markdown table.\n\nItems:\n{% for s in low_stock %}- {{s.item_code}} @ {{s.warehouse}}: {{s.actual_qty}} on hand, {{s.projected_qty}} projected\n{% endfor %}', allowed_doctypes: 'Bin, Item, Stock Ledger Entry, Purchase Order Item', can_write: 'false', max_iters: '10', output: 'reorder_plan' } },
            { t: 'int_email',        cfg: { to: 'purchasing@example.com', subject: 'Stock reorder recommendations', body: '<p>{{low_stock | length}} items below threshold. AI recommendations:</p><pre style="font-family:monospace">{{reorder_plan.text}}</pre>' } },
        ],
        trigger: { type: 'Schedule', cron: '0 7 * * *' },
    },

    leave_summarizer: {
        name: 'Leave Pattern Insights',
        category: 'HR',
        icon: 'ti-calendar-off',
        accent: '#10B981',
        description: 'Weekly AI summary of leave patterns across the org, flagging unusual clusters or recurring absentees.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 9 * * 1' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Leave Application', filters: '{"status": "Approved", "from_date": [">", "{{ frappe.utils.add_days(frappe.utils.nowdate(), -7) }}"]}', fields: 'employee_name, leave_type, from_date, to_date, total_leave_days, department', limit: '200', output: 'leaves' } },
            { t: 'ai_llm',           cfg: { prompt: 'You are an HR analyst. Given last week\'s approved leaves below, write a 5-line summary covering: 1) total leave-days, 2) which departments had the most absences, 3) any unusual clustering (e.g. same team off the same week), 4) recurring absentees.\n\n{% for l in leaves %}- {{l.employee_name}} ({{l.department}}): {{l.leave_type}}, {{l.from_date}} to {{l.to_date}} ({{l.total_leave_days}} days)\n{% endfor %}', output: 'leave_summary' } },
            { t: 'int_email',        cfg: { to: 'hr@example.com', subject: 'Weekly leave summary — week of {{ frappe.utils.nowdate() }}', body: '{{leave_summary}}' } },
        ],
        trigger: { type: 'Schedule', cron: '0 9 * * 1' },
    },

    project_status: {
        name: 'AI Project Status Reports',
        category: 'Projects',
        icon: 'ti-progress-check',
        accent: '#38BDF8',
        description: 'Generate weekly project status updates per active Project, summarising recent task activity and flagging blockers.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 16 * * 5' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Project', filters: '{"status": "Open"}', fields: 'name, project_name, percent_complete, expected_end_date, customer', limit: '30', output: 'projects' } },
            { t: 'logic_loop',       cfg: { items: '{{projects}}', item_var: 'project', max_items: '30' } },
            { t: 'ai_agent',         cfg: { task: 'For project {{project.name}} ({{project.project_name}}, currently {{project.percent_complete}}% done), look up the most recent 10 Tasks and ToDos linked to it. Write a 4-bullet status update: recent wins, in-progress items, blockers, next-week focus.', allowed_doctypes: 'Project, Task, ToDo, Timesheet', can_write: 'false', max_iters: '8', output: 'status' } },
            { t: 'int_email',        cfg: { to: '{{project.customer}}', subject: 'Project update: {{project.project_name}}', body: '<h3>{{project.project_name}}</h3><p>Status: {{project.percent_complete}}% complete · Target: {{project.expected_end_date}}</p><div>{{status.text}}</div>' } },
        ],
        trigger: { type: 'Schedule', cron: '0 16 * * 5' },
    },

    customer_welcome: {
        name: 'New Customer Welcome',
        category: 'CRM',
        icon: 'ti-confetti',
        accent: '#F472B6',
        description: 'When a new Customer is created, generate a personalised welcome email and create an onboarding ToDo for the account manager.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Customer', event: 'After Insert' } },
            { t: 'ai_llm',          cfg: { prompt: 'Write a warm, professional welcome email (4-5 sentences) for our new customer {{trigger.doc.customer_name}} ({{trigger.doc.customer_type}} from {{trigger.doc.territory}}). Mention they can reach out anytime and that an account manager will be in touch. Sign off as "The {{trigger.doc.customer_group}} team".', output: 'welcome_body' } },
            { t: 'int_email',       cfg: { to: '{{trigger.doc.email_id}}', subject: 'Welcome to our family, {{trigger.doc.customer_name}}!', body: '{{welcome_body}}' } },
            { t: 'frappe_create',   cfg: { doctype: 'ToDo', values: '{"description": "Schedule onboarding call with {{trigger.doc.customer_name}}", "reference_type": "Customer", "reference_name": "{{trigger.doc.name}}", "priority": "Medium", "date": "{{ frappe.utils.add_days(frappe.utils.nowdate(), 2) }}"}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Customer', event: 'After Insert' },
    },

    asset_maintenance: {
        name: 'Asset Maintenance Insights',
        category: 'Assets',
        icon: 'ti-tool',
        accent: '#FB923C',
        description: 'When an Asset Maintenance Log is filed, AI categorises the issue and updates the asset\'s health notes.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Asset Maintenance Log', event: 'After Insert' } },
            { t: 'ai_extract',      cfg: { source: 'Maintenance type: {{trigger.doc.maintenance_type}}\nDescription: {{trigger.doc.description}}\nActions taken: {{trigger.doc.actions_performed}}', fields: '{"severity": "Low | Medium | High | Critical", "category": "Routine | Repair | Replacement | Inspection", "next_check_days": "integer — days until next recommended check"}', output: 'analysis' } },
            { t: 'frappe_update',   cfg: { doctype: 'Asset Maintenance Log', name: '{{trigger.doc.name}}', fields: '{"custom_severity": "{{analysis.severity}}", "custom_category": "{{analysis.category}}"}' } },
            { t: 'logic_condition', cfg: { expr: '"{{analysis.severity}}" in ["High", "Critical"]' } },
            { t: 'int_slack',       cfg: { channel: '#maintenance', message: '⚠️ *{{analysis.severity}}* asset issue: {{trigger.doc.asset_name}} — {{trigger.doc.description}}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Asset Maintenance Log', event: 'After Insert' },
    },

    stale_lead_cleanup: {
        name: 'Stale Lead Auto-Archive',
        category: 'CRM',
        icon: 'ti-archive',
        accent: '#94A3B8',
        description: 'Weekly review of leads with no activity in 60 days. AI decides whether to archive, mark cold, or trigger a re-engagement email.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 10 * * 1' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Lead', filters: '{"status": "Open", "modified": ["<", "{{ frappe.utils.add_days(frappe.utils.nowdate(), -60) }}"]}', fields: 'name, lead_name, company_name, email_id, notes, status', limit: '100', output: 'stale_leads' } },
            { t: 'logic_loop',       cfg: { items: '{{stale_leads}}', item_var: 'lead', max_items: '100' } },
            { t: 'ai_classify',      cfg: { text: 'Lead: {{lead.lead_name}} at {{lead.company_name}}. Notes: {{lead.notes}}. No activity in 60+ days.', categories: 'archive, re-engage, mark cold', instructions: 'archive = clearly dead (no engagement signals). re-engage = had genuine interest, worth one more email. mark cold = some signal but lower priority.', output: 'decision' } },
            { t: 'logic_condition',  cfg: { expr: '"{{decision}}" == "re-engage"' } },
            { t: 'ai_llm',           cfg: { prompt: 'Write a short (4 line), no-pressure re-engagement email to {{lead.lead_name}} at {{lead.company_name}}. Lead with curiosity, not a sales pitch.', output: 'reengage_body' } },
            { t: 'int_email',        cfg: { to: '{{lead.email_id}}', subject: 'Checking in, {{lead.lead_name}}', body: '{{reengage_body}}' } },
        ],
        trigger: { type: 'Schedule', cron: '0 10 * * 1' },
    },

    attendance_anomaly: {
        name: 'Attendance Anomaly Detection',
        category: 'HR',
        icon: 'ti-clock-pause',
        accent: '#F59E0B',
        description: 'Daily scan of yesterday\'s Attendance records. AI flags unusual patterns — late arrivals clusters, unauthorised absences, repeat offenders.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '30 9 * * *' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Attendance', filters: '{"attendance_date": "{{ frappe.utils.add_days(frappe.utils.nowdate(), -1) }}"}', fields: 'employee_name, status, working_hours, late_entry, early_exit, department', limit: '500', output: 'yesterday_att' } },
            { t: 'ai_llm',           cfg: { prompt: 'Analyse yesterday\'s attendance records below. Surface in 4-6 bullets: 1) total absences, 2) departments with notable issues, 3) repeat late-entry employees, 4) anything that warrants HR attention. Be concise; don\'t list every employee.\n\n{% for a in yesterday_att %}- {{a.employee_name}} ({{a.department}}): {{a.status}}, {{a.working_hours}}h{% if a.late_entry %} (late){% endif %}{% if a.early_exit %} (early-exit){% endif %}\n{% endfor %}', output: 'att_report' } },
            { t: 'int_email',        cfg: { to: 'hr@example.com', subject: 'Daily attendance brief — {{ frappe.utils.add_days(frappe.utils.nowdate(), -1) }}', body: '{{att_report}}' } },
        ],
        trigger: { type: 'Schedule', cron: '30 9 * * *' },
    },

    kb_autotag: {
        name: 'Knowledge Base Auto-Tagger',
        category: 'Support',
        icon: 'ti-tags',
        accent: '#10B981',
        description: 'When a new Article is created, AI extracts topics and writes a one-paragraph SEO description.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Article', event: 'After Insert' } },
            { t: 'ai_extract',      cfg: { source: 'Title: {{trigger.doc.title}}\nContent: {{trigger.doc.content}}', fields: '{"tags": "comma-separated topical tags, lowercase, max 6", "seo_description": "single paragraph 150-160 chars, plain text", "audience": "Developer | End user | Admin | Mixed"}', output: 'meta' } },
            { t: 'frappe_update',   cfg: { doctype: 'Article', name: '{{trigger.doc.name}}', fields: '{"custom_ai_tags": "{{meta.tags}}", "meta_description": "{{meta.seo_description}}", "custom_audience": "{{meta.audience}}"}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Article', event: 'After Insert' },
    },

    payment_followup: {
        name: 'Payment Reminder Bot',
        category: 'Accounts',
        icon: 'ti-cash',
        accent: '#F59E0B',
        description: 'Every Tuesday, send AI-personalised payment reminders for invoices overdue 7, 14, and 30 days with escalating tone.',
        nodes: [
            { t: 'trigger_schedule', cfg: { cron: '0 11 * * 2' } },
            { t: 'frappe_fetch',     cfg: { doctype: 'Sales Invoice', filters: '{"status": "Overdue", "docstatus": 1}', fields: 'name, customer_name, contact_email, grand_total, due_date, outstanding_amount', limit: '200', output: 'overdue' } },
            { t: 'logic_loop',       cfg: { items: '{{overdue}}', item_var: 'inv', max_items: '200' } },
            { t: 'ai_llm',           cfg: { prompt: 'Compose a payment reminder email to {{inv.customer_name}} for invoice {{inv.name}} (₹{{inv.outstanding_amount}} outstanding, due {{inv.due_date}}).\n\nMatch the tone to how overdue it is: under 14 days = polite reminder, 14-30 days = firmer with clear payment instructions, over 30 days = formal escalation mentioning potential service hold.\n\nKeep it under 6 lines. Sign off as "Accounts Receivable".', output: 'reminder_body' } },
            { t: 'int_email',        cfg: { to: '{{inv.contact_email}}', subject: 'Payment reminder: {{inv.name}}', body: '{{reminder_body}}' } },
        ],
        trigger: { type: 'Schedule', cron: '0 11 * * 2' },
    },

    stock_recon_audit: {
        name: 'Stock Reconciliation Audit',
        category: 'Inventory',
        icon: 'ti-clipboard-check',
        accent: '#FB923C',
        description: 'When a Stock Reconciliation is submitted, AI flags items with unusual variance and creates audit ToDos.',
        nodes: [
            { t: 'trigger_doctype', cfg: { doctype: 'Stock Reconciliation', event: 'After Submit' } },
            { t: 'ai_llm',          cfg: { prompt: 'You are an inventory auditor. Inspect this stock reconciliation. For each item, calculate the variance (qty - current_qty). Flag any item with absolute variance > 10 or value variance > ₹10,000. Reply with a markdown list of flagged items only; if none, reply "No anomalies".\n\nReconciled items:\n{% for item in trigger.doc.items %}- {{item.item_code}} @ {{item.warehouse}}: counted {{item.qty}}, system {{item.current_qty}}, valuation ₹{{item.valuation_rate}}\n{% endfor %}', output: 'audit' } },
            { t: 'logic_condition', cfg: { expr: '"No anomalies" not in "{{audit}}"' } },
            { t: 'frappe_create',   cfg: { doctype: 'ToDo', values: '{"description": "Audit Stock Reconciliation {{trigger.doc.name}}: {{audit}}", "reference_type": "Stock Reconciliation", "reference_name": "{{trigger.doc.name}}", "priority": "High"}' } },
        ],
        trigger: { type: 'DocType Event', doctype: 'Stock Reconciliation', event: 'After Submit' },
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
    // Canvas viewport — applied to .fa-canvas-stage as translate(x,y) scale(zoom)
    zoom: 1,
    panX: 0,
    panY: 0,
    spaceDown: false,
    // AI Build modal mode: 'create' or 'modify'
    aiMode: 'create',
    // Dry-run mode: writes and integrations are simulated.
    testMode: false,
    // Undo / redo: stack of canvas snapshots. Each entry is the full
    // serialized graph (nodes + edges + trigger). We cap the history
    // depth so memory doesn't grow forever on long sessions.
    history: [],
    historyIndex: -1,
    _historyTimer: null,
};

const HISTORY_MAX = 50;

// ============================================================
// Canvas undo / redo
// ============================================================
//
// History is a stack of full graph snapshots. We push a snapshot
// whenever the user changes the graph structure (add/remove node,
// add/remove edge) or modifies a node's config. To avoid spamming
// history with every keystroke on a textarea, config changes use a
// debounce timer.
//
// historyIndex points to the CURRENT state. undo decrements, redo
// increments. After any new edit, we truncate everything past the
// current index — that's the standard "linear history" behavior.

function snapshotState(immediate) {
    // Coalesce rapid edits into a single history entry. Most config-field
    // changes fire on every keystroke, so we wait 350ms before pushing.
    if (state._historyTimer) {
        clearTimeout(state._historyTimer);
        state._historyTimer = null;
    }
    const doSnap = () => {
        const snap = {
            nodes: state.nodes.map(n => ({
                id: n.id, type: n.type, x: n.x, y: n.y,
                cfg: JSON.parse(JSON.stringify(n.cfg || {})),
            })),
            edges: state.edges.map(e => ({
                from: e.from, to: e.to, fromPort: e.fromPort,
            })),
            trigger: JSON.parse(JSON.stringify(state.trigger || {})),
        };
        // Drop redo branch
        state.history.length = state.historyIndex + 1;
        state.history.push(snap);
        // Cap history depth
        if (state.history.length > HISTORY_MAX) {
            state.history.shift();
        }
        state.historyIndex = state.history.length - 1;
    };
    if (immediate) {
        doSnap();
    } else {
        state._historyTimer = setTimeout(doSnap, 350);
    }
}

function undo() {
    if (state.historyIndex <= 0) {
        frappe.show_alert({ message: 'Nothing to undo', indicator: 'gray' }, 2);
        return;
    }
    state.historyIndex--;
    _restoreSnapshot(state.history[state.historyIndex]);
}

function redo() {
    if (state.historyIndex >= state.history.length - 1) {
        frappe.show_alert({ message: 'Nothing to redo', indicator: 'gray' }, 2);
        return;
    }
    state.historyIndex++;
    _restoreSnapshot(state.history[state.historyIndex]);
}

function _restoreSnapshot(snap) {
    if (!snap) return;
    // Rebuild state.nodes from the snapshot, re-resolving NODE_DEFS so each
    // node object has its full def reference. We keep node IDs stable so
    // existing edges remain valid.
    state.nodes = snap.nodes.map(n => ({
        id: n.id, type: n.type, x: n.x, y: n.y,
        cfg: JSON.parse(JSON.stringify(n.cfg || {})),
        def: NODE_DEFS[n.type],
    }));
    state.edges = snap.edges.map(e => ({ from: e.from, to: e.to, fromPort: e.fromPort }));
    state.trigger = JSON.parse(JSON.stringify(snap.trigger || {}));
    state.selectedNodeId = null;
    renderAll();
    document.getElementById('fa-config-body').innerHTML =
        '<p class="fa-muted">Select a node to configure it</p>';
}

const ZOOM_MIN = 0.3;
const ZOOM_MAX = 2.5;
const ZOOM_STEP = 0.1;

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

        <!-- Options menu — every non-canvas workflow action lives here -->
        <div class="fa-tb-menu" data-menu="options">
            <button class="fa-tb-btn fa-tb-menu-btn" data-action="toggle-menu" data-menu-target="options">
                <i class="ti ti-menu-2"></i> Options
                <i class="ti ti-chevron-down fa-tb-menu-chevron"></i>
            </button>
            <div class="fa-tb-menu-dropdown" id="fa-menu-options">
                <div class="fa-tb-menu-section">File</div>
                <button class="fa-tb-menu-item" data-action="open">
                    <i class="ti ti-folder-open"></i><span>Open workflow…</span>
                    <span class="fa-tb-menu-kbd">⌘O</span>
                </button>
                <button class="fa-tb-menu-item" data-action="new">
                    <i class="ti ti-plus"></i><span>New workflow</span>
                </button>
                <div class="fa-tb-menu-divider"></div>
                <div class="fa-tb-menu-section">Templates</div>
                <button class="fa-tb-menu-item" data-action="templates">
                    <i class="ti ti-template"></i><span>Browse templates…</span>
                </button>
                <button class="fa-tb-menu-item" data-action="save-as-template">
                    <i class="ti ti-bookmark-plus"></i><span>Save as template</span>
                </button>
                <button class="fa-tb-menu-item" data-action="import-template">
                    <i class="ti ti-upload"></i><span>Import template…</span>
                </button>
                <div class="fa-tb-menu-divider"></div>
                <div class="fa-tb-menu-section">History</div>
                <button class="fa-tb-menu-item" data-action="versions">
                    <i class="ti ti-history"></i><span>Versions…</span>
                </button>
                <div class="fa-tb-menu-divider"></div>
                <div class="fa-tb-menu-section">Tools</div>
                <button class="fa-tb-menu-item" data-action="bulk-retrigger">
                    <i class="ti ti-repeat"></i><span>Bulk re-run…</span>
                </button>
                <button class="fa-tb-menu-item" data-action="diagnose">
                    <i class="ti ti-stethoscope"></i><span>Diagnose triggers</span>
                </button>
                <div class="fa-tb-menu-divider"></div>
                <button class="fa-tb-menu-item fa-tb-menu-item-danger" data-action="clear">
                    <i class="ti ti-trash"></i><span>Clear canvas</span>
                </button>
            </div>
        </div>

        <div class="fa-tb-sep"></div>

        <button class="fa-tb-btn fa-tb-icon-only" data-action="undo" title="Undo (Ctrl/⌘ + Z)">
            <i class="ti ti-arrow-back-up"></i></button>
        <button class="fa-tb-btn fa-tb-icon-only" data-action="redo" title="Redo (Ctrl/⌘ + Shift + Z)">
            <i class="ti ti-arrow-forward-up"></i></button>

        <div class="fa-tb-sep"></div>
        <label class="fa-tb-toggle">
            <input type="checkbox" id="fa-enabled-toggle">
            <span>Enabled</span>
        </label>
        <span id="fa-trigger-indicator" class="fa-trigger-pill" title="Trigger status"></span>
        <div class="fa-spacer"></div>
        <span id="fa-wf-name" title="Click to rename">Untitled workflow</span>
        <button class="fa-tb-btn" data-action="save">
            <i class="ti ti-device-floppy"></i> Save</button>
        <label class="fa-tb-toggle fa-test-toggle" title="Dry-run mode — preview the flow without writing data or hitting external services">
            <input type="checkbox" id="fa-test-mode-toggle">
            <span>Test mode</span>
        </label>
        <button class="fa-tb-btn fa-run" data-action="run">
            <i class="ti ti-player-play"></i> Run</button>
      </div>

      <div class="fa-main">
        <div class="fa-sidebar">${sidebarHtml}</div>

        <div class="fa-canvas-wrap" id="fa-canvas-wrap">
            <div class="fa-canvas-grid" id="fa-canvas-grid"></div>
            <div class="fa-canvas-stage" id="fa-canvas-stage">
                <svg class="fa-edges" id="fa-edges"></svg>
                <div id="fa-canvas"></div>
            </div>
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

            <!-- Minimap (top-right) -->
            <div class="fa-minimap" id="fa-minimap" title="Click to centre the view">
                <svg class="fa-minimap-svg" id="fa-minimap-svg"
                     xmlns="http://www.w3.org/2000/svg"
                     preserveAspectRatio="xMidYMid meet"></svg>
            </div>

            <!-- Floating AI Build button -->
            <button class="fa-ai-fab" id="fa-ai-fab" data-action="ai-modal"
                    title="AI Build — describe a workflow (Ctrl/⌘ + K)">
                <i class="ti ti-sparkles"></i>
                <span class="fa-ai-fab-label">AI Build</span>
                <span class="fa-ai-fab-kbd">⌘K</span>
            </button>

            <!-- AI Build modal (hidden by default) -->
            <div class="fa-ai-modal" id="fa-ai-modal" style="display:none">
                <div class="fa-ai-modal-backdrop" data-action="ai-modal-close"></div>
                <div class="fa-ai-modal-box">
                    <div class="fa-ai-modal-header">
                        <div class="fa-ai-modal-mark">
                            <i class="ti ti-sparkles"></i>
                        </div>
                        <div>
                            <div class="fa-ai-modal-title">AI Workflow Builder</div>
                            <div class="fa-ai-modal-sub" id="fa-ai-modal-sub">Describe what you want. We'll build it.</div>
                        </div>
                        <button class="fa-ai-modal-close" data-action="ai-modal-close" title="Close (Esc)">
                            <i class="ti ti-x"></i>
                        </button>
                    </div>

                    <!-- Mode toggle -->
                    <div class="fa-ai-mode-tabs" id="fa-ai-mode-tabs">
                        <button class="fa-ai-mode-tab fa-ai-mode-active" data-mode="create">
                            <i class="ti ti-plus"></i> Create new
                        </button>
                        <button class="fa-ai-mode-tab" data-mode="modify" id="fa-ai-mode-modify-btn">
                            <i class="ti ti-edit"></i> Modify this workflow
                            <span class="fa-ai-mode-count" id="fa-ai-mode-count"></span>
                        </button>
                    </div>

                    <div class="fa-ai-modal-body">
                        <textarea id="fa-ai-modal-input" rows="3"
                            placeholder="When a Sales Invoice is submitted with grand_total > 50000, send a WhatsApp approval to the manager…"></textarea>
                        <div class="fa-ai-modal-tips" id="fa-ai-modal-tips-create">
                            <span class="fa-ai-modal-tip-label">Try one of these</span>
                            <button class="fa-ai-modal-tip" data-aipm="When a new Lead is created, classify it as hot, warm or cold with AI and update the lead score">Lead auto-qualify</button>
                            <button class="fa-ai-modal-tip" data-aipm="Every weekday at 9am, fetch overdue Sales Invoices, summarize with AI, and email the accounts team">Daily overdue digest</button>
                            <button class="fa-ai-modal-tip" data-aipm="When a Job Applicant is added, score their resume against the job with AI and reply to the candidate">Candidate screening</button>
                            <button class="fa-ai-modal-tip" data-aipm="When an Issue is created, triage it for priority and team using AI, and notify Slack if urgent">Support triage</button>
                        </div>
                        <div class="fa-ai-modal-tips" id="fa-ai-modal-tips-modify" style="display:none">
                            <span class="fa-ai-modal-tip-label">Common edits</span>
                            <button class="fa-ai-modal-tip" data-aipm="Add a Slack notification step after the existing AI step">Add Slack notification</button>
                            <button class="fa-ai-modal-tip" data-aipm="Add an email step at the end that emails the manager with the summary">Add email step</button>
                            <button class="fa-ai-modal-tip" data-aipm="Add a condition that only runs the downstream steps if the customer is a premium customer">Add a condition</button>
                            <button class="fa-ai-modal-tip" data-aipm="Change the trigger to fire on After Submit instead of After Save">Change trigger event</button>
                        </div>
                    </div>
                    <div class="fa-ai-modal-footer">
                        <span class="fa-ai-modal-hint">
                            <kbd>Enter</kbd> to build · <kbd>Esc</kbd> to close
                        </span>
                        <button class="fa-ai-modal-build" data-action="ai-modal-build">
                            <i class="ti ti-sparkles"></i> <span id="fa-ai-modal-build-label">Build workflow</span>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Zoom controls (bottom-left) -->
            <div class="fa-zoom-controls">
                <button class="fa-zoom-btn" data-action="zoom-out" title="Zoom out (Ctrl/⌘ + −)">
                    <i class="ti ti-minus"></i></button>
                <span class="fa-zoom-pct" id="fa-zoom-pct" data-action="zoom-reset" title="Reset (Ctrl/⌘ + 0)">100%</span>
                <button class="fa-zoom-btn" data-action="zoom-in" title="Zoom in (Ctrl/⌘ + +)">
                    <i class="ti ti-plus"></i></button>
                <span class="fa-zoom-sep"></span>
                <button class="fa-zoom-btn" data-action="zoom-fit" title="Fit all nodes (F)">
                    <i class="ti ti-maximize"></i></button>
            </div>
        </div>

        <div class="fa-panel" id="fa-panel">
            <div class="fa-tabs">
                <div class="fa-tab fa-tab-active" data-tab="config">Config</div>
                <div class="fa-tab" data-tab="ai">AI Build</div>
                <div class="fa-tab" data-tab="trace">Trace</div>
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

            <div class="fa-panel-pane" id="fa-pane-trace" style="display:none">
                <div class="fa-panel-header">
                    <i class="ti ti-zoom-scan"></i> Run trace
                    <span class="fa-spacer"></span>
                    <button class="fa-trace-replay" id="fa-trace-replay" data-action="replay-run"
                            title="Run again with the same payload" style="display:none">
                        <i class="ti ti-refresh"></i> Replay
                    </button>
                </div>
                <div class="fa-panel-body" id="fa-trace-body">
                    <p class="fa-muted">Run the workflow or pick a previous run to inspect it here</p>
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

                    <div class="fa-stats-section">
                        <div class="fa-stats-section-label">Last 50 runs</div>
                        <div class="fa-sparkline-wrap" id="fa-sparkline-wrap">
                            <p class="fa-muted" style="padding:14px 0">No runs yet</p>
                        </div>
                    </div>

                    <div class="fa-stats-section" id="fa-ai-usage-section" style="display:none">
                        <div class="fa-stats-section-label">AI usage (cumulative)</div>
                        <div class="fa-stats-grid">
                            <div class="fa-stat"><div class="fa-sv" id="fa-stat-ai-calls">0</div><div class="fa-sl">AI calls</div></div>
                            <div class="fa-stat"><div class="fa-sv" id="fa-stat-ai-tokens">0</div><div class="fa-sl">tokens</div></div>
                            <div class="fa-stat" style="grid-column: span 2">
                                <div class="fa-sv" id="fa-stat-ai-cost" style="color:var(--fa-accent-hot)">$0</div>
                                <div class="fa-sl">estimated cost (USD)</div>
                            </div>
                        </div>
                    </div>

                    <div class="fa-stats-section" id="fa-top-errors-section" style="display:none">
                        <div class="fa-stats-section-label">Top errors</div>
                        <div id="fa-top-errors"></div>
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
    applyTransform();
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

// Called by the Page when the user navigates away. Releases the global
// listeners so the rest of Frappe Desk doesn't pay for them.
window.flowagent_studio_teardown = function () {
    if (state._keydownHandler) {
        document.removeEventListener('keydown', state._keydownHandler);
        state._keydownHandler = null;
    }
    if (state._keyupHandler) {
        document.removeEventListener('keyup', state._keyupHandler);
        state._keyupHandler = null;
    }
    if (state._runPollTimer) {
        clearTimeout(state._runPollTimer);
        state._runPollTimer = null;
    }
    if (state._runPollVisHandler) {
        document.removeEventListener('visibilitychange', state._runPollVisHandler);
        state._runPollVisHandler = null;
    }
};

function bindEvents() {
    const root = document.getElementById('fa-app');
    if (!root) return;

    // Toolbar buttons. Auto-close any open dropdown menu when a menu-item
    // is clicked — except the toggle itself.
    root.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            const action = btn.dataset.action;
            if (action !== 'toggle-menu' && btn.classList.contains('fa-tb-menu-item')) {
                closeAllMenus();
            }
            handleAction(action, e);
        });
    });

    // Close dropdowns when clicking outside of them
    document.addEventListener('click', e => {
        if (e.target.closest && e.target.closest('.fa-tb-menu')) return;
        closeAllMenus();
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

    // Mouse wheel zoom — only when Ctrl/Cmd is held (otherwise scroll).
    // Without this gate, every wheel touch on the canvas would zoom,
    // which feels chaotic on trackpads.
    let wheelRaf = null;
    let pendingWheel = null;
    wrap.addEventListener('wheel', e => {
        if (!(e.ctrlKey || e.metaKey)) return;
        e.preventDefault();
        const rect = wrap.getBoundingClientRect();
        pendingWheel = {
            cx: e.clientX - rect.left,
            cy: e.clientY - rect.top,
            delta: -Math.sign(e.deltaY) * ZOOM_STEP,
        };
        if (wheelRaf) return;
        wheelRaf = requestAnimationFrame(() => {
            wheelRaf = null;
            if (pendingWheel) {
                zoomAtPoint(state.zoom + pendingWheel.delta, pendingWheel.cx, pendingWheel.cy);
                pendingWheel = null;
            }
        });
    }, { passive: false });

    // Pan: space-bar + drag, or middle-mouse drag, or two-finger pinch-pan
    // Track handlers so we can detach when leaving the Studio (these are
    // attached to document, so they'd otherwise leak across page navigations
    // and slow down the rest of Frappe Desk).
    state._keydownHandler = function (e) {
        if (e.code === 'Space' && !state.spaceDown && !isTypingTarget(e.target)) {
            state.spaceDown = true;
            wrap.classList.add('fa-space-down');
            e.preventDefault();
        }
        // Cmd/Ctrl-based shortcuts. Undo/redo work even when focused inside
        // a text input — that matches what users expect from any editor.
        if (e.ctrlKey || e.metaKey) {
            // Undo / redo (allowed even when typing — flushes pending edits first)
            if (e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                if (state._historyTimer) {
                    clearTimeout(state._historyTimer);
                    state._historyTimer = null;
                    snapshotState(true);  // flush pending
                }
                undo();
                return;
            }
            if ((e.key === 'y') || (e.key === 'z' && e.shiftKey)) {
                e.preventDefault();
                redo();
                return;
            }
        }
        // Keyboard zoom shortcuts (when not typing)
        if (!isTypingTarget(e.target) && (e.ctrlKey || e.metaKey)) {
            if (e.key === '=' || e.key === '+') { e.preventDefault(); setZoom(state.zoom + ZOOM_STEP); }
            if (e.key === '-')                  { e.preventDefault(); setZoom(state.zoom - ZOOM_STEP); }
            if (e.key === '0')                  { e.preventDefault(); resetView(); }
            if (e.key === 'k')                  { e.preventDefault(); openAIBuildModal(); }
            if (e.key === 'o' && !isTypingTarget(e.target)) { e.preventDefault(); openDialog(); }
        }
        if (!isTypingTarget(e.target) && e.key === 'f') {
            e.preventDefault();
            fitView();
        }
    };
    state._keyupHandler = function (e) {
        if (e.code === 'Space') {
            state.spaceDown = false;
            wrap.classList.remove('fa-space-down');
        }
    };
    document.addEventListener('keydown', state._keydownHandler);
    document.addEventListener('keyup', state._keyupHandler);

    // Pan drag (space-held or middle-button)
    wrap.addEventListener('mousedown', e => {
        const isMiddle = e.button === 1;
        const isPanRequested = state.spaceDown || isMiddle;
        // Allow pan from blank canvas (not on a node or port)
        const isBlank = e.target === wrap
            || e.target.classList.contains('fa-canvas-grid')
            || e.target.classList.contains('fa-canvas-stage');
        if (!isPanRequested && !isBlank) return;
        if (e.target.classList.contains('fa-port') || e.target.closest('.fa-wf-node')) {
            // node / port has its own mousedown handler
            if (!isPanRequested) return;
        }
        e.preventDefault();
        const stage = document.getElementById('fa-canvas-stage');
        stage.classList.add('fa-panning');
        const startX = e.clientX, startY = e.clientY;
        const startPanX = state.panX, startPanY = state.panY;
        let rafId = null;
        let pendingX = state.panX, pendingY = state.panY;
        function onMove(ev) {
            pendingX = startPanX + (ev.clientX - startX);
            pendingY = startPanY + (ev.clientY - startY);
            if (rafId) return;
            rafId = requestAnimationFrame(() => {
                rafId = null;
                state.panX = pendingX;
                state.panY = pendingY;
                applyTransformFast();
            });
        }
        function onUp() {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            stage.classList.remove('fa-panning');
            if (rafId) cancelAnimationFrame(rafId);
            state.panX = pendingX;
            state.panY = pendingY;
            applyTransform();  // full update including minimap
        }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
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

    // Test mode toggle — flips dry_run on the next Run
    document.getElementById('fa-test-mode-toggle').addEventListener('change', e => {
        state.testMode = e.target.checked;
        document.body.classList.toggle('fa-test-mode-active', state.testMode);
        const runBtn = document.querySelector('[data-action="run"]');
        if (runBtn) {
            runBtn.innerHTML = state.testMode
                ? '<i class="ti ti-flask"></i> Test run'
                : '<i class="ti ti-player-play"></i> Run';
        }
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

    // Minimap click → centre view at that spot
    const minimap = document.getElementById('fa-minimap');
    if (minimap) {
        minimap.addEventListener('click', e => {
            const r = minimap.getBoundingClientRect();
            const fx = (e.clientX - r.left) / r.width;
            const fy = (e.clientY - r.top) / r.height;
            centreViewAt(fx, fy);
        });
    }

    // AI modal tip buttons — fill the textarea
    root.querySelectorAll('[data-aipm]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            const ta = document.getElementById('fa-ai-modal-input');
            if (ta) {
                ta.value = btn.dataset.aipm;
                ta.focus();
            }
        });
    });

    // AI modal mode tabs (Create / Modify)
    root.querySelectorAll('.fa-ai-mode-tab').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            if (btn.disabled) return;
            setAIMode(btn.dataset.mode);
        });
    });

    // First-time pulse on the AI FAB to draw attention
    try {
        if (!localStorage.getItem('flowagent.aiFabSeen')) {
            const fab = document.getElementById('fa-ai-fab');
            if (fab) {
                fab.classList.add('fa-ai-fab-pulse');
                // Stop pulsing after 8 seconds even if the user ignores it —
                // a longer pulse just costs GPU cycles for no benefit.
                setTimeout(() => fab.classList.remove('fa-ai-fab-pulse'), 8000);
            }
        }
    } catch (_) {}
}

function isTypingTarget(el) {
    if (!el) return false;
    const tag = (el.tagName || '').toUpperCase();
    return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable;
}

// ============================================================
// Zoom + pan
// ============================================================
function applyTransform() {
    applyTransformFast();
    renderMinimap();
}

function applyTransformFast() {
    const stage = document.getElementById('fa-canvas-stage');
    const grid = document.getElementById('fa-canvas-grid');
    if (!stage) return;
    const t = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
    stage.style.transform = t;
    // The grid also pans (but not scales) so dots stay 22px on screen
    if (grid) {
        grid.style.backgroundPosition = `${state.panX}px ${state.panY}px`;
    }
    const pctEl = document.getElementById('fa-zoom-pct');
    if (pctEl) pctEl.textContent = Math.round(state.zoom * 100) + '%';
}

function setZoom(newZoom) {
    const wrap = document.getElementById('fa-canvas-wrap');
    if (!wrap) return;
    const rect = wrap.getBoundingClientRect();
    zoomAtPoint(newZoom, rect.width / 2, rect.height / 2);
}

function zoomAtPoint(newZoom, cx, cy) {
    newZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, newZoom));
    // Adjust pan so the point under (cx, cy) stays put while zooming
    const scaleRatio = newZoom / state.zoom;
    state.panX = cx - (cx - state.panX) * scaleRatio;
    state.panY = cy - (cy - state.panY) * scaleRatio;
    state.zoom = newZoom;
    applyTransform();
}

function resetView() {
    state.zoom = 1;
    state.panX = 0;
    state.panY = 0;
    applyTransform();
}

function fitView() {
    if (!state.nodes.length) { resetView(); return; }
    const wrap = document.getElementById('fa-canvas-wrap');
    if (!wrap) return;
    const rect = wrap.getBoundingClientRect();
    const padding = 60;
    // Bounding box of nodes (node width ~184, head+body ~88)
    const NW = 184, NH = 88;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    state.nodes.forEach(n => {
        minX = Math.min(minX, n.x);
        minY = Math.min(minY, n.y);
        maxX = Math.max(maxX, n.x + NW);
        maxY = Math.max(maxY, n.y + NH);
    });
    const contentW = maxX - minX;
    const contentH = maxY - minY;
    const availW = rect.width - padding * 2;
    const availH = rect.height - padding * 2;
    const z = Math.min(availW / contentW, availH / contentH, 1.5);
    state.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
    // Centre the content
    state.panX = padding + (availW - contentW * state.zoom) / 2 - minX * state.zoom;
    state.panY = padding + (availH - contentH * state.zoom) / 2 - minY * state.zoom;
    applyTransform();
}

function centreViewAt(fx, fy) {
    // fx, fy are 0..1 fractions of the minimap → translate to world coords
    if (!state.nodes.length) return;
    const wrap = document.getElementById('fa-canvas-wrap');
    if (!wrap) return;
    const rect = wrap.getBoundingClientRect();
    const NW = 184, NH = 88;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    state.nodes.forEach(n => {
        minX = Math.min(minX, n.x);
        minY = Math.min(minY, n.y);
        maxX = Math.max(maxX, n.x + NW);
        maxY = Math.max(maxY, n.y + NH);
    });
    const worldX = minX + fx * (maxX - minX);
    const worldY = minY + fy * (maxY - minY);
    state.panX = rect.width / 2 - worldX * state.zoom;
    state.panY = rect.height / 2 - worldY * state.zoom;
    applyTransform();
}

function renderMinimap() {
    const svg = document.getElementById('fa-minimap-svg');
    if (!svg) return;
    const wrap = document.getElementById('fa-canvas-wrap');
    if (!wrap) return;
    if (!state.nodes.length) {
        svg.innerHTML = '';
        return;
    }
    const NW = 184, NH = 88;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    state.nodes.forEach(n => {
        minX = Math.min(minX, n.x);
        minY = Math.min(minY, n.y);
        maxX = Math.max(maxX, n.x + NW);
        maxY = Math.max(maxY, n.y + NH);
    });
    // Pad bounds a bit
    const pad = 50;
    minX -= pad; minY -= pad; maxX += pad; maxY += pad;
    const w = maxX - minX, h = maxY - minY;
    svg.setAttribute('viewBox', `${minX} ${minY} ${w} ${h}`);

    // Viewport rectangle = canvas-wrap mapped through inverse transform
    const rect = wrap.getBoundingClientRect();
    const vx = -state.panX / state.zoom;
    const vy = -state.panY / state.zoom;
    const vw = rect.width / state.zoom;
    const vh = rect.height / state.zoom;

    const nodeRects = state.nodes.map(n =>
        `<rect class="fa-minimap-node" x="${n.x}" y="${n.y}" width="${NW}" height="${NH}" rx="6"/>`
    ).join('');

    svg.innerHTML = nodeRects +
        `<rect class="fa-minimap-viewport" x="${vx}" y="${vy}" width="${vw}" height="${vh}" rx="4"/>`;
}

// ============================================================
// Topbar dropdown menus
// ============================================================
// We render at most one open dropdown at a time. The button that toggled it
// is the one before its sibling .fa-tb-menu-dropdown.

function toggleMenu(e) {
    const btn = e && e.currentTarget;
    if (!btn) return;
    const target = btn.dataset.menuTarget;
    if (!target) return;
    const dropdown = document.getElementById('fa-menu-' + target);
    if (!dropdown) return;
    const wasOpen = dropdown.classList.contains('fa-tb-menu-open');
    closeAllMenus();
    if (!wasOpen) {
        dropdown.classList.add('fa-tb-menu-open');
        btn.classList.add('fa-tb-menu-btn-open');
    }
}

function closeAllMenus() {
    document.querySelectorAll('.fa-tb-menu-dropdown.fa-tb-menu-open').forEach(d => {
        d.classList.remove('fa-tb-menu-open');
    });
    document.querySelectorAll('.fa-tb-menu-btn-open').forEach(b => {
        b.classList.remove('fa-tb-menu-btn-open');
    });
}

function handleAction(name, e) {
    switch (name) {
        case 'open':            return openDialog();
        case 'new':             return newWorkflow();
        case 'templates':       return templatesDialog();
        case 'clear':           return clearCanvas(true);
        case 'save':            return saveWorkflow();
        case 'run':             return runWorkflow();
        case 'ai-send':         return aiSend();
        case 'diagnose':        return runDiagnose();
        case 'open-ai-tab':     return switchTab('ai');
        case 'zoom-in':         return setZoom(state.zoom + ZOOM_STEP);
        case 'zoom-out':        return setZoom(state.zoom - ZOOM_STEP);
        case 'zoom-reset':      return resetView();
        case 'zoom-fit':        return fitView();
        case 'ai-modal':        return openAIBuildModal();
        case 'ai-modal-close':  return closeAIBuildModal();
        case 'ai-modal-build':  return aiModalBuild();
        case 'replay-run':      return replayLastRun();
        case 'versions':        return openVersionsDialog();
        case 'undo':              return undo();
        case 'redo':              return redo();
        case 'bulk-retrigger':    return openBulkRetriggerDialog();
        case 'toggle-menu':       return toggleMenu(e);
        case 'save-as-template':  return saveAsTemplate();
        case 'import-template':   return importTemplateFromFile();
    }
}

// ============================================================
// Bulk re-trigger — run the workflow against historic docs
// ============================================================
function openBulkRetriggerDialog() {
    if (!state.currentWorkflow) {
        frappe.show_alert({ message: 'Save the workflow first', indicator: 'orange' }, 3);
        return;
    }
    const triggerDt = (state.trigger && state.trigger.doctype) || '';
    const d = new frappe.ui.Dialog({
        title: '<i class="ti ti-repeat"></i>&nbsp; Bulk re-trigger workflow',
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML', fieldname: 'intro',
                options: `<div style="padding: 0 0 12px; font-size: 12.5px; opacity: 0.85; line-height: 1.55">
                    Run this workflow against existing documents. Useful when you've added a
                    new workflow and want to apply it retroactively. Defaults to <b>dry run</b>
                    — toggle it off to actually mutate data.
                </div>`,
            },
            {
                fieldname: 'doctype', label: 'DocType', fieldtype: 'Link',
                options: 'DocType', reqd: 1, default: triggerDt,
                description: triggerDt ? `Defaults to this workflow's trigger doctype.` : '',
            },
            { fieldtype: 'Column Break' },
            {
                fieldname: 'max_docs', label: 'Max documents', fieldtype: 'Int',
                default: 100, description: 'Hard cap (max 500).',
            },
            { fieldtype: 'Section Break', label: 'Date range (optional)' },
            { fieldname: 'from_date', label: 'From (creation ≥)', fieldtype: 'Date' },
            { fieldtype: 'Column Break' },
            { fieldname: 'to_date',   label: 'To (creation ≤)',   fieldtype: 'Date' },
            { fieldtype: 'Section Break', label: 'Extra filters (optional)' },
            {
                fieldname: 'filters_json', label: 'Filters JSON', fieldtype: 'Code',
                options: 'JSON',
                description: 'Frappe filter dict, e.g. {"status": "Open"}. Combines with date range.',
            },
            { fieldtype: 'Section Break' },
            {
                fieldname: 'dry_run', label: 'Dry run (preview only — no writes)',
                fieldtype: 'Check', default: 1,
            },
            { fieldtype: 'Section Break' },
            { fieldtype: 'HTML', fieldname: 'preview',
              options: '<div id="fa-bulk-preview" style="font-size: 12.5px; opacity: 0.8"></div>' },
        ],
        primary_action_label: 'Queue runs',
        primary_action: vals => {
            if (!vals.doctype) {
                frappe.show_alert({ message: 'DocType required', indicator: 'orange' }, 3);
                return;
            }
            const confirmMsg = vals.dry_run
                ? `Queue ${vals.max_docs || 100} dry runs against ${vals.doctype}?`
                : `⚠️ Queue REAL workflow runs (with writes) against up to ${vals.max_docs || 100} ${vals.doctype} records?`;
            frappe.confirm(confirmMsg, () => {
                frappe.call({
                    method: 'flowagent.api.studio.bulk_retrigger',
                    args: {
                        workflow: state.currentWorkflow,
                        doctype: vals.doctype,
                        from_date: vals.from_date || null,
                        to_date: vals.to_date || null,
                        filters_json: vals.filters_json || null,
                        max_docs: vals.max_docs || 100,
                        dry_run: vals.dry_run ? 1 : 0,
                    },
                    callback: r => {
                        const res = r.message || {};
                        d.hide();
                        frappe.show_alert({
                            message: `✓ Queued ${res.queued} run${res.queued === 1 ? '' : 's'}${res.dry_run ? ' (dry)' : ''}`,
                            indicator: 'green',
                        }, 6);
                        addLog(`Bulk re-trigger queued ${res.queued} runs${res.dry_run ? ' (dry)' : ''}`, 'info');
                        // Refresh runs panel after a short delay so they appear
                        setTimeout(refreshRuns, 1500);
                    },
                });
            });
        },
    });
    d.show();

    // Live preview the count as the user adjusts filters
    function refreshPreview() {
        const vals = d.get_values(true);
        if (!vals || !vals.doctype) return;
        frappe.call({
            method: 'flowagent.api.studio.preview_retrigger_count',
            args: {
                workflow: state.currentWorkflow,
                doctype: vals.doctype,
                from_date: vals.from_date || null,
                to_date: vals.to_date || null,
                filters_json: vals.filters_json || null,
            },
            callback: r => {
                const c = r.message || {};
                const el = document.getElementById('fa-bulk-preview');
                if (!el) return;
                const cap = vals.max_docs || 100;
                el.innerHTML = c.count > 0
                    ? `<b>${c.count}</b> matching ${frappe.utils.escape_html(c.doctype)} record${c.count === 1 ? '' : 's'} found.
                       ${c.count > cap ? `<span style="color:#B45309"> First ${cap} will be processed.</span>` : ''}`
                    : `<span style="color:#71717A">No records match the current filters.</span>`;
            },
        });
    }
    setTimeout(() => {
        ['doctype', 'from_date', 'to_date', 'filters_json'].forEach(f => {
            const ctrl = d.get_field(f);
            if (ctrl && ctrl.$wrapper) {
                ctrl.$wrapper.on('change', refreshPreview);
            }
        });
        refreshPreview();
    }, 100);
}

// ============================================================
// Versions — list, restore, annotate
// ============================================================
function openVersionsDialog() {
    if (!state.currentWorkflow) {
        frappe.show_alert({ message: 'Save the workflow first', indicator: 'orange' }, 3);
        return;
    }
    frappe.call({
        method: 'flowagent.api.studio.list_versions',
        args: { workflow: state.currentWorkflow },
        callback: r => {
            const versions = r.message || [];
            const html = versions.length ? versions.map(v => `
                <div class="fa-ver-row" data-ver="${v.name}">
                    <div class="fa-ver-main">
                        <div class="fa-ver-label">${frappe.utils.escape_html(v.version_label || v.name)}</div>
                        <div class="fa-ver-meta">
                            ${v.node_count} nodes ·
                            by ${frappe.utils.escape_html(v.created_by_user || '?')} ·
                            ${frappe.datetime.comment_when(v.creation)}
                        </div>
                        ${v.message ? `<div class="fa-ver-msg">${frappe.utils.escape_html(v.message)}</div>` : ''}
                    </div>
                    <div class="fa-ver-actions">
                        <button class="fa-ver-btn" data-act="annotate" data-ver="${v.name}"
                                title="Add or edit a note for this version"><i class="ti ti-pencil"></i></button>
                        <button class="fa-ver-btn fa-ver-btn-primary" data-act="restore" data-ver="${v.name}">Restore</button>
                    </div>
                </div>
            `).join('') : '<p class="text-muted">No versions yet. Save the workflow to start its history.</p>';

            const d = new frappe.ui.Dialog({
                title: '<i class="ti ti-history"></i>&nbsp; Workflow versions',
                size: 'large',
                fields: [{
                    fieldtype: 'HTML',
                    options: `
                        <style>
                        .fa-ver-row {
                            display: flex; gap: 12px; padding: 12px;
                            border: 1px solid var(--border-color, #e5e7eb);
                            border-radius: 8px; margin-bottom: 8px;
                            align-items: flex-start;
                        }
                        .fa-ver-row:hover { background: var(--bg-light-gray, #f9fafb); }
                        .fa-ver-main { flex: 1; }
                        .fa-ver-label {
                            font-family: 'Geist Mono', ui-monospace, monospace;
                            font-size: 13px; font-weight: 600;
                            margin-bottom: 3px;
                        }
                        .fa-ver-meta { font-size: 11.5px; opacity: 0.7; }
                        .fa-ver-msg {
                            font-size: 12px; margin-top: 6px;
                            padding: 5px 9px; background: rgba(99,102,241,0.06);
                            border-left: 2px solid #6366F1;
                            border-radius: 3px;
                        }
                        .fa-ver-actions { display: flex; gap: 6px; }
                        .fa-ver-btn {
                            padding: 5px 10px; border-radius: 5px;
                            border: 1px solid var(--border-color, #d4d4d8);
                            background: white; font-size: 12px;
                            cursor: pointer;
                        }
                        .fa-ver-btn:hover { background: #f4f4f5; }
                        .fa-ver-btn-primary {
                            background: #6366F1; color: white; border-color: #6366F1;
                            font-weight: 500;
                        }
                        .fa-ver-btn-primary:hover { background: #4F46E5; border-color: #4F46E5; }
                        </style>
                        ${html}
                    `,
                }],
            });
            d.show();
            setTimeout(() => {
                d.$wrapper.find('[data-act="restore"]').on('click', function () {
                    const ver = this.dataset.ver;
                    frappe.confirm(
                        'Restore this version? Your current state will also be saved as a new version first, so this is reversible.',
                        () => restoreVersion(ver, d),
                    );
                });
                d.$wrapper.find('[data-act="annotate"]').on('click', function () {
                    const ver = this.dataset.ver;
                    const current = '';  // we don't have it on the row; user will type
                    frappe.prompt(
                        [{ fieldname: 'msg', label: 'Message', fieldtype: 'Data', reqd: 1 }],
                        vals => {
                            frappe.call({
                                method: 'flowagent.api.studio.annotate_version',
                                args: { version: ver, message: vals.msg },
                                callback: () => {
                                    frappe.show_alert({ message: 'Note saved', indicator: 'green' }, 2);
                                    d.hide();
                                    openVersionsDialog();  // reopen to refresh
                                },
                            });
                        },
                        'Annotate version', 'Save',
                    );
                });
            }, 50);
        },
    });
}

function restoreVersion(versionName, dialog) {
    frappe.call({
        method: 'flowagent.api.studio.restore_version',
        args: { version: versionName },
        callback: r => {
            if (r.message && r.message.restored) {
                frappe.show_alert({ message: 'Version restored — reloading…', indicator: 'green' }, 3);
                if (dialog) dialog.hide();
                // Reload the workflow into the canvas so the user sees the restored state
                loadWorkflow(r.message.workflow);
            }
        },
    });
}

// Replay the most recently inspected run with its original payload.
// Lets users iterate on a workflow without picking the same record
// every time.
function replayLastRun() {
    if (!state.lastRun) {
        frappe.show_alert({ message: 'No run to replay', indicator: 'orange' }, 3);
        return;
    }
    // Use the stored payload from the last manual run if we have it; otherwise
    // reconstruct from the run's trigger_payload (server returns it on get_run).
    let payload = state.lastPayload;
    if (!payload) {
        // The trigger_payload from get_run contains the full hydrated context.
        // Strip down to {doctype, name} so run_workflow_now re-hydrates fresh
        // (in case the doc was updated since the original run).
        const tp = state.lastRun.trigger_payload || {};
        if (tp.doctype && tp.doc_name) {
            payload = { doctype: tp.doctype, name: tp.doc_name };
        } else {
            payload = tp;
        }
    }
    addLog(`Replaying ${state.lastRun.name}…`, 'info');
    executeRun(payload);
}

function openAIBuildModal() {
    const modal = document.getElementById('fa-ai-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    // Stop the FAB pulse once the user has discovered it
    const fab = document.getElementById('fa-ai-fab');
    if (fab) fab.classList.remove('fa-ai-fab-pulse');
    try { localStorage.setItem('flowagent.aiFabSeen', '1'); } catch (_) {}

    // Decide default mode: if there's an existing workflow on the canvas,
    // default to "modify" so the user can iteratively refine. Otherwise
    // default to "create".
    const hasExistingWorkflow = state.nodes && state.nodes.length > 0;
    setAIMode(hasExistingWorkflow ? 'modify' : 'create');
    // Show the modify tab as enabled only when there's a workflow to modify
    const modifyBtn = document.getElementById('fa-ai-mode-modify-btn');
    if (modifyBtn) {
        modifyBtn.disabled = !hasExistingWorkflow;
        modifyBtn.style.opacity = hasExistingWorkflow ? '' : '0.4';
        modifyBtn.style.cursor = hasExistingWorkflow ? 'pointer' : 'not-allowed';
    }
    const countEl = document.getElementById('fa-ai-mode-count');
    if (countEl) {
        countEl.textContent = hasExistingWorkflow ? `(${state.nodes.length} nodes)` : '';
    }

    // Focus the textarea after the modal animates in
    setTimeout(() => {
        const ta = document.getElementById('fa-ai-modal-input');
        if (ta) ta.focus();
    }, 50);
    // Esc to close
    state._aiModalEsc = function (e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeAIBuildModal();
        }
        // Enter (no shift) to submit
        if (e.key === 'Enter' && !e.shiftKey && document.activeElement &&
            document.activeElement.id === 'fa-ai-modal-input') {
            e.preventDefault();
            aiModalBuild();
        }
    };
    document.addEventListener('keydown', state._aiModalEsc);
}

function setAIMode(mode) {
    state.aiMode = mode;
    // Update tab UI
    document.querySelectorAll('.fa-ai-mode-tab').forEach(btn => {
        btn.classList.toggle('fa-ai-mode-active', btn.dataset.mode === mode);
    });
    // Swap placeholder + button label + sub text + tip list
    const ta = document.getElementById('fa-ai-modal-input');
    const sub = document.getElementById('fa-ai-modal-sub');
    const buildLabel = document.getElementById('fa-ai-modal-build-label');
    const tipsCreate = document.getElementById('fa-ai-modal-tips-create');
    const tipsModify = document.getElementById('fa-ai-modal-tips-modify');
    if (mode === 'modify') {
        if (ta) ta.placeholder = 'Add a Slack notification after the AI step, and only if the amount is above 10000…';
        if (sub) sub.textContent = 'Describe a change to apply to the current workflow.';
        if (buildLabel) buildLabel.textContent = 'Apply change';
        if (tipsCreate) tipsCreate.style.display = 'none';
        if (tipsModify) tipsModify.style.display = '';
    } else {
        if (ta) ta.placeholder = "When a Sales Invoice is submitted with grand_total > 50000, send a WhatsApp approval to the manager…";
        if (sub) sub.textContent = "Describe what you want. We'll build it.";
        if (buildLabel) buildLabel.textContent = 'Build workflow';
        if (tipsCreate) tipsCreate.style.display = '';
        if (tipsModify) tipsModify.style.display = 'none';
    }
}

function closeAIBuildModal() {
    const modal = document.getElementById('fa-ai-modal');
    if (!modal) return;
    modal.style.display = 'none';
    if (state._aiModalEsc) {
        document.removeEventListener('keydown', state._aiModalEsc);
        state._aiModalEsc = null;
    }
}

function aiModalBuild() {
    const ta = document.getElementById('fa-ai-modal-input');
    if (!ta) return;
    const msg = ta.value.trim();
    if (!msg) {
        ta.focus();
        return;
    }
    const buildBtn = document.querySelector('[data-action="ai-modal-build"]');
    if (buildBtn) {
        buildBtn.disabled = true;
        buildBtn.innerHTML = '<i class="ti ti-loader-2 fa-spin"></i> Working…';
    }

    // Prepare args. In modify mode, send the current workflow so the
    // model can revise it instead of starting over.
    const args = { prompt: msg, mode: state.aiMode };
    if (state.aiMode === 'modify') {
        // Sync any pending Link control values into node cfg before snapshotting
        if (typeof syncAllControls === 'function') syncAllControls();
        args.current_workflow = JSON.stringify({
            workflow_name: state.workflowName,
            trigger: inferTriggerFromCanvas(),
            nodes: state.nodes.map(n => ({
                id: n.id, type: n.type, x: n.x, y: n.y, cfg: n.cfg,
            })),
            edges: state.edges.map(e => ({ from: e.from, to: e.to, fromPort: e.fromPort })),
        });
    }

    frappe.call({
        method: 'flowagent.api.ai_build.build_from_prompt',
        args: args,
        callback: r => {
            if (buildBtn) {
                buildBtn.disabled = false;
                const label = state.aiMode === 'modify' ? 'Apply change' : 'Build workflow';
                buildBtn.innerHTML = `<i class="ti ti-sparkles"></i> ${label}`;
            }
            const parsed = r.message;
            if (!parsed || !parsed.nodes) {
                frappe.show_alert({
                    message: 'AI could not produce a workflow. Try rephrasing.',
                    indicator: 'orange',
                }, 6);
                return;
            }
            applyAIWorkflow(parsed);
            closeAIBuildModal();
            ta.value = '';
            const verb = parsed._mode === 'modify' ? 'Updated' : 'Built';
            frappe.show_alert({
                message: `✓ ${verb} ${parsed.nodes.length} nodes — review and Save`,
                indicator: 'green',
            }, 6);
            addLog(`AI ${verb.toLowerCase()} ${parsed.nodes.length} nodes from prompt`, 'ok');
        },
        error: err => {
            if (buildBtn) {
                buildBtn.disabled = false;
                const label = state.aiMode === 'modify' ? 'Apply change' : 'Build workflow';
                buildBtn.innerHTML = `<i class="ti ti-sparkles"></i> ${label}`;
            }
            frappe.show_alert({
                message: 'AI Build failed: ' + ((err && err.message) || 'unknown error'),
                indicator: 'red',
            }, 8);
        },
    });
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
    state.history = [];
    state.historyIndex = -1;
    document.getElementById('fa-wf-name').textContent = n;
    document.getElementById('fa-enabled-toggle').checked = false;
    renderAll();
    renderConfigPanel();
    document.getElementById('fa-empty').style.display = '';
    snapshotState(true);  // initial blank state
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
            // Reset history so undo doesn't try to revert across workflows
            state.history = [];
            state.historyIndex = -1;
            snapshotState(true);
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
                if (idx.ok && idx.registered && idx.restart_needed) {
                    // Successful save but the worker's loaded doc_events
                    // doesn't yet include this trigger DocType — needs restart.
                    frappe.show_alert({
                        message: `Saved — bench restart needed for trigger to fire`,
                        indicator: 'orange',
                    }, 10);
                    addLog(idx.reason, 'warn');
                } else if (idx.ok && idx.registered) {
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
    snapshotState(true);  // so Ctrl+Z can recover an accidental clear
}

// ============================================================
// Canvas: drag, drop, render, wire
// ============================================================
function handleDrop(e) {
    if (!state.draggingType) return;
    const { wx, wy } = screenToWorld(e.clientX, e.clientY);
    addNode(state.draggingType, wx - 90, wy - 40);
    state.draggingType = null;
    document.getElementById('fa-empty').style.display = 'none';
}

// Convert a screen-space (clientX, clientY) into world coordinates within
// the canvas stage. Required everywhere we accept mouse input because
// nodes live in world space but mouse events report screen pixels.
function screenToWorld(clientX, clientY) {
    const wrap = document.getElementById('fa-canvas-wrap');
    const rect = wrap.getBoundingClientRect();
    const sx = clientX - rect.left;
    const sy = clientY - rect.top;
    return {
        wx: (sx - state.panX) / state.zoom,
        wy: (sy - state.panY) / state.zoom,
    };
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
    snapshotState(true);
    return id;
}

function renderAll() {
    document.getElementById('fa-canvas').innerHTML = '';
    state.nodes.forEach(renderNode);
    renderEdges();
    refreshTriggerIndicator();
    applyTransform();
    renderMinimap();
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
    // Branched nodes default to out-yes / out-no for conditions. Other
    // branched nodes (e.g. logic_approval) declare a `branchPorts` pair
    // and we render their labels accordingly.
    const branchPorts = (def.branchPorts && def.branchPorts.length === 2) ? def.branchPorts : ['out-yes', 'out-no'];
    const branchLabels = (def.branchPorts && def.branchPorts[0] === 'out-approve') ? ['✓', '✗'] : ['Y', 'N'];

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
            ? `<div class="fa-port fa-port-yes" data-node="${n.id}" data-port="${branchPorts[0]}"></div>
               <div class="fa-port fa-port-no"  data-node="${n.id}" data-port="${branchPorts[1]}"></div>
               <span class="fa-port-label fa-port-label-yes">${branchLabels[0]}</span>
               <span class="fa-port-label fa-port-label-no">${branchLabels[1]}</span>`
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
    // If user is space-panning, skip node drag
    if (state.spaceDown) return;
    const n = state.nodes.find(x => x.id === id);
    if (!n) return;
    e.preventDefault();
    // Compute the offset between the cursor (in world space) and the node origin
    const start = screenToWorld(e.clientX, e.clientY);
    const ox = start.wx - n.x;
    const oy = start.wy - n.y;
    const el = document.getElementById('fa-node-' + id);
    let rafId = null;
    let pendingX = n.x, pendingY = n.y;
    function move(e2) {
        const w = screenToWorld(e2.clientX, e2.clientY);
        pendingX = Math.max(0, w.wx - ox);
        pendingY = Math.max(0, w.wy - oy);
        // Move the node element immediately for snappy feel — this is cheap
        if (el) { el.style.left = pendingX + 'px'; el.style.top = pendingY + 'px'; }
        // Throttle the expensive bits (edge redraw, minimap) to one per frame
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
            rafId = null;
            n.x = pendingX;
            n.y = pendingY;
            renderEdgesFast();
        });
    }
    function up() {
        document.removeEventListener('mousemove', move);
        document.removeEventListener('mouseup', up);
        if (rafId) cancelAnimationFrame(rafId);
        n.x = pendingX;
        n.y = pendingY;
        renderEdges();
        renderMinimap();
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
}

// Cheap variant of renderEdges that only updates the `d` attributes of
// existing paths instead of rebuilding the whole SVG. Used during drag.
function renderEdgesFast() {
    const svg = document.getElementById('fa-edges');
    if (!svg) return;
    // Build a lookup of existing flow overlay paths by edge key, so when a
    // node is dragged mid-run the animated overlay tracks the base path.
    const flowByKey = new Map();
    svg.querySelectorAll('.fa-edge-running-flow').forEach(p => {
        flowByKey.set(p.getAttribute('data-edge-key'), p);
    });
    const paths = svg.querySelectorAll('path.fa-edge-path');
    state.edges.forEach((e, i) => {
        const from = state.nodes.find(n => n.id === e.from);
        const to = state.nodes.find(n => n.id === e.to);
        if (!from || !to) return;
        const fp = portXY(from, e.fromPort || 'out');
        const tp = portXY(to, 'in');
        const dx = (tp.x - fp.x) / 2;
        const d = `M${fp.x},${fp.y} C${fp.x + dx},${fp.y} ${tp.x - dx},${tp.y} ${tp.x},${tp.y}`;
        if (paths[i]) paths[i].setAttribute('d', d);
        const flow = flowByKey.get(_edgeKey(e));
        if (flow) flow.setAttribute('d', d);
    });
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
    const fromNode = state.nodes.find(n => n.id === fromNodeId);
    if (!fromNode) return;

    // Highlight the source port so the user knows wire-drag mode is active
    flashPort(fromNodeId, fromPort, true);

    // Add a live preview path to the edges SVG (which lives inside the
    // transformed stage, so we plot in WORLD coordinates)
    const svg = document.getElementById('fa-edges');
    const previewPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    previewPath.setAttribute('class', 'fa-edge-path fa-edge-preview');
    svg.appendChild(previewPath);

    function onMove(e) {
        const fp = portXY(fromNode, fromPort);
        const { wx, wy } = screenToWorld(e.clientX, e.clientY);
        const dx = (wx - fp.x) / 2;
        previewPath.setAttribute('d',
            `M${fp.x},${fp.y} C${fp.x + dx},${fp.y} ${wx - dx},${wy} ${wx},${wy}`);
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
        snapshotState(true);
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
    if (!svg) return;
    // Size SVG based on actual content. A massive fixed canvas is a paint
    // hog; this stays just big enough for the current graph plus margin.
    let maxX = 1200, maxY = 800;
    state.nodes.forEach(n => {
        if (n.x + 300 > maxX) maxX = n.x + 300;
        if (n.y + 200 > maxY) maxY = n.y + 200;
    });
    svg.setAttribute('width', maxX);
    svg.setAttribute('height', maxY);
    svg.style.width = maxX + 'px';
    svg.style.height = maxY + 'px';
    svg.innerHTML = '';
    state.edges.forEach(e => {
        const from = state.nodes.find(n => n.id === e.from);
        const to = state.nodes.find(n => n.id === e.to);
        if (!from || !to) return;
        const fp = portXY(from, e.fromPort || 'out');
        const tp = portXY(to, 'in');
        const dx = (tp.x - fp.x) / 2;
        const d = `M${fp.x},${fp.y} C${fp.x + dx},${fp.y} ${tp.x - dx},${tp.y} ${tp.x},${tp.y}`;
        const key = _edgeKey(e);

        // Base path — the static line. Tagged with the edge key so
        // updateRunAnimations() can find and toggle classes on it
        // without rebuilding the SVG.
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', d);
        path.setAttribute('class', 'fa-edge-path');
        path.setAttribute('data-edge-key', key);
        if (e.runHighlight) path.classList.add('fa-edge-active');
        if (e.runActive)    path.classList.add('fa-edge-running-base');
        svg.appendChild(path);

        // Animated overlay — only on edges feeding into the next-to-fire
        // node. We use pure CSS stroke-dashoffset animation for the flow
        // effect; the SVG element stays in place across polling cycles
        // so the animation doesn't restart and look jittery.
        if (e.runActive) {
            const flow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            flow.setAttribute('d', d);
            flow.setAttribute('class', 'fa-edge-running-flow');
            flow.setAttribute('data-edge-key', key);
            svg.appendChild(flow);
        }
    });
}

// Stable identifier for an edge so we can find its DOM element across
// polling cycles even if state.edges gets reordered.
function _edgeKey(e) {
    return `${e.from}|${e.to}|${e.fromPort || 'out'}`;
}

// Update only the run-state classes on existing edge paths, and add or
// remove the flow overlay as needed. Crucially: does NOT rebuild the
// SVG, so CSS animations on existing elements continue smoothly.
//
// Called by paintTrace on every polling tick. The full renderEdges()
// rebuild is reserved for actual graph changes (drag, wire, delete).
//
// If the SVG is out of sync with state.edges (e.g. a new edge was wired
// without renderEdges having been called), we fall through to a full
// rebuild rather than silently skipping the missing edge.
function updateRunAnimations() {
    const svg = document.getElementById('fa-edges');
    if (!svg) return;

    // Build a lookup of existing path elements by edge key
    const existingBase = new Map();
    const existingFlow = new Map();
    svg.querySelectorAll('.fa-edge-path').forEach(p => {
        existingBase.set(p.getAttribute('data-edge-key'), p);
    });
    svg.querySelectorAll('.fa-edge-running-flow').forEach(p => {
        existingFlow.set(p.getAttribute('data-edge-key'), p);
    });

    // Sync check: if any current edge lacks a base path, the SVG is out
    // of date and we need to rebuild.
    for (const e of state.edges) {
        if (!existingBase.has(_edgeKey(e))) {
            renderEdges();
            return;
        }
    }
    // Also detect stale paths (edge removed from state but still in DOM)
    if (existingBase.size !== state.edges.length) {
        renderEdges();
        return;
    }

    const desiredKeys = new Set();

    state.edges.forEach(e => {
        const key = _edgeKey(e);
        desiredKeys.add(key);
        const path = existingBase.get(key);
        // Toggle classes only when state actually changed. classList.toggle
        // with an explicit boolean is a no-op when it matches the current
        // state, which is exactly the property we want for CSS animations.
        path.classList.toggle('fa-edge-active', !!e.runHighlight);
        path.classList.toggle('fa-edge-running-base', !!e.runActive);

        const flow = existingFlow.get(key);
        if (e.runActive && !flow) {
            // Need to add a flow overlay — copy the d attribute from the base
            const newFlow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            newFlow.setAttribute('d', path.getAttribute('d'));
            newFlow.setAttribute('class', 'fa-edge-running-flow');
            newFlow.setAttribute('data-edge-key', key);
            svg.appendChild(newFlow);
        } else if (!e.runActive && flow) {
            flow.remove();
        }
    });

    // Clean up any stale flow overlays whose edge no longer exists
    existingFlow.forEach((flow, key) => {
        if (!desiredKeys.has(key)) flow.remove();
    });
}

function portXY(node, port) {
    // Node is 184px wide, head ~46px + body ~36px ≈ 88px total.
    const W = 184, H = 88;
    if (port === 'in')          return { x: node.x,       y: node.y + H / 2 };
    if (port === 'out')         return { x: node.x + W,   y: node.y + H / 2 };
    if (port === 'out-yes')     return { x: node.x + W,   y: node.y + H * 0.36 };
    if (port === 'out-no')      return { x: node.x + W,   y: node.y + H * 0.64 };
    // logic_approval uses the same two positions but with semantic names
    if (port === 'out-approve') return { x: node.x + W,   y: node.y + H * 0.36 };
    if (port === 'out-reject')  return { x: node.x + W,   y: node.y + H * 0.64 };
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

    // Advanced section — applies to every node type. Collapsible because
    // most workflows won't need to touch retry settings.
    const retryAttempts = n.cfg.retry_attempts || '';
    const retryDelay = n.cfg.retry_delay_ms || '';
    html += `
        <div class="fa-cfg-advanced">
            <div class="fa-cfg-advanced-head" data-fa-advanced-toggle>
                <i class="ti ti-chevron-right fa-cfg-adv-chev"></i>
                <span>Advanced</span>
                <span class="fa-cfg-adv-hint">retry on failure</span>
            </div>
            <div class="fa-cfg-advanced-body" style="display:none">
                <div class="fa-field">
                    <label>Retry attempts on failure</label>
                    <input type="number" min="0" max="10"
                           data-cfg-key="retry_attempts"
                           value="${frappe.utils.escape_html(String(retryAttempts))}"
                           placeholder="0">
                </div>
                <div class="fa-field">
                    <label>Retry delay (ms)</label>
                    <input type="number" min="0" step="100"
                           data-cfg-key="retry_delay_ms"
                           value="${frappe.utils.escape_html(String(retryDelay))}"
                           placeholder="exponential backoff if blank">
                </div>
            </div>
        </div>
    `;
    body.innerHTML = html;

    // Advanced section toggle
    const advHead = body.querySelector('[data-fa-advanced-toggle]');
    if (advHead) {
        advHead.addEventListener('click', () => {
            const advBody = body.querySelector('.fa-cfg-advanced-body');
            const chev = body.querySelector('.fa-cfg-adv-chev');
            const isOpen = advBody.style.display !== 'none';
            advBody.style.display = isOpen ? 'none' : '';
            chev.style.transform = isOpen ? '' : 'rotate(90deg)';
        });
    }

    // Plain inputs / textareas / selects — bind change handlers
    body.querySelectorAll('[data-cfg-key]').forEach(inp => {
        inp.addEventListener('input', e => {
            const key = inp.dataset.cfgKey;
            n.cfg[key] = inp.value;
            renderNode(n);
            snapshotState(false);  // debounced
        });
        if (inp.tagName === 'SELECT') {
            inp.addEventListener('change', e => {
                const key = inp.dataset.cfgKey;
                n.cfg[key] = inp.value;
                renderNode(n);
                snapshotState(true);
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
    snapshotState(true);
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
// ============================================================
// User templates (browser-local, per-user)
// ============================================================
// User-saved templates live in localStorage under flowagent.userTemplates
// as a map of slug -> template object. Same shape as the built-in TEMPLATES
// entries except they include a `_user: true` flag so the UI can show a
// delete button.

function loadUserTemplates() {
    try {
        return JSON.parse(localStorage.getItem('flowagent.userTemplates') || '{}');
    } catch (_) {
        return {};
    }
}

function saveUserTemplates(map) {
    try {
        localStorage.setItem('flowagent.userTemplates', JSON.stringify(map));
        return true;
    } catch (e) {
        frappe.show_alert({ message: 'Could not save (storage quota?)', indicator: 'red' }, 4);
        return false;
    }
}

// Save the current canvas as a user template.
function saveAsTemplate() {
    if (!state.nodes.length) {
        frappe.show_alert({ message: 'Canvas is empty', indicator: 'orange' }, 3);
        return;
    }
    syncAllControls();
    const d = new frappe.ui.Dialog({
        title: 'Save as template',
        fields: [
            { fieldname: 'name',        label: 'Template name', fieldtype: 'Data', reqd: 1,
              default: state.workflowName || 'My template' },
            { fieldname: 'category',    label: 'Category',      fieldtype: 'Data',
              default: 'Custom' },
            { fieldname: 'description', label: 'Description',   fieldtype: 'Small Text',
              description: 'Short summary shown in the template grid' },
        ],
        primary_action_label: 'Save',
        primary_action: vals => {
            const slug = 'user_' + (vals.name || '').toLowerCase()
                .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') + '_' + Date.now().toString(36);
            const map = loadUserTemplates();
            map[slug] = {
                name: vals.name,
                category: vals.category || 'Custom',
                description: vals.description || '',
                icon: 'ti-bookmark',
                accent: '#6366F1',
                _user: true,
                // Serialise nodes in template-loader shape: { t, cfg }
                nodes: state.nodes.map(n => ({ t: n.type, cfg: JSON.parse(JSON.stringify(n.cfg || {})) })),
                // Edges + trigger so re-loaded templates wire up exactly
                _edges: state.edges.map(e => ({ from: e.from, to: e.to, fromPort: e.fromPort })),
                _node_ids: state.nodes.map(n => n.id),
                trigger: inferTriggerFromCanvas(),
            };
            if (!saveUserTemplates(map)) return;
            d.hide();
            frappe.show_alert({ message: 'Template saved', indicator: 'green' }, 3);
        },
    });
    d.show();
}

function deleteUserTemplate(slug) {
    const map = loadUserTemplates();
    if (!map[slug]) return;
    frappe.confirm(`Delete template "${map[slug].name}"?`, () => {
        delete map[slug];
        saveUserTemplates(map);
        // Reopen the dialog to refresh
        const open = document.querySelector('.fa-templates-grid');
        if (open) {
            // Find and close existing dialog
            $('.modal.fade.in, .modal.fade.show').modal('hide');
        }
        templatesDialog();
    });
}

// Export a template (built-in or user) as a downloadable JSON file.
function exportTemplate(key) {
    const tpl = TEMPLATES[key] || loadUserTemplates()[key];
    if (!tpl) return;
    const json = JSON.stringify({
        flowagent_template_version: 1,
        slug: key,
        ...tpl,
    }, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(tpl.name || key).replace(/[^a-z0-9]+/gi, '_')}.flowagent-template.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

// Import a template from a user-picked JSON file. Stored as a user template.
function importTemplateFromFile() {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = '.json,application/json';
    inp.onchange = () => {
        const file = inp.files && inp.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = e => {
            try {
                const data = JSON.parse(e.target.result);
                if (!data.nodes || !Array.isArray(data.nodes)) {
                    throw new Error('JSON does not look like a template (missing nodes)');
                }
                const slug = (data.slug || 'imported_' + Date.now().toString(36));
                const map = loadUserTemplates();
                map[slug] = {
                    name: data.name || 'Imported template',
                    category: data.category || 'Imported',
                    description: data.description || '',
                    icon: data.icon || 'ti-download',
                    accent: data.accent || '#6366F1',
                    _user: true,
                    nodes: data.nodes,
                    _edges: data._edges,
                    _node_ids: data._node_ids,
                    trigger: data.trigger,
                };
                saveUserTemplates(map);
                frappe.show_alert({ message: `Imported "${map[slug].name}"`, indicator: 'green' }, 3);
                $('.modal.fade.in, .modal.fade.show').modal('hide');
                templatesDialog();
            } catch (err) {
                frappe.show_alert({ message: 'Invalid template file: ' + err.message, indicator: 'red' }, 6);
            }
        };
        reader.readAsText(file);
    };
    inp.click();
}

function templatesDialog() {
    const userTemplates = loadUserTemplates();
    const allTpls = { ...TEMPLATES, ...userTemplates };

    // Build the card grid HTML
    const cards = Object.entries(allTpls).map(([key, tpl]) => {
        const isUser = tpl._user;
        return `
            <div class="fa-template-card" data-tpl="${key}"
                 style="--accent:${tpl.accent};--accent-bg:${tpl.accent}22">
                ${isUser ? '<div class="fa-tpl-user-badge">yours</div>' : ''}
                <div class="fa-tpl-icon"><i class="ti ${tpl.icon}"></i></div>
                <div class="fa-tpl-title">${frappe.utils.escape_html(tpl.name)}</div>
                <div class="fa-tpl-desc">${frappe.utils.escape_html(tpl.description || '')}</div>
                <div class="fa-tpl-meta">
                    <span class="fa-tpl-chip">${frappe.utils.escape_html(tpl.category)}</span>
                    <span class="fa-tpl-chip">${tpl.nodes.length} nodes</span>
                </div>
                <div class="fa-tpl-actions">
                    <button class="fa-tpl-act" data-tpl-act="export" data-tpl-key="${key}"
                            title="Export as JSON"
                            onclick="event.stopPropagation()">
                        <i class="ti ti-download"></i>
                    </button>
                    ${isUser ? `
                    <button class="fa-tpl-act fa-tpl-act-del" data-tpl-act="delete" data-tpl-key="${key}"
                            title="Delete template"
                            onclick="event.stopPropagation()">
                        <i class="ti ti-trash"></i>
                    </button>` : ''}
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
                .fa-tpl-user-badge {
                    position: absolute;
                    top: 12px; right: 12px;
                    font-size: 9px;
                    font-weight: 600;
                    color: #6366F1;
                    background: rgba(99,102,241,0.1);
                    padding: 2px 7px;
                    border-radius: 9px;
                    text-transform: uppercase;
                    letter-spacing: 0.07em;
                }
                .fa-tpl-actions {
                    position: absolute;
                    bottom: 10px; right: 10px;
                    display: none;
                    gap: 4px;
                }
                .fa-template-card:hover .fa-tpl-actions { display: flex; }
                .fa-tpl-act {
                    width: 26px; height: 26px;
                    border-radius: 5px;
                    border: 1px solid var(--border-color, #d4d4d8);
                    background: white;
                    color: var(--text-muted, #71717A);
                    cursor: pointer;
                    display: flex; align-items: center; justify-content: center;
                }
                [data-theme="dark"] .fa-tpl-act { background: #131316; color: #A1A1AA; }
                .fa-tpl-act:hover {
                    background: #f4f4f5; color: var(--text-color, #18181B);
                }
                .fa-tpl-act-del:hover { color: #B91C1C; border-color: #FCA5A5; }
                .fa-tpl-tools {
                    display: flex; gap: 8px; margin-bottom: 12px;
                }
                .fa-tpl-tools-btn {
                    padding: 6px 12px;
                    border-radius: 6px;
                    border: 1px solid var(--border-color, #d4d4d8);
                    background: white;
                    color: var(--text-color, #18181B);
                    font-size: 12px;
                    font-weight: 500;
                    cursor: pointer;
                    display: inline-flex; align-items: center; gap: 5px;
                }
                [data-theme="dark"] .fa-tpl-tools-btn {
                    background: #131316; color: #F5F5F7; border-color: #2A2A30;
                }
                .fa-tpl-tools-btn:hover { background: #f4f4f5; }
                </style>
                <div class="fa-tpl-tools">
                    <button class="fa-tpl-tools-btn" data-tpl-tools="save-as">
                        <i class="ti ti-bookmark-plus"></i> Save canvas as template
                    </button>
                    <button class="fa-tpl-tools-btn" data-tpl-tools="import">
                        <i class="ti ti-upload"></i> Import JSON
                    </button>
                </div>
                <div class="fa-templates-grid">${cards}</div>
            `,
        }],
    });
    d.show();

    // Bind click handlers after the dialog body renders
    setTimeout(() => {
        d.$wrapper.find('.fa-template-card').on('click', function (e) {
            // Per-card action buttons stop propagation, so this only fires
            // on a real card click (not on Export/Delete buttons).
            const key = this.dataset.tpl;
            d.hide();
            loadTemplate(key);
        });
        d.$wrapper.find('[data-tpl-act="export"]').on('click', function (e) {
            e.stopPropagation();
            exportTemplate(this.dataset.tplKey);
        });
        d.$wrapper.find('[data-tpl-act="delete"]').on('click', function (e) {
            e.stopPropagation();
            deleteUserTemplate(this.dataset.tplKey);
        });
        // Header action buttons (Save as / Import)
        d.$wrapper.find('[data-tpl-tools="save-as"]').on('click', () => {
            d.hide();
            saveAsTemplate();
        });
        d.$wrapper.find('[data-tpl-tools="import"]').on('click', () => {
            importTemplateFromFile();
        });
    }, 50);
}

function loadTemplate(key) {
    const tpl = TEMPLATES[key] || loadUserTemplates()[key];
    if (!tpl) return;
    clearCanvas(false);
    state.workflowName = tpl.name;
    document.getElementById('fa-wf-name').textContent = tpl.name;
    state.trigger = tpl.trigger || { type: 'Manual' };

    if (tpl._user && tpl._edges && tpl._node_ids) {
        // User template — preserve the exact graph topology, not auto-chain
        const idMap = {};  // original id -> new id assigned by addNode
        tpl.nodes.forEach((nd, idx) => {
            const newId = addNode(nd.t, 40 + idx * 220, 160, nd.cfg);
            idMap[tpl._node_ids[idx]] = newId;
        });
        tpl._edges.forEach(e => {
            const from = idMap[e.from], to = idMap[e.to];
            if (from && to) {
                state.edges.push({ from, to, fromPort: e.fromPort });
            }
        });
    } else {
        // Built-in template — lay out left-to-right and auto-chain
        tpl.nodes.forEach((nd, idx) => {
            addNode(nd.t, 40 + idx * 220, 160, nd.cfg);
        });
        for (let i = 0; i < state.nodes.length - 1; i++) {
            const from = state.nodes[i], to = state.nodes[i + 1];
            if (from.def && from.def.hasBranch) {
                // Use the node's declared first branch port (out-yes by default,
                // out-approve for logic_approval, etc.)
                const defaultPort = (from.def.branchPorts && from.def.branchPorts[0]) || 'out-yes';
                state.edges.push({ from: from.id, to: to.id, fromPort: defaultPort });
            } else {
                state.edges.push({ from: from.id, to: to.id });
            }
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
    const dry = state.testMode ? 1 : 0;
    addLog(dry ? 'Test run (dry, no writes)…' : 'Running…', 'info');

    // Reset any leftover visual state from a previous run so the canvas
    // starts clean. This wipes the visual-state cache too so paintTrace
    // can properly apply diffs against a known baseline.
    resetRunVisualState();

    // Show the Trace tab immediately with a "running" placeholder so the
    // user knows things are happening even before the first step lands.
    switchTab('trace');
    renderTracePane({
        name: 'pending',
        status: 'Running',
        duration_ms: 0,
        steps: [],
        trigger_source: dry ? 'studio_dry_run' : 'studio_manual',
    });

    // Light up the trigger node(s) immediately while we wait for the first
    // step to land — gives instant visual feedback that the Run actually fired.
    state.nodes.forEach(n => {
        if (n.type && n.type.startsWith('trigger_')) {
            const el = document.getElementById('fa-node-' + n.id);
            if (el) {
                el.classList.add('fa-node-running');
                _runVisualState.nodeClass.set(n.id, 'running');
            }
        }
    });

    // Stop any prior polling
    if (state._runPollTimer) {
        clearTimeout(state._runPollTimer);
        state._runPollTimer = null;
    }

    frappe.call({
        method: 'flowagent.api.studio.run_workflow_now',
        args: {
            name: state.currentWorkflow,
            sync: 0,  // enqueue async so we can stream progress via polling
            payload: JSON.stringify(payload || {}),
            dry_run: dry,
        },
        callback: r => {
            const queued = r.message;
            if (!queued || !queued.run_name) {
                addLog('Run queue failed — falling back to sync', 'warn');
                return _executeRunSync(payload, dry);
            }
            state.lastPayload = payload;
            _startPollingRun(queued.run_name);
        },
        error: err => addLog('Run failed: ' + (err.message || err), 'err'),
    });
}

// Sync-execution fallback for when async enqueue isn't available
// (e.g. Redis down — run_workflow_now will still try the inline path).
function _executeRunSync(payload, dry) {
    frappe.call({
        method: 'flowagent.api.studio.run_workflow_now',
        args: {
            name: state.currentWorkflow,
            sync: 1,
            payload: JSON.stringify(payload || {}),
            dry_run: dry,
        },
        callback: r => {
            const run = r.message;
            if (!run) return;
            state.lastRun = run;
            paintTrace(run);
            refreshStats();
            switchTab('trace');
            addLog(`Run ${run.name}: ${run.status} (${run.duration_ms}ms)`,
                   run.status === 'Success' ? 'ok' : 'err');
        },
        error: err => addLog('Run failed: ' + (err.message || err), 'err'),
    });
}

// Poll a queued run until it reaches a terminal state. We paint each
// intermediate response so users see steps light up as the engine
// records them. Starts at 400ms for snappy initial response, backs off
// to 1500ms after 10 polls so a long workflow doesn't hammer the server.
// Pauses while the tab is hidden — browsers throttle background timers
// anyway, but pausing explicitly saves API calls.
function _startPollingRun(runName) {
    let lastStepCount = -1;
    let consecutiveErrors = 0;
    let pollCount = 0;
    let runFinished = false;
    const TERMINAL = new Set(['Success', 'Failed', 'Timeout', 'Cancelled']);

    const nextPollDelay = () => pollCount < 10 ? 400 : 1500;

    const scheduleNext = () => {
        if (runFinished) return;
        if (document.hidden) {
            // Wait for visibilitychange to resume
            return;
        }
        state._runPollTimer = setTimeout(fetchOnce, nextPollDelay());
    };

    const fetchOnce = () => {
        pollCount++;
        frappe.call({
            method: 'flowagent.api.studio.get_run',
            args: { run_name: runName },
            callback: r => {
                consecutiveErrors = 0;
                const run = r.message;
                if (!run) { scheduleNext(); return; }
                const steps = run.steps || [];
                if (steps.length !== lastStepCount || TERMINAL.has(run.status)) {
                    lastStepCount = steps.length;
                    state.lastRun = run;
                    paintTrace(run);
                }
                if (TERMINAL.has(run.status)) {
                    runFinished = true;
                    if (state._runPollTimer) {
                        clearTimeout(state._runPollTimer);
                        state._runPollTimer = null;
                    }
                    refreshStats();
                    addLog(`Run ${run.name}: ${run.status} (${run.duration_ms}ms)`,
                           run.status === 'Success' ? 'ok' : 'err');
                    return;
                }
                scheduleNext();
            },
            error: () => {
                consecutiveErrors++;
                if (consecutiveErrors >= 5) {
                    runFinished = true;
                    if (state._runPollTimer) {
                        clearTimeout(state._runPollTimer);
                        state._runPollTimer = null;
                    }
                    addLog('Lost contact with the run — check Runs tab manually', 'warn');
                    return;
                }
                scheduleNext();
            },
        });
    };

    // Resume polling immediately when the user returns to the tab
    const onVisibility = () => {
        if (!document.hidden && !runFinished && !state._runPollTimer) {
            fetchOnce();
        }
    };
    document.addEventListener('visibilitychange', onVisibility);
    state._runPollVisHandler = onVisibility;

    fetchOnce();
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

// Cache of the visual state we last painted, so subsequent paints can
// compute a minimal diff. CSS animations restart when their class is
// removed and re-added — so the trick to smooth animation across polling
// is to only touch nodes whose desired state actually changed.
const _runVisualState = {
    nodeClass: new Map(),      // node_id -> 'completed' | 'failed' | 'running' | null
    nodeWarning: new Map(),    // node_id -> warning text or null
    nodeStatus: new Map(),     // node_id -> dot status string or null
    loggedSteps: new Set(),    // step_index keys we've already addLog'd for this run
    runName: null,
};

function paintTrace(run) {
    const steps = run.steps || [];

    // If this is a different run than what we last painted, reset our caches.
    // A new run could legitimately have the same step state as the last frame
    // of the previous run; without the reset we'd skip the repaint.
    if (run.name !== _runVisualState.runName) {
        _runVisualState.nodeClass.clear();
        _runVisualState.nodeWarning.clear();
        _runVisualState.nodeStatus.clear();
        _runVisualState.loggedSteps.clear();
        _runVisualState.runName = run.name;
    }

    // ---- Compute the desired visual state per node ----
    const recordedIds = new Set();
    const completedIds = new Set();
    const desiredClass  = new Map();   // node_id -> class suffix
    const desiredWarn   = new Map();   // node_id -> warning text
    const desiredStatus = new Map();   // node_id -> step status

    steps.forEach(step => {
        recordedIds.add(step.node_id);
        desiredStatus.set(step.node_id, step.status);
        if (step.status === 'Success') {
            desiredClass.set(step.node_id, 'completed');
            completedIds.add(step.node_id);
        } else if (step.status === 'Failed' || step.status === 'Timeout') {
            desiredClass.set(step.node_id, 'failed');
        }
        // Render-warning badge condition (matches original logic)
        if (step.error && (step.error.startsWith('⚠') || (step.status === 'Success' && step.error))) {
            desiredWarn.set(step.node_id, step.error.replace(/^⚠\s*/, ''));
        }
    });

    // While the run is live, figure out which node(s) are *currently* firing.
    // The "running" node is the downstream target of the most recent step
    // that hasn't itself recorded a step yet. Completed/failed always wins
    // over running so we never blink between states on the same node.
    const runIsLive = run.status === 'Running' || run.status === 'Queued';
    if (runIsLive) {
        if (steps.length > 0) {
            const lastStep = steps[steps.length - 1];
            // Only propagate "running" downstream if the last step succeeded.
            // A failed step halts the workflow, so its downstream nodes will
            // never fire — marking them as running would mislead the user.
            if (lastStep.status === 'Success') {
                state.edges.forEach(e => {
                    if (e.from === lastStep.node_id && !recordedIds.has(e.to)) {
                        if (!desiredClass.has(e.to)) desiredClass.set(e.to, 'running');
                    }
                });
            }
        } else {
            // No steps recorded yet — the trigger is firing
            state.nodes.forEach(n => {
                if (n.type && n.type.startsWith('trigger_') && !desiredClass.has(n.id)) {
                    desiredClass.set(n.id, 'running');
                }
            });
        }
    }

    // ---- Apply node-class diff ----
    // Touch only the nodes whose desired class differs from the cache. This
    // is what keeps the pulse animation smooth: the class is added once
    // when the node enters the running state and not touched again until
    // it transitions out.
    state.nodes.forEach(n => {
        const el = document.getElementById('fa-node-' + n.id);
        if (!el) return;
        const want = desiredClass.get(n.id) || null;
        const prev = _runVisualState.nodeClass.get(n.id) || null;
        if (want === prev) return;
        if (prev) el.classList.remove('fa-node-' + prev);
        if (want) el.classList.add('fa-node-' + want);
        _runVisualState.nodeClass.set(n.id, want);
    });

    // ---- Apply status-dot diff ----
    state.nodes.forEach(n => {
        const dot = document.getElementById('fa-ns-' + n.id);
        if (!dot) return;
        const want = desiredStatus.get(n.id) || null;
        const prev = _runVisualState.nodeStatus.get(n.id) || null;
        if (want === prev) return;
        if (want) dot.setAttribute('data-status', want);
        else      dot.removeAttribute('data-status');
        _runVisualState.nodeStatus.set(n.id, want);
    });

    // ---- Apply warning-badge diff ----
    state.nodes.forEach(n => {
        const want = desiredWarn.get(n.id) || null;
        const prev = _runVisualState.nodeWarning.get(n.id) || null;
        if (want === prev) return;
        const nodeEl = document.getElementById('fa-node-' + n.id);
        if (!nodeEl) return;
        const existing = nodeEl.querySelector('.fa-node-warn-badge');
        if (existing) existing.remove();
        if (want) {
            const badge = document.createElement('div');
            badge.className = 'fa-node-warn-badge';
            badge.innerHTML = '<i class="ti ti-alert-triangle"></i>';
            badge.title = want;
            nodeEl.appendChild(badge);
        }
        _runVisualState.nodeWarning.set(n.id, want);
    });

    // ---- Apply edge state ----
    state.edges.forEach(e => {
        e.runHighlight = completedIds.has(e.from) && completedIds.has(e.to);
        e.runActive = false;
    });
    if (runIsLive && steps.length > 0) {
        const lastStep = steps[steps.length - 1];
        if (lastStep.status === 'Success') {
            state.edges.forEach(e => {
                if (e.from === lastStep.node_id && !recordedIds.has(e.to)) {
                    e.runActive = true;
                }
            });
        }
    }
    // Diff-update the SVG without rebuilding. This preserves the dashed
    // flow animation across polling cycles — it doesn't restart from zero
    // every time a poll lands.
    updateRunAnimations();

    // ---- Append log entries for steps we haven't logged yet ----
    steps.forEach(step => {
        const logKey = step.step_index + ':' + step.status;
        if (_runVisualState.loggedSteps.has(logKey)) return;
        _runVisualState.loggedSteps.add(logKey);
        addLog(
            `#${step.step_index} ${step.node_label} → ${step.status}${step.error ? ' — ' + (step.error || '').split('\n')[0] : ''} (${step.duration_ms}ms)`,
            step.status === 'Success' ? (step.error ? 'warn' : 'ok')
              : step.status === 'Failed' ? 'err' : 'warn'
        );
    });

    renderTracePane(run);
}

// Force-reset the cached run-visual state. Called when starting a brand
// new run so the previous run's completed/failed classes get properly
// cleaned off the canvas.
function resetRunVisualState() {
    _runVisualState.nodeClass.forEach((cls, nodeId) => {
        const el = document.getElementById('fa-node-' + nodeId);
        if (el && cls) el.classList.remove('fa-node-' + cls);
    });
    _runVisualState.nodeStatus.forEach((_, nodeId) => {
        const dot = document.getElementById('fa-ns-' + nodeId);
        if (dot) dot.removeAttribute('data-status');
    });
    _runVisualState.nodeWarning.forEach((_, nodeId) => {
        const el = document.getElementById('fa-node-' + nodeId);
        if (el) {
            const badge = el.querySelector('.fa-node-warn-badge');
            if (badge) badge.remove();
        }
    });
    _runVisualState.nodeClass.clear();
    _runVisualState.nodeStatus.clear();
    _runVisualState.nodeWarning.clear();
    _runVisualState.loggedSteps.clear();
    _runVisualState.runName = null;
    state.edges.forEach(e => { e.runHighlight = false; e.runActive = false; });
    updateRunAnimations();
}

// ============================================================
// Trace pane — step-by-step inspector with JSON variable trees
// ============================================================

// Compact token counts: 12345 → "12.3k", 999 → "999"
function formatTokens(n) {
    n = Number(n || 0);
    if (n < 1000) return String(n);
    if (n < 10000) return (n / 1000).toFixed(1) + 'k';
    return Math.round(n / 1000) + 'k';
}

// Format a small USD amount with appropriate precision.
function formatCost(usd) {
    usd = Number(usd || 0);
    if (usd === 0) return '$0';
    if (usd < 0.01) return '<$0.01';
    if (usd < 1)    return '$' + usd.toFixed(3);
    return '$' + usd.toFixed(2);
}

function renderTracePane(run) {
    state.lastRun = run;
    const body = document.getElementById('fa-trace-body');
    const replayBtn = document.getElementById('fa-trace-replay');
    if (!body) return;

    if (!run || !run.steps || !run.steps.length) {
        body.innerHTML = '<p class="fa-muted">No steps recorded for this run</p>';
        if (replayBtn) replayBtn.style.display = 'none';
        return;
    }

    if (replayBtn) replayBtn.style.display = '';

    const statusClass = run.status === 'Success' ? 'fa-trace-status-ok'
                      : run.status === 'Failed' ? 'fa-trace-status-err'
                      : 'fa-trace-status-warn';

    const errorMsg = run.error_message
        ? `<div class="fa-trace-error">${frappe.utils.escape_html(run.error_message).split('\n')[0]}</div>`
        : '';

    let stepsHtml = '';
    (run.steps || []).forEach((step, i) => {
        const stepStatus = step.status === 'Success' ? 'ok' : step.status === 'Failed' ? 'err' : 'warn';
        const warnIcon = (step.error && step.status === 'Success') ? '<i class="ti ti-alert-triangle" style="color:var(--fa-warn)" title="Render warning"></i> ' : '';
        // Detect dry-run output ({"_dry_run": true, ...}) so users can tell at
        // a glance which steps were simulated vs actually executed.
        let isDry = false;
        try {
            const out = typeof step.output === 'string' ? JSON.parse(step.output) : step.output;
            isDry = out && out._dry_run === true;
        } catch (_) { /* not JSON or not parseable */ }
        const dryPill = isDry ? '<span class="fa-trace-dry-pill">🧪 dry</span>' : '';
        stepsHtml += `
            <div class="fa-trace-step" data-step-idx="${i}">
                <div class="fa-trace-step-head">
                    <span class="fa-trace-step-idx">${step.step_index}</span>
                    <span class="fa-trace-step-dot fa-trace-step-dot-${stepStatus}"></span>
                    <span class="fa-trace-step-label">${warnIcon}${frappe.utils.escape_html(step.node_label || step.node_type || '')}</span>
                    ${dryPill}
                    <span class="fa-trace-step-ms">${step.duration_ms || 0}ms</span>
                    <i class="ti ti-chevron-down fa-trace-step-chevron"></i>
                </div>
                <div class="fa-trace-step-body" style="display:none">
                    ${step.error ? `<div class="fa-trace-${stepStatus === 'err' ? 'error' : 'warn'}-msg">${frappe.utils.escape_html(step.error)}</div>` : ''}
                    <div class="fa-trace-section-label">Input <span class="fa-trace-hint">click any value to copy its path</span></div>
                    <div class="fa-trace-tree" data-tree="input-${i}"></div>
                    <div class="fa-trace-section-label">Output</div>
                    <div class="fa-trace-tree" data-tree="output-${i}"></div>
                </div>
            </div>`;
    });

    // Render AI usage row only if this run actually made AI calls — for a
    // pure DocType-create workflow with no LLM nodes there's nothing to show.
    const tokensTotal = (run.ai_tokens_in || 0) + (run.ai_tokens_out || 0);
    const costStr = (run.ai_cost_usd || 0) > 0
        ? '$' + (run.ai_cost_usd || 0).toFixed(4)
        : '—';
    const usageRow = (run.ai_calls || 0) > 0 ? `
        <div class="fa-trace-trigger-info">
            <span class="fa-trace-meta-label">AI</span>
            <span class="fa-trace-meta-val">
                ${run.ai_calls} call${run.ai_calls === 1 ? '' : 's'}
                · ${formatTokens(run.ai_tokens_in)} in / ${formatTokens(run.ai_tokens_out)} out
                · ${costStr}
            </span>
        </div>` : '';

    body.innerHTML = `
        <div class="fa-trace-header">
            <div class="fa-trace-run-name">${run.name || 'Run'}</div>
            <div class="fa-trace-meta">
                <span class="fa-trace-status-pill ${statusClass}">${run.status || ''}</span>
                <span class="fa-trace-meta-item">${run.duration_ms || 0}ms</span>
                <span class="fa-trace-meta-item">${(run.steps || []).length} steps</span>
            </div>
            ${errorMsg}
            <div class="fa-trace-trigger-info">
                <span class="fa-trace-meta-label">trigger</span>
                <span class="fa-trace-meta-val">${frappe.utils.escape_html(run.trigger_source || 'manual')}</span>
            </div>
            ${usageRow}
        </div>
        <div class="fa-trace-steps">${stepsHtml}</div>
    `;

    // Bind expand/collapse on each step
    body.querySelectorAll('.fa-trace-step').forEach((stepEl, i) => {
        const head = stepEl.querySelector('.fa-trace-step-head');
        head.addEventListener('click', () => {
            const sb = stepEl.querySelector('.fa-trace-step-body');
            const chev = stepEl.querySelector('.fa-trace-step-chevron');
            const open = sb.style.display !== 'none';
            sb.style.display = open ? 'none' : '';
            stepEl.classList.toggle('fa-trace-step-open', !open);
            if (!open) {
                // Lazy-render the trees on first expand
                const step = run.steps[i];
                const inEl = stepEl.querySelector(`[data-tree="input-${i}"]`);
                const outEl = stepEl.querySelector(`[data-tree="output-${i}"]`);
                // Snapshots come back from the server as JSON strings (Long Text).
                // Parse them defensively — fall back to the raw string if invalid.
                const safeParse = v => {
                    if (v === null || v === undefined || v === '') return null;
                    if (typeof v !== 'string') return v;
                    try { return JSON.parse(v); }
                    catch (_) { return v; }
                };
                if (inEl && !inEl.dataset.rendered) {
                    renderJsonTree(inEl, safeParse(step.input), step.node_id || '');
                    inEl.dataset.rendered = '1';
                }
                if (outEl && !outEl.dataset.rendered) {
                    renderJsonTree(outEl, safeParse(step.output), step.node_id || '');
                    outEl.dataset.rendered = '1';
                }
            }
        });
    });
}

// Render a value as an interactive JSON tree. Each leaf is clickable to
// copy a Jinja path. `pathPrefix` is the path components leading up to
// this node (we don't suggest paths to the trigger context since users
// already know `trigger.doc.X` works — instead we copy the literal value).
function renderJsonTree(el, value, pathPrefix) {
    el.innerHTML = '';
    if (value === null || value === undefined) {
        el.innerHTML = '<span class="fa-trace-null">∅ no data</span>';
        return;
    }
    const node = buildJsonTreeNode(value, [], 0);
    el.appendChild(node);
}

function buildJsonTreeNode(value, path, depth) {
    const wrap = document.createElement('div');
    wrap.className = 'fa-tree-node';

    if (value === null) {
        wrap.innerHTML = '<span class="fa-tree-val fa-tree-null">null</span>';
        return wrap;
    }
    if (typeof value === 'boolean') {
        wrap.appendChild(_treeLeaf(String(value), 'bool', value, path));
        return wrap;
    }
    if (typeof value === 'number') {
        wrap.appendChild(_treeLeaf(String(value), 'num', value, path));
        return wrap;
    }
    if (typeof value === 'string') {
        wrap.appendChild(_treeLeaf(JSON.stringify(value), 'str', value, path));
        return wrap;
    }
    if (Array.isArray(value)) {
        if (value.length === 0) {
            wrap.innerHTML = '<span class="fa-tree-val fa-tree-empty">[ ]</span>';
            return wrap;
        }
        const head = document.createElement('div');
        head.className = 'fa-tree-collapsible';
        const isOpen = depth < 1;
        head.innerHTML = `<span class="fa-tree-toggle">${isOpen ? '▾' : '▸'}</span>
            <span class="fa-tree-meta">Array · ${value.length} item${value.length === 1 ? '' : 's'}</span>`;
        wrap.appendChild(head);
        const list = document.createElement('div');
        list.className = 'fa-tree-children';
        list.style.display = isOpen ? '' : 'none';
        value.forEach((v, i) => {
            const child = document.createElement('div');
            child.className = 'fa-tree-row';
            const key = document.createElement('span');
            key.className = 'fa-tree-key';
            key.textContent = '[' + i + ']';
            child.appendChild(key);
            child.appendChild(buildJsonTreeNode(v, path.concat([i]), depth + 1));
            list.appendChild(child);
        });
        wrap.appendChild(list);
        head.addEventListener('click', () => {
            const open = list.style.display !== 'none';
            list.style.display = open ? 'none' : '';
            head.querySelector('.fa-tree-toggle').textContent = open ? '▸' : '▾';
        });
        return wrap;
    }
    if (typeof value === 'object') {
        const keys = Object.keys(value);
        if (keys.length === 0) {
            wrap.innerHTML = '<span class="fa-tree-val fa-tree-empty">{ }</span>';
            return wrap;
        }
        const head = document.createElement('div');
        head.className = 'fa-tree-collapsible';
        const isOpen = depth < 1;
        head.innerHTML = `<span class="fa-tree-toggle">${isOpen ? '▾' : '▸'}</span>
            <span class="fa-tree-meta">Object · ${keys.length} field${keys.length === 1 ? '' : 's'}</span>`;
        wrap.appendChild(head);
        const list = document.createElement('div');
        list.className = 'fa-tree-children';
        list.style.display = isOpen ? '' : 'none';
        keys.forEach(k => {
            const child = document.createElement('div');
            child.className = 'fa-tree-row';
            const key = document.createElement('span');
            key.className = 'fa-tree-key';
            key.textContent = k;
            child.appendChild(key);
            child.appendChild(buildJsonTreeNode(value[k], path.concat([k]), depth + 1));
            list.appendChild(child);
        });
        wrap.appendChild(list);
        head.addEventListener('click', () => {
            const open = list.style.display !== 'none';
            list.style.display = open ? 'none' : '';
            head.querySelector('.fa-tree-toggle').textContent = open ? '▸' : '▾';
        });
        return wrap;
    }
    wrap.innerHTML = '<span class="fa-tree-val">' + frappe.utils.escape_html(String(value)) + '</span>';
    return wrap;
}

function _treeLeaf(displayText, kind, rawValue, path) {
    const span = document.createElement('span');
    span.className = 'fa-tree-leaf fa-tree-' + kind;
    span.textContent = displayText.length > 80 ? displayText.slice(0, 80) + '…' : displayText;
    span.title = (path.length ? 'Click to copy value' : '') + ' ' + (typeof rawValue === 'string' ? rawValue : '');
    span.addEventListener('click', e => {
        e.stopPropagation();
        const text = typeof rawValue === 'string' ? rawValue : JSON.stringify(rawValue);
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                frappe.show_alert({ message: 'Copied to clipboard', indicator: 'green' }, 2);
            });
        }
    });
    return span;
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
            state.lastPayload = null;  // replay should re-hydrate from trigger_payload
            paintTrace(run);
            switchTab('trace');
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
    let title = '';
    let cls = 'fa-trigger-pill';
    if (!enabled) {
        txt = 'Disabled';
        title = 'Workflow is disabled';
        cls += ' fa-trigger-off';
    } else if (trig.type === 'DocType Event' && trig.doctype && trig.event) {
        // Compact: just the doctype name. Full event detail in tooltip.
        txt = trig.doctype;
        title = `Listening: ${trig.doctype} / ${trig.event}`;
        cls += ' fa-trigger-on';
    } else if (trig.type === 'Schedule' && trig.cron) {
        txt = 'Schedule';
        title = `Schedule: ${trig.cron}`;
        cls += ' fa-trigger-on';
    } else if (trig.type === 'Webhook') {
        txt = 'Webhook';
        title = 'Webhook trigger active';
        cls += ' fa-trigger-on';
    } else if (trig.type === 'Manual') {
        txt = 'Manual';
        title = 'Manual trigger only';
        cls += ' fa-trigger-off';
    } else {
        txt = 'Setup';
        title = 'Trigger configuration incomplete';
        cls += ' fa-trigger-warn';
    }
    el.textContent = txt;
    el.className = cls;
    el.title = title;
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
            renderSparkline(s.last_50 || []);
            renderTopErrors(s.top_errors || []);
            renderAIUsage(s);
        },
    });
}

function renderAIUsage(s) {
    const section = document.getElementById('fa-ai-usage-section');
    if (!section) return;
    if (!s || !s.ai_calls_total) {
        section.style.display = 'none';
        return;
    }
    section.style.display = '';
    document.getElementById('fa-stat-ai-calls').textContent  = s.ai_calls_total || 0;
    document.getElementById('fa-stat-ai-tokens').textContent = formatTokens(s.ai_tokens_total || 0);
    document.getElementById('fa-stat-ai-cost').textContent   = formatCost(s.ai_cost_total || 0);
}

// Render a sparkline of the last 50 runs as colored bars. Bar height
// encodes duration_ms (clamped), colour encodes success/failure.
function renderSparkline(rows) {
    const wrap = document.getElementById('fa-sparkline-wrap');
    if (!wrap) return;
    if (!rows.length) {
        wrap.innerHTML = '<p class="fa-muted" style="padding:14px 0">No runs yet</p>';
        return;
    }
    const maxMs = Math.max(...rows.map(r => r.duration_ms || 0), 100);
    const bars = rows.map(r => {
        const cls = r.status === 'Success' ? 'fa-spark-ok'
                  : r.status === 'Failed' || r.status === 'Timeout' ? 'fa-spark-err'
                  : 'fa-spark-warn';
        const heightPct = Math.max(8, Math.min(100, ((r.duration_ms || 0) / maxMs) * 100));
        return `<div class="fa-spark-bar ${cls}" style="height:${heightPct}%"
                     title="${r.status} · ${r.duration_ms || 0}ms"></div>`;
    }).join('');
    wrap.innerHTML = `<div class="fa-sparkline">${bars}</div>`;
}

function renderTopErrors(errors) {
    const section = document.getElementById('fa-top-errors-section');
    const body = document.getElementById('fa-top-errors');
    if (!section || !body) return;
    if (!errors.length) {
        section.style.display = 'none';
        return;
    }
    section.style.display = '';
    body.innerHTML = errors.map(e => `
        <div class="fa-top-err">
            <span class="fa-top-err-count">${e.count}×</span>
            <span class="fa-top-err-msg">${frappe.utils.escape_html(e.error)}</span>
        </div>
    `).join('');
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
