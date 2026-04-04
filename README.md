# NexusForge Engine v1.0

Generate enterprise automation projects from natural language prompts or YAML manifests.

## What's New in v1.0

- **Intelligent Intent Router** -- Weighted TF-IDF scoring, multi-intent detection, confidence scores, context-aware routing from user history, and structured requirement extraction (data sources, outputs, industry, scale, compliance)
- **Multi-Stack Support** -- Generate projects in `python-fastapi` (full templates), `python-flask` (skeleton), or `node-express` (skeleton) via `--stack` flag
- **Generation Telemetry** -- Track what gets generated, timing, quality gate pass rates, and failure patterns. View with `cli/stats.py`
- **Project Memory** -- Persistent memory across sessions: learned module preferences, repair pattern warnings, project history. Stored in `~/.nexusforge/memory.json`
- **Enhanced Quality Gates** -- 16 checks including Python syntax validation, import resolution, circular dependency detection, and test file coverage
- **Interactive Mode** -- Step-by-step guided creation with `--interactive`
- **Module Suggestions** -- `--suggest` shows recommended modules based on your history

## Quick Start

```bash
pip install -r requirements.txt

# Generate from a prompt
python cli/new_project.py --prompt "Create a ticket triage system for customer support"

# Interactive guided creation
python cli/new_project.py --interactive

# Generate with a specific stack
python cli/new_project.py --prompt "Invoice processor" --stack python-flask

# Show module suggestions from history
python cli/new_project.py --prompt "SaaS platform" --suggest

# Generate from a manifest
python cli/new_project.py --manifest manifests/ticket_system.yaml --output ./my-project

# Dry run (preview without writing files)
python cli/new_project.py --prompt "Invoice processing pipeline with OCR" --dry-run

# Disable telemetry
python cli/new_project.py --prompt "Support desk" --no-telemetry
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `cli/new_project.py` | Generate a new project from prompt or manifest |
| `cli/add_module.py` | Add a module to an existing project |
| `cli/validate_project.py` | Validate project structure and quality |
| `cli/repair_project.py` | Detect and fix common project issues |
| `cli/upgrade_project.py` | Upgrade project to newer engine version |
| `cli/stats.py` | View generation telemetry and statistics |

### new_project.py

```bash
python cli/new_project.py --prompt "Create a ticket triage system"
python cli/new_project.py --prompt "SaaS platform" --stack node-express
python cli/new_project.py --interactive
python cli/new_project.py --prompt "Monitor system" --suggest --no-telemetry
python cli/new_project.py --manifest manifests/ticket_system.yaml --output ./my-project
python cli/new_project.py --prompt "SaaS platform" --blueprint agentic_saas --dry-run
```

| Flag | Description |
|------|-------------|
| `--prompt, -p` | Natural language project description |
| `--manifest, -m` | Path to YAML manifest file |
| `--output, -o` | Output directory (default: `./output`) |
| `--blueprint, -b` | Explicit blueprint name (skips intent routing) |
| `--stack` | Technology stack: `python-fastapi`, `python-flask`, `node-express` |
| `--dry-run` | Preview without writing files |
| `--verbose, -v` | Verbose output |
| `--no-telemetry` | Disable telemetry and project memory recording |
| `--suggest` | Show module suggestions based on history |
| `--interactive` | Step-by-step guided creation mode |

### add_module.py

```bash
python cli/add_module.py --project ./my_project --module billing
python cli/add_module.py --project ./my_project --module billing --dry-run
python cli/add_module.py --project ./my_project --list
python cli/add_module.py --project ./my_project --check billing
```

| Flag | Description |
|------|-------------|
| `--project, -p` | Path to the project (required) |
| `--module, -m` | Module ID to add |
| `--list` | List all available modules and their status |
| `--check MODULE` | Check compatibility without installing |
| `--dry-run` | Preview what would change |
| `--no-telemetry` | Disable telemetry recording |

### validate_project.py

```bash
python cli/validate_project.py --project ./my_project
```

Runs 16 quality gate checks:
1. Required directories exist
2. Required files exist
3. `.env.example` covers required env vars
4. `requirements.txt` is valid
5. No empty files
6. No duplicate file paths
7. Module dependencies satisfied
8. Manifest is valid YAML
9. Compatibility matrix passes
10. All module env vars in `.env.example`
11. All module packages in `requirements.txt`
12. No module conflicts
13. Python syntax validation
14. Import resolution
15. Circular dependency detection
16. Test file coverage

### repair_project.py

```bash
# Report only (default)
python cli/repair_project.py --project ./my_project

