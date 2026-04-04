# NexusForge Engine v0.5

Generate enterprise automation projects from natural language prompts or YAML manifests.

## What's New in v0.5

- **Repair Mode** -- Detect and auto-fix common project issues (missing `__init__.py`, broken imports, missing env vars, empty files, SQL syntax validation)
- **Improved add-module CLI** -- Compatibility checks, dependency resolution, `--list`, `--check`, `--dry-run` support
- **Compatibility Matrix** -- Centralized registry of module/blueprint compatibility, conflicts, packages, and env vars
- **Upgrade CLI** -- Compare project files against current engine templates and bump versions
- **Enhanced Quality Gates** -- 12 checks including compatibility matrix, module env vars, module packages, and conflict detection

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
| `cli/repair_project.py` | Detect and fix common project issues |
| `cli/upgrade_project.py` | Upgrade project to newer engine version |

### new_project.py

```bash
python cli/new_project.py --prompt "Create a ticket triage system"
python cli/new_project.py --manifest manifests/ticket_system.yaml --output ./my-project
python cli/new_project.py --prompt "SaaS platform" --blueprint agentic_saas --dry-run
```

| Flag | Description |
|------|-------------|
| `--prompt, -p` | Natural language project description |
| `--manifest, -m` | Path to YAML manifest file |
| `--output, -o` | Output directory (default: `./output`) |
| `--blueprint, -b` | Explicit blueprint name (skips intent routing) |
| `--dry-run` | Preview without writing files |
| `--verbose, -v` | Verbose output |

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

### validate_project.py

```bash
python cli/validate_project.py --project ./my_project
```

Runs 12 quality gate checks:
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

Issues detected:
- Missing `__init__.py` in Python packages
- Missing router imports in `main.py`
- Broken module dependencies
- Missing `.env` variables
- Empty/corrupt files (0 bytes)
- SQL migration syntax errors
- Missing `requirements.txt` entries

### upgrade_project.py

```bash
# Show diff of template changes
python cli/upgrade_project.py --project ./my_project --diff

# Apply version upgrade
python cli/upgrade_project.py --project ./my_project --target-version 0.5
```

| Flag | Description |
|------|-------------|
| `--project, -p` | Path to the project (required) |
| `--target-version, -t` | Target engine version (default: current) |
| `--diff` | Show what would change without applying |

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

## Compatibility Matrix

The compatibility matrix (`core/compatibility.py`) defines for each module:

- **compatible_blueprints** -- Which blueprints the module works with
- **requires** -- Other modules that must be installed first
- **conflicts_with** -- Modules that cannot coexist
- **python_packages** -- PyPI packages needed by the module
- **env_vars** -- Environment variables the module expects

The matrix is validated automatically by the quality gate, add-module CLI, and repair engine.

## Example Workflows

### 1. Generate a new project

```bash
python cli/new_project.py --prompt "Build a ticket triage system with analytics" --output ./my-tickets
cd my-tickets
pip install -r requirements.txt
```

### 2. Add a module to an existing project

```bash
# Check compatibility first
python cli/add_module.py --project ./my-tickets --check billing

# Add the module
python cli/add_module.py --project ./my-tickets --module billing
```

### 3. Repair a broken project

```bash
# See what's wrong
python cli/repair_project.py --project ./my-tickets

# Fix everything automatically
python cli/repair_project.py --project ./my-tickets --fix
```

### 4. Upgrade after engine update

```bash
# See what changed in templates
python cli/upgrade_project.py --project ./my-tickets --diff

# Apply version bump
python cli/upgrade_project.py --project ./my-tickets --target-version 0.5
```

## Architecture

```
cli/              CLI entry points
  new_project.py        Generate a new project
  add_module.py         Add module with compatibility checks
  validate_project.py   Run quality gate checks
  repair_project.py     Detect and fix project issues
  upgrade_project.py    Upgrade project to newer version
core/             Engine pipeline
  intent_router.py      Classify prompts into project types
  blueprint_selector.py Pick the right project template
  module_composer.py    Assemble required modules
  spec_generator.py     Build the file manifest
  template_engine.py    Render Jinja2 templates
  execution_engine.py   Write files to disk
  quality_gate.py       Validate output (12 checks)
  compatibility.py      Module/blueprint compatibility matrix
  repair_engine.py      Project repair scanner and fixer
blueprints/       Project blueprint definitions
modules/          Reusable module templates
templates/        Jinja2 templates for scaffolding
manifests/        Example YAML manifests
agents/           Agent definitions (YAML)
validators/       Validation rules
tests/            Test suite
```

## Version History

| Version | Features |
|---------|----------|
| v0.1 | Initial release: intent routing, blueprint selection, module composition, template rendering, quality gates |
| v0.3 | DB persistence, `/analyze` endpoint, email integration, Drive integration |
| v0.5 | Repair mode, improved add-module CLI, compatibility matrix, upgrade CLI, enhanced quality gates (12 checks) |
