"""Stack Manager v1.0 — Multi-stack support for project generation.

Defines available technology stacks and provides helpers to retrieve
stack configuration, validate stack choices, and generate skeleton
templates for each supported stack.

Supported stacks in v1.0:
- ``python-fastapi`` (full templates — default)
- ``python-flask`` (skeleton templates)
- ``node-express`` (skeleton templates)
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Stack definitions
# ---------------------------------------------------------------------------

STACKS: dict[str, dict[str, Any]] = {
    "python-fastapi": {
        "language": "python",
        "framework": "fastapi",
        "db_driver": "asyncpg",
        "package_manager": "pip",
        "package_file": "requirements.txt",
        "run_command": "uvicorn main:app --reload",
        "test_command": "pytest",
        "docker_base": "python:3.12-slim",
        "full_templates": True,
    },
    "python-flask": {
        "language": "python",
        "framework": "flask",
        "db_driver": "sqlalchemy",
        "package_manager": "pip",
        "package_file": "requirements.txt",
        "run_command": "flask run",
        "test_command": "pytest",
        "docker_base": "python:3.12-slim",
        "full_templates": False,
    },
    "node-express": {
        "language": "javascript",
        "framework": "express",
        "db_driver": "prisma",
        "package_manager": "npm",
        "package_file": "package.json",
        "run_command": "npm run dev",
        "test_command": "npm test",
        "docker_base": "node:20-slim",
        "full_templates": False,
    },
}

DEFAULT_STACK = "python-fastapi"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_stack(stack_id: str) -> dict[str, Any]:
    """Retrieve a stack configuration by ID.

    Args:
        stack_id: One of the keys in :data:`STACKS`.

    Returns:
        Stack configuration dictionary.

    Raises:
        ValueError: If the stack ID is not recognized.
    """
    if stack_id not in STACKS:
        available = ", ".join(sorted(STACKS.keys()))
        raise ValueError(
            f"Unknown stack '{stack_id}'. Available stacks: {available}"
        )
    return dict(STACKS[stack_id])


def list_stacks() -> list[dict[str, Any]]:
    """Return a list of all available stacks with their metadata.

    Returns:
        List of dicts with ``id`` plus all stack fields.
    """
    result: list[dict[str, Any]] = []
    for stack_id, config in STACKS.items():
        entry = {"id": stack_id}
        entry.update(config)
        result.append(entry)
    return result


def validate_stack(stack_id: str) -> bool:
    """Check whether a stack ID is valid.

    Args:
        stack_id: The stack identifier to validate.

    Returns:
        True if valid, False otherwise.
    """
    return stack_id in STACKS


def has_full_templates(stack_id: str) -> bool:
    """Check whether a stack has full (non-skeleton) templates.

    Args:
        stack_id: The stack identifier.

    Returns:
        True if the stack has complete module templates.
    """
    stack = STACKS.get(stack_id, {})
    return stack.get("full_templates", False)


# ---------------------------------------------------------------------------
# Skeleton template generators
# ---------------------------------------------------------------------------

def generate_flask_skeleton(project_name: str, description: str) -> list[dict[str, str]]:
    """Generate minimal Flask project skeleton files.

    Args:
        project_name: The project name for configuration.
        description: Project description for README.

    Returns:
        List of ``{path, content}`` dicts ready for the execution engine.
    """
    files: list[dict[str, str]] = []

    # app.py — main entry point
    files.append({
        "path": "app.py",
        "content": (
            '"""Flask application entry point."""\n'
            "\n"
            "from flask import Flask, jsonify\n"
            "\n"
            "from config import Config\n"
            "\n"
            "\n"
            "def create_app(config_class: type = Config) -> Flask:\n"
            '    """Application factory.\n'
            "\n"
            "    Args:\n"
            "        config_class: Configuration class to use.\n"
            "\n"
            "    Returns:\n"
            "        Configured Flask application instance.\n"
            '    """\n'
            "    app = Flask(__name__)\n"
            "    app.config.from_object(config_class)\n"
            "\n"
            "    # TODO: Register blueprints for each module\n"
            "    # from src.auth.routes import auth_bp\n"
            "    # app.register_blueprint(auth_bp, url_prefix='/api/auth')\n"
            "\n"
            '    @app.route("/health")\n'
            "    def health() -> dict:\n"
            '        """Health check endpoint."""\n'
            '        return jsonify({"status": "healthy", "framework": "flask"})\n'
            "\n"
            "    return app\n"
            "\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    application = create_app()\n"
            "    application.run(debug=True)\n"
        ),
    })

    # config.py
    files.append({
        "path": "config.py",
        "content": (
            '"""Flask application configuration."""\n'
            "\n"
            "import os\n"
            "\n"
            "\n"
            "class Config:\n"
            '    """Base configuration.\n'
            "\n"
            "    Attributes:\n"
            "        SECRET_KEY: Application secret key.\n"
            "        SQLALCHEMY_DATABASE_URI: Database connection string.\n"
            "        SQLALCHEMY_TRACK_MODIFICATIONS: Disable modification tracking.\n"
            '    """\n'
            "\n"
            '    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-in-production")\n'
            "    SQLALCHEMY_DATABASE_URI: str = os.environ.get(\n"
            '        "DATABASE_URL", "sqlite:///app.db"\n'
            "    )\n"
            "    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False\n"
        ),
    })

    # requirements.txt
    files.append({
        "path": "requirements.txt",
        "content": (
            "flask>=3.0\n"
            "flask-sqlalchemy>=3.1\n"
            "flask-migrate>=4.0\n"
            "python-dotenv>=1.0\n"
            "gunicorn>=22.0\n"
        ),
    })

    # README.md
    files.append({
        "path": "README.md",
        "content": (
            f"# {project_name}\n"
            "\n"
            f"{description}\n"
            "\n"
            "## Stack\n"
            "\n"
            "- **Framework:** Flask\n"
            "- **Database:** SQLAlchemy + SQLite (dev) / PostgreSQL (prod)\n"
            "- **Language:** Python 3.12+\n"
            "\n"
            "## Quick Start\n"
            "\n"
            "```bash\n"
            "pip install -r requirements.txt\n"
            "flask run\n"
            "```\n"
            "\n"
            "## TODO\n"
            "\n"
            "- [ ] Implement module blueprints\n"
            "- [ ] Add database migrations\n"
            "- [ ] Configure authentication\n"
            "- [ ] Add tests\n"
        ),
    })

    return files


