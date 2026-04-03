# NexusForge Engine v0.1

Generate enterprise automation projects from natural language prompts or YAML manifests.

## Quick Start

```bash
pip install -r requirements.txt

# Generate from a prompt
python cli/new_project.py --prompt "Create a ticket triage system for customer support"

# Generate from a manifest
python cli/new_project.py --manifest manifests/ticket_system.yaml --output ./my-project

# Dry run (preview without writing files)
python cli/new_project.py --prompt "Invoice processing pipeline with OCR" --dry-run

# Skip intent routing with explicit blueprint
python cli/new_project.py --prompt "Support desk" --blueprint ticket_system --output ./support
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `cli/new_project.py` | Generate a new project from prompt or manifest |
| `cli/add_module.py` | Add a module to an existing project |
| `cli/validate_project.py` | Validate project structure and quality |

## Supported Project Types

- **ticket_system** — Ticket triage and customer support automation
- **invoice_processor** — Document/invoice processing pipeline
- **email_responder** — Smart email auto-response system
- **approval_workflow** — Request approval and authorization pipeline
- **report_generator** — Automated report and analytics generator
- **data_sync** — Data synchronization between systems
- **monitoring** — Operations monitoring and alerting
- **agentic_saas** — Full AI agent orchestration SaaS platform

## Available Modules

- **auth** — JWT authentication and authorization
- **billing** — Stripe subscriptions and payments
- **analytics** — Metrics tracking and aggregation
- **ai_chat** — LLM integration (Claude, OpenAI)
- **notifications** — Email, Slack, webhooks
- **connectors** — Gmail, Drive, Notion integrations
- **observability** — Structured logging and tracing
- **admin_panel** — Admin dashboard and settings

## Architecture

```
cli/              CLI entry points
core/             Engine pipeline
  intent_router.py      Classify prompts into project types
  blueprint_selector.py Pick the right project template
  module_composer.py    Assemble required modules
  spec_generator.py     Build the file manifest
  template_engine.py    Render Jinja2 templates
  execution_engine.py   Write files to disk
  quality_gate.py       Validate output
blueprints/       Project blueprint definitions
modules/          Reusable module templates
templates/        Jinja2 templates for scaffolding
manifests/        Example YAML manifests
```

## Adding a Module to Existing Project

```bash
python cli/add_module.py --project ./my-project --module billing
```

## Validating a Project

```bash
python cli/validate_project.py --project ./my-project
```
