"""Compatibility Matrix -- Defines module/blueprint compatibility rules.

Provides a centralized registry of which modules work with which blueprints,
their inter-module dependencies, conflicts, required Python packages, and
environment variables. Used by the add-module CLI, repair engine, and
quality gate to validate project compositions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Compatibility Matrix -- one entry per module
# ---------------------------------------------------------------------------

COMPATIBILITY_MATRIX: dict[str, dict[str, Any]] = {
    "auth": {
        "compatible_blueprints": ["ticket_system", "invoice_processor", "agentic_saas"],
        "requires": [],
        "conflicts_with": [],
        "python_packages": ["bcrypt>=4.1", "python-jose>=3.3", "passlib>=1.7"],
        "env_vars": ["SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES", "REFRESH_TOKEN_EXPIRE_DAYS"],
    },
    "billing": {
        "compatible_blueprints": ["agentic_saas", "invoice_processor"],
        "requires": ["auth"],
        "conflicts_with": [],
        "python_packages": ["stripe>=8.0"],
        "env_vars": ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_PRO", "STRIPE_PRICE_ENTERPRISE"],
    },
    "analytics": {
        "compatible_blueprints": ["ticket_system", "invoice_processor", "agentic_saas"],
        "requires": ["auth"],
        "conflicts_with": [],
        "python_packages": [],
        "env_vars": ["ANALYTICS_RETENTION_DAYS"],
    },
    "ai_chat": {
        "compatible_blueprints": ["agentic_saas"],
        "requires": ["auth"],
        "conflicts_with": [],
        "python_packages": ["anthropic>=0.39"],
        "env_vars": ["ANTHROPIC_API_KEY", "AI_MODEL", "AI_MAX_TOKENS"],
    },
    "notifications": {
        "compatible_blueprints": ["ticket_system", "invoice_processor", "agentic_saas"],
        "requires": ["auth"],
        "conflicts_with": [],
        "python_packages": ["aiosmtplib>=3.0"],
        "env_vars": ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"],
    },
    "connectors": {
        "compatible_blueprints": ["ticket_system", "invoice_processor", "agentic_saas"],
        "requires": ["auth"],
        "conflicts_with": [],
        "python_packages": [
            "slack-sdk>=3.27",
            "google-api-python-client>=2.0",
            "notion-client>=2.2",
        ],
        "env_vars": [
            "SLACK_BOT_TOKEN",
            "SLACK_SIGNING_SECRET",
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            "NOTION_API_KEY",
            "JIRA_URL",
            "JIRA_API_TOKEN",
        ],
    },
    "observability": {
        "compatible_blueprints": ["ticket_system", "invoice_processor", "agentic_saas"],
        "requires": [],
        "conflicts_with": [],
        "python_packages": ["structlog>=24.0"],
        "env_vars": ["LOG_LEVEL", "LOG_FORMAT", "SENTRY_DSN"],
    },
    "admin_panel": {
        "compatible_blueprints": ["ticket_system", "invoice_processor", "agentic_saas"],
        "requires": ["auth", "observability"],
        "conflicts_with": [],
        "python_packages": [],
        "env_vars": ["ADMIN_EMAIL"],
    },
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class CompatibilityResult:
    """Result of a compatibility check.

    Attributes:
        compatible: True if the full composition is valid.
        issues: Human-readable list of compatibility problems.
        missing_deps: Module IDs that are required but not present.
        conflicts: Pairs of module IDs that conflict with each other.
        env_vars_needed: Complete list of env vars required by all modules.
        packages_needed: Complete list of Python packages required by all modules.
    """

    compatible: bool = True
    issues: list[str] = field(default_factory=list)
    missing_deps: list[str] = field(default_factory=list)
    conflicts: list[tuple[str, str]] = field(default_factory=list)
    env_vars_needed: list[str] = field(default_factory=list)
    packages_needed: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_compatibility(
    blueprint_id: str,
    modules: list[str],
) -> CompatibilityResult:
    """Validate a full composition of blueprint + modules.

    Checks that every requested module is compatible with the given blueprint,
    that all inter-module dependencies are satisfied, and that no conflicting
    modules are present.

    Args:
        blueprint_id: The blueprint ID (e.g. ``"agentic_saas"``).
        modules: List of module IDs to include.

    Returns:
        A :class:`CompatibilityResult` with all findings.
    """
    result = CompatibilityResult()

    for mod_id in modules:
        entry = COMPATIBILITY_MATRIX.get(mod_id)
        if entry is None:
            result.compatible = False
            result.issues.append(f"Unknown module: '{mod_id}'")
            continue

        # Blueprint compatibility
        if blueprint_id not in entry["compatible_blueprints"]:
            result.compatible = False
            result.issues.append(
                f"Module '{mod_id}' is not compatible with blueprint '{blueprint_id}'"
            )

    # Dependencies
    result.missing_deps = get_missing_dependencies(modules)
    if result.missing_deps:
        result.compatible = False
        for dep in result.missing_deps:
            result.issues.append(f"Missing dependency: '{dep}'")

    # Conflicts
    result.conflicts = get_conflicts(modules)
    if result.conflicts:
        result.compatible = False
        for a, b in result.conflicts:
            result.issues.append(f"Module conflict: '{a}' conflicts with '{b}'")

    # Aggregated env vars and packages
    result.env_vars_needed = get_all_env_vars(modules)
    result.packages_needed = get_all_packages(modules)

    return result


def get_missing_dependencies(modules: list[str]) -> list[str]:
    """Return module IDs that are required but not present in *modules*.

    Args:
        modules: List of module IDs in the composition.

    Returns:
        Sorted list of missing dependency IDs.
    """
    present = set(modules)
    missing: set[str] = set()

    for mod_id in modules:
        entry = COMPATIBILITY_MATRIX.get(mod_id)
        if entry is None:
            continue
        for dep in entry["requires"]:
            if dep not in present:
                missing.add(dep)

    return sorted(missing)


def get_conflicts(modules: list[str]) -> list[tuple[str, str]]:
    """Return pairs of module IDs that conflict with each other.

    Args:
        modules: List of module IDs in the composition.

    Returns:
        List of ``(module_a, module_b)`` tuples representing conflicts.
    """
    present = set(modules)
    conflicts: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for mod_id in modules:
        entry = COMPATIBILITY_MATRIX.get(mod_id)
        if entry is None:
            continue
        for conflict_id in entry["conflicts_with"]:
            if conflict_id in present:
                pair = tuple(sorted([mod_id, conflict_id]))
                if pair not in seen:
                    seen.add(pair)
                    conflicts.append(pair)

    return conflicts


def get_all_env_vars(modules: list[str]) -> list[str]:
    """Collect every environment variable required by the given modules.

    Args:
        modules: List of module IDs.

    Returns:
        Deduplicated, sorted list of env var names.
    """
    env_vars: set[str] = set()

    for mod_id in modules:
        entry = COMPATIBILITY_MATRIX.get(mod_id)
        if entry is None:
            continue
        for var in entry["env_vars"]:
            env_vars.add(var)

    return sorted(env_vars)


def get_all_packages(modules: list[str]) -> list[str]:
    """Collect every Python package required by the given modules.

    Args:
        modules: List of module IDs.

    Returns:
        Deduplicated, sorted list of package specifiers.
    """
    packages: set[str] = set()

    for mod_id in modules:
        entry = COMPATIBILITY_MATRIX.get(mod_id)
        if entry is None:
            continue
        for pkg in entry["python_packages"]:
            packages.add(pkg)

    return sorted(packages)


def get_module_info(module_id: str) -> dict[str, Any] | None:
    """Return the compatibility entry for a single module.

    Args:
        module_id: The module ID (e.g. ``"auth"``).

    Returns:
        The entry dict or ``None`` if the module is unknown.
    """
    return COMPATIBILITY_MATRIX.get(module_id)