def generate_express_skeleton(project_name: str, description: str) -> list[dict[str, str]]:
    """Generate minimal Express.js project skeleton files.

    Args:
        project_name: The project name for package.json.
        description: Project description.

    Returns:
        List of ``{path, content}`` dicts ready for the execution engine.
    """
    files: list[dict[str, str]] = []

    # Convert project name to valid npm package name
    npm_name = project_name.lower().replace(" ", "-").replace("_", "-")

    # package.json
    files.append({
        "path": "package.json",
        "content": (
            "{\n"
            f'  "name": "{npm_name}",\n'
            '  "version": "1.0.0",\n'
            f'  "description": "{description}",\n'
            '  "main": "src/index.js",\n'
            '  "scripts": {\n'
            '    "start": "node src/index.js",\n'
            '    "dev": "nodemon src/index.js",\n'
            '    "test": "jest"\n'
            "  },\n"
            '  "dependencies": {\n'
            '    "express": "^4.18.0",\n'
            '    "cors": "^2.8.0",\n'
            '    "dotenv": "^16.0.0",\n'
            '    "@prisma/client": "^5.0.0"\n'
            "  },\n"
            '  "devDependencies": {\n'
            '    "nodemon": "^3.0.0",\n'
            '    "jest": "^29.0.0",\n'
            '    "prisma": "^5.0.0"\n'
            "  }\n"
            "}\n"
        ),
    })

    # src/index.js
    files.append({
        "path": "src/index.js",
        "content": (
            '/** Express.js application entry point. */\n'
            "\n"
            "const express = require('express');\n"
            "const cors = require('cors');\n"
            "require('dotenv').config();\n"
            "\n"
            "const app = express();\n"
            f"const PORT = process.env.PORT || 3000;\n"
            "\n"
            "// Middleware\n"
            "app.use(cors());\n"
            "app.use(express.json());\n"
            "\n"
            "// TODO: Register route modules\n"
            "// const authRoutes = require('./routes/auth');\n"
            "// app.use('/api/auth', authRoutes);\n"
            "\n"
            "// Health check\n"
            "app.get('/health', (req, res) => {\n"
            "  res.json({ status: 'healthy', framework: 'express' });\n"
            "});\n"
            "\n"
            "app.listen(PORT, () => {\n"
            "  console.log(`Server running on port ${PORT}`);\n"
            "});\n"
            "\n"
            "module.exports = app;\n"
        ),
    })

    # src/config.js
    files.append({
        "path": "src/config.js",
        "content": (
            "/** Application configuration. */\n"
            "\n"
            "require('dotenv').config();\n"
            "\n"
            "module.exports = {\n"
            "  port: parseInt(process.env.PORT, 10) || 3000,\n"
            "  databaseUrl: process.env.DATABASE_URL || 'file:./dev.db',\n"
            "  jwtSecret: process.env.JWT_SECRET || 'change-me-in-production',\n"
            "  nodeEnv: process.env.NODE_ENV || 'development',\n"
            "};\n"
        ),
    })

    # README.md
    files.append({
        "path": "README.md",
        "content": (
            f"# {project_name}\n"
            "\n"
            f"{description}\n"
            "\n"
            "## Stack\n"
            "\n"
            "- **Framework:** Express.js\n"
            "- **Database:** Prisma + SQLite (dev) / PostgreSQL (prod)\n"
            "- **Language:** JavaScript (Node.js 20+)\n"
            "\n"
            "## Quick Start\n"
            "\n"
            "```bash\n"
            "npm install\n"
            "npx prisma generate\n"
            "npm run dev\n"
            "```\n"
            "\n"
            "## TODO\n"
            "\n"
            "- [ ] Define Prisma schema\n"
            "- [ ] Implement route modules\n"
            "- [ ] Configure authentication middleware\n"
            "- [ ] Add tests\n"
        ),
    })

    return files


def get_skeleton_files(
    stack_id: str,
    project_name: str,
    description: str,
) -> list[dict[str, str]]:
    """Generate skeleton template files for stacks without full templates.

    Args:
        stack_id: The stack identifier.
        project_name: Project name for configuration files.
        description: Project description.

    Returns:
        List of ``{path, content}`` file dicts, or empty list if the
        stack has full templates (no skeleton needed).
    """
    if has_full_templates(stack_id):
        return []

    generators = {
        "python-flask": generate_flask_skeleton,
        "node-express": generate_express_skeleton,
    }

    generator = generators.get(stack_id)
    if generator is None:
        return []

    return generator(project_name, description)
