# Installation

FlowAgent installs like any Frappe app via the bench CLI.

## Requirements

- Frappe v15.x
- Python 3.10+
- An Anthropic API key (for AI nodes — you can install the app without one and add it later)

## Steps

From your bench directory:

```bash
cd ~/frappe-bench
bench get-app https://github.com/MirzaAreebBaig/Frappe-FlowAgent
bench --site <yoursite> install-app flowagent
bench --site <yoursite> migrate
bench restart
```

The `bench restart` is required: the wildcard `doc_events` hook only loads after worker restart.

## Frappe Cloud

If you're installing via Frappe Cloud, attach the app to your bench through the dashboard and trigger a deploy. Migrate runs automatically after deploy.

## Post-install

1. Open **FlowAgent Settings** in your desk
2. Paste your Anthropic API key
3. Navigate to **FlowAgent → Open Studio** from the sidebar
4. Click **Templates** to start from a ready-made workflow, or **AI Build** to describe one in natural language

## Verifying the install

After install, the FlowAgent workspace should appear in the desk sidebar with:
- 4 number cards across the top
- 3 charts (Daily Runs, AI Cost Trend, Top Workflows)
- Quick-access shortcuts to Studio / Workflows / Runs
- Sidebar links to all 5 reports

If number cards or charts don't render, see the [troubleshooting section](#troubleshooting).

## Troubleshooting

**"Workflow doesn't fire after enabling"**
Click the stethoscope icon in the Studio toolbar. It reports what's wrong (missing API key, trigger not bound, doctype not found, etc.) in plain English.

**"Workspace cards/charts are empty"**
Run `bench --site <yoursite> migrate` again. The install hook idempotently rebuilds dashboard records. If still empty, check the Error Log doctype for entries titled `FlowAgent: ...`.

**"After upgrading, old workflows aren't firing on save"**
The v0.4.1 release fixes a latent bug where `after_save` (an invalid hook name) was used instead of `on_update`. Run migrate — it auto-rebuilds all trigger indexes.

## Uninstall

```bash
bench --site <yoursite> uninstall-app flowagent
```

This removes all FlowAgent doctypes and their data. The workspace, reports, charts, and number cards go with the app.