# Auto-fix all fixable issues
python cli/repair_project.py --project ./my_project --fix

# Dry-run: show what would be fixed without writing
python cli/repair_project.py --project ./my_project --fix --dry-run
```

| Flag | Description |
|------|-------------|
| `--project, -p` | Path to the project (required) |
| `--fix` | Auto-fix all fixable issues |
| `--dry-run` | Show what would be fixed (requires `--fix`) |
| `--no-telemetry` | Disable telemetry recording |

### stats.py

```bash
python cli/stats.py                    # show generation stats
python cli/stats.py --history          # show last 20 generations
python cli/stats.py --modules          # most used modules
python cli/stats.py --failures         # common failure patterns
python cli/stats.py --memory           # project memory summary
python cli/stats.py --all              # show everything
```

| Flag | Description |
|------|-------------|
| `--history` | Show last 20 generation events |
| `--modules` | Show most used modules |
| `--failures` | Show common failure patterns |
| `--memory` | Show project memory summary |
| `--all` | Show all telemetry data |
| `--limit N` | Number of history entries (default: 20) |

## Supported Technology Stacks

| Stack | Language | Framework | DB Driver | Templates |
|-------|----------|-----------|-----------|-----------|
| `python-fastapi` | Python | FastAPI | asyncpg | Full |
| `python-flask` | Python | Flask | SQLAlchemy | Skeleton |
| `node-express` | JavaScript | Express.js | Prisma | Skeleton |

**Full templates** include complete module implementations for all 8 modules.
**Skeleton templates** include the main entry point, config, README, and package file with TODO markers for module implementation.

## Supported Blueprints

| Blueprint | Description |
|-----------|-------------|
| `ticket_system` | Ticket triage and customer support automation |
| `invoice_processor` | Document/invoice processing pipeline |
| `agentic_saas` | Full AI agent orchestration SaaS platform |

## Available Modules

| Module | Requires | Compatible Blueprints |
|--------|----------|-----------------------|
| `auth` | -- | ticket_system, invoice_processor, agentic_saas |
| `billing` | auth | agentic_saas, invoice_processor |
| `analytics` | auth | ticket_system, invoice_processor, agentic_saas |
| `ai_chat` | auth | agentic_saas |
| `notifications` | auth | ticket_system, invoice_processor, agentic_saas |
| `connectors` | auth | ticket_system, invoice_processor, agentic_saas |
| `observability` | -- | ticket_system, invoice_processor, agentic_saas |
| `admin_panel` | auth, observability | ticket_system, invoice_processor, agentic_saas |

## Intent Router v1.0

The v1.0 router replaces simple keyword counting with:

- **Weighted TF-IDF scoring** -- Keywords have explicit weights, and IDF penalizes common keywords
- **Multi-intent detection** -- "ticket system with invoice processing" detects both types
- **Confidence score** -- 0.0-1.0; if < 0.5, the engine warns and suggests `--interactive`
- **Context-aware routing** -- Reads `~/.nexusforge/history.json` to suggest modules
- **Prompt enhancement** -- Extracts structured requirements:
  - Data sources (email, files, API, webhook, database, queue)
  - Output destinations (email, Slack, Notion, dashboard, webhook, PDF)
  - Industry (finance, healthcare, technology, legal, retail, education)
  - Scale (solo dev, small team, enterprise)
  - Compliance (GDPR, HIPAA, SOC2, PCI-DSS)

## Telemetry and Privacy

Telemetry data is stored locally in `~/.nexusforge/telemetry.json`. It records:
- Event type, project type, stack, modules
- File counts, duration, quality gate results
- Error messages (no sensitive content)

**What is never recorded:**
- API keys, secrets, or credentials
- File contents or source code
- Personal data

Telemetry is opt-out: pass `--no-telemetry` to any CLI command.

## Project Memory

Project memory (`~/.nexusforge/memory.json`) learns from your usage:
- Which modules you always pick for each project type
- Which repairs are common (warns during generation)
- Your preferred stack and naming conventions

## Compatibility Matrix

The compatibility matrix (`core/compatibility.py`) defines for each module:

- **compatible_blueprints** -- Which blueprints the module works with
- **requires** -- Other modules that must be installed first
- **conflicts_with** -- Modules that cannot coexist
- **python_packages** -- PyPI packages needed by the module
- **env_vars** -- Environment variables the module expects

## Architecture

```
cli/                   CLI entry points
  new_project.py             Generate a new project (v1.0: multi-stack, interactive)
  add_module.py              Add module with compatibility checks + telemetry
  validate_project.py        Run quality gate checks (16 total)
  repair_project.py          Detect and fix project issues + learn patterns
  upgrade_project.py         Upgrade project to newer version
  stats.py                   View generation telemetry and statistics
core/                  Engine pipeline
  intent_router.py           Intelligent intent classification (TF-IDF, multi-intent)
  blueprint_selector.py      Pick the right project template
  module_composer.py         Assemble required modules
  spec_generator.py          Build the file manifest
  template_engine.py         Render Jinja2 templates
  execution_engine.py        Write files to disk
  quality_gate.py            Validate output (16 checks)
  compatibility.py           Module/blueprint compatibility matrix
  repair_engine.py           Project repair scanner and fixer
  stack_manager.py           Multi-stack support (FastAPI, Flask, Express)
  telemetry.py               Generation event tracking and statistics
  project_memory.py          Persistent memory and learned preferences
blueprints/            Project blueprint definitions
modules/               Reusable module templates
templates/             Jinja2 templates for scaffolding
manifests/             Example YAML manifests
agents/                Agent definitions (YAML)
validators/            Validation rules
tests/                 Test suite
```

## Example Workflows

### 1. Interactive project creation

```bash
python cli/new_project.py --interactive
```

The guided flow walks you through:
1. Describe your project
2. Review detected intent and confidence
3. Accept or modify suggested modules
4. Choose technology stack
5. Confirm and generate

### 2. Generate with a non-default stack

```bash
python cli/new_project.py --prompt "Invoice processor" --stack python-flask --output ./invoices
cd invoices
pip install -r requirements.txt
flask run
```

### 3. Check your generation history

```bash
python cli/stats.py --all
```

### 4. Add a module to an existing project

```bash
python cli/add_module.py --project ./my-tickets --check billing
python cli/add_module.py --project ./my-tickets --module billing
```

### 5. Repair a broken project

```bash
python cli/repair_project.py --project ./my-tickets
python cli/repair_project.py --project ./my-tickets --fix
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Follow the coding standards:
   - Every function must have docstrings and type hints
   - Telemetry data must never include sensitive information
   - Quality gates must not crash on invalid files -- catch errors gracefully
   - Spanish for UI/comments, English for code (variables, functions)
4. Run tests: `pytest`
5. Submit a pull request

## Version History

| Version | Features |
|---------|----------|
| v0.1 | Initial release: intent routing, blueprint selection, module composition, template rendering, quality gates |
| v0.3 | DB persistence, `/analyze` endpoint, email integration, Drive integration |
| v0.5 | Repair mode, improved add-module CLI, compatibility matrix, upgrade CLI, enhanced quality gates (12 checks) |
| v1.0 | Intelligent intent router (TF-IDF, multi-intent, confidence), multi-stack support (FastAPI/Flask/Express), generation telemetry, project memory, 16 quality gates, interactive mode, module suggestions |
