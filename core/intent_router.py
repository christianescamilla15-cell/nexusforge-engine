"""Intent Router v1.0 — Intelligent intent classification with scoring,
multi-intent detection, confidence, context-aware routing, and prompt enhancement.

Replaces the v0.5 keyword-counting approach with a weighted TF-IDF-like
scoring system that returns richer metadata including confidence scores,
alternative types, extracted data sources, outputs, industry, scale, and
compliance requirements.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any


# ---------------------------------------------------------------------------
# Keyword registry — each keyword carries an explicit weight
# ---------------------------------------------------------------------------

INTENT_PATTERNS: dict[str, dict[str, Any]] = {
    "ticket_system": {
        "keywords": {
            "ticket": 3.0, "soporte": 2.5, "support": 2.5, "triage": 3.0,
            "helpdesk": 3.0, "mesa de ayuda": 3.0, "clasificar tickets": 3.5,
            "customer service": 2.5, "incidencias": 2.5, "issue tracker": 3.0,
            "bug tracking": 2.5, "service desk": 3.0,
        },
        "description": "Ticket triage and customer support automation",
    },
    "invoice_processor": {
        "keywords": {
            "factura": 3.0, "invoice": 3.0, "pdf": 1.5, "ocr": 2.5,
            "extraccion": 2.5, "extraction": 2.5, "datos de factura": 3.5,
            "procesamiento de facturas": 3.5, "billing": 2.0,
            "receipt": 2.0, "accounts payable": 2.5,
        },
        "description": "Document/invoice processing pipeline",
    },
    "email_responder": {
        "keywords": {
            "email": 2.5, "correo": 2.5, "auto-responder": 3.0,
            "respuesta automatica": 3.0, "inbox": 2.0,
            "bandeja de entrada": 2.5, "reply": 1.5, "auto-reply": 3.0,
            "email automation": 3.0,
        },
        "description": "Smart email auto-response system",
    },
    "approval_workflow": {
        "keywords": {
            "aprobacion": 3.0, "approval": 3.0, "solicitud": 2.0,
            "request": 1.5, "autorizacion": 2.5, "authorization": 2.5,
            "vacaciones": 2.0, "compras": 1.5, "gastos": 2.0,
            "expenses": 2.0, "reembolso": 2.0, "workflow": 2.0,
        },
        "description": "Request approval and authorization pipeline",
    },
    "report_generator": {
        "keywords": {
            "reporte": 3.0, "report": 2.5, "resumen": 2.0, "summary": 2.0,
            "kpi": 2.5, "dashboard": 2.0, "metricas": 2.5,
            "analytics": 2.0, "ejecutivo": 2.0, "executive": 2.0,
            "charts": 1.5, "visualization": 1.5,
        },
        "description": "Automated report and analytics generator",
    },
    "data_sync": {
        "keywords": {
            "sincronizar": 3.0, "sync": 2.5, "migrar": 2.5, "migrate": 2.5,
            "crm": 2.0, "erp": 2.0, "integrar sistemas": 3.0,
            "data pipeline": 3.0, "etl": 3.0, "data warehouse": 2.5,
        },
        "description": "Data synchronization between systems",
    },
    "monitoring": {
        "keywords": {
            "monitoreo": 3.0, "monitoring": 3.0, "alertas": 2.5,
            "alerts": 2.5, "sla": 2.5, "uptime": 2.5,
            "anomalias": 2.5, "anomaly": 2.5, "vigilar": 2.0,
            "health check": 2.0, "observability": 2.0,
        },
        "description": "Operations monitoring and alerting",
    },
    "agentic_saas": {
        "keywords": {
            "saas": 3.0, "plataforma": 2.0, "platform": 2.0,
            "multi-agent": 3.0, "orquestacion": 3.0, "orchestration": 3.0,
            "nexusforge": 3.5, "agentes ia": 3.0, "ai agents": 3.0,
            "multi-tenant": 2.5, "subscription": 2.0,
        },
        "description": "Full AI agent orchestration SaaS platform",
    },
}

COMPLEXITY_KEYWORDS: dict[str, list[str]] = {
    "simple": [
        "simple", "basico", "basic", "sencillo", "rapido", "quick",
        "minimal", "3 agentes", "3 agents", "mvp", "prototype",
    ],
    "medium": [
        "medio", "medium", "moderado", "moderate", "estandar", "standard",
        "5 agentes", "5 agents",
    ],
    "complex": [
        "complejo", "complex", "avanzado", "advanced", "enterprise",
        "empresarial", "7 agentes", "7 agents", "full", "production",
        "scalable",
    ],
}

MODULE_KEYWORDS: dict[str, list[str]] = {
    "auth": ["auth", "login", "registro", "authentication", "jwt", "oauth", "sesion", "session"],
    "billing": ["billing", "pago", "payment", "suscripcion", "subscription", "stripe", "plan", "premium"],
    "analytics": ["analytics", "analitica", "metricas", "metrics", "tracking", "telemetria"],
    "ai_chat": ["chat", "chatbot", "asistente", "assistant", "conversacion", "llm"],
    "notifications": ["notificacion", "notification", "email", "slack", "webhook", "alerta", "alert"],
    "connectors": ["conector", "connector", "integracion", "integration", "api", "gmail", "drive", "notion"],
    "observability": ["observabilidad", "observability", "logs", "tracing", "monitoring"],
    "admin_panel": ["admin", "panel", "dashboard", "configuracion", "settings"],
}

# Default modules per project type
TYPE_DEFAULTS: dict[str, list[str]] = {
    "ticket_system": ["auth", "notifications", "connectors", "observability"],
    "invoice_processor": ["auth", "connectors", "observability"],
    "email_responder": ["auth", "connectors", "notifications"],
    "approval_workflow": ["auth", "notifications", "admin_panel"],
    "report_generator": ["auth", "analytics", "connectors"],
    "data_sync": ["auth", "connectors", "observability"],
    "monitoring": ["auth", "notifications", "observability", "analytics"],
    "agentic_saas": [
        "auth", "billing", "analytics", "ai_chat",
        "notifications", "connectors", "observability", "admin_panel",
    ],
}

# ---------------------------------------------------------------------------
# Prompt enhancement patterns
# ---------------------------------------------------------------------------

DATA_SOURCE_PATTERNS: dict[str, list[str]] = {
    "email": ["email", "correo", "inbox", "smtp", "imap"],
    "files": ["file", "archivo", "csv", "excel", "pdf", "upload"],
    "api": ["api", "rest", "graphql", "endpoint", "webhook"],
    "webhook": ["webhook", "callback", "hook"],
    "database": ["database", "db", "sql", "postgres", "mysql", "mongo"],
    "queue": ["queue", "kafka", "rabbitmq", "sqs", "redis"],
}

OUTPUT_PATTERNS: dict[str, list[str]] = {
    "email": ["send email", "enviar correo", "email notification", "smtp"],
    "slack": ["slack", "slack notification", "slack message"],
    "notion": ["notion", "notion page", "notion database"],
    "dashboard": ["dashboard", "panel", "web ui", "frontend"],
    "webhook": ["webhook", "callback", "http post"],
    "pdf": ["pdf", "report", "generate pdf", "export pdf"],
}

INDUSTRY_PATTERNS: dict[str, list[str]] = {
    "finance": ["finance", "finanzas", "banking", "banco", "payment", "invoice", "accounting", "contabilidad"],
    "healthcare": ["healthcare", "salud", "medical", "hospital", "patient", "hipaa", "clinical"],
    "technology": ["tech", "software", "saas", "api", "devops", "cloud", "startup"],
    "legal": ["legal", "law", "contract", "compliance", "regulation", "attorney"],
    "retail": ["retail", "ecommerce", "tienda", "store", "inventory", "commerce"],
    "education": ["education", "learning", "school", "university", "course", "student"],
}

SCALE_PATTERNS: dict[str, list[str]] = {
    "solo_dev": ["personal", "solo", "individual", "side project", "hobby"],
    "small_team": ["small team", "startup", "equipo", "team", "small business"],
    "enterprise": ["enterprise", "empresa", "corporate", "large scale", "production", "high availability"],
}

COMPLIANCE_PATTERNS: dict[str, list[str]] = {
    "GDPR": ["gdpr", "data protection", "privacy", "european", "eu regulation"],
    "HIPAA": ["hipaa", "health data", "phi", "protected health"],
    "SOC2": ["soc2", "soc 2", "security audit", "trust services"],
    "PCI_DSS": ["pci", "credit card", "card data", "payment security"],
}


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def _compute_idf_weights(patterns: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Compute inverse document frequency for each keyword across all types.

    Keywords that appear in many intent types get a lower weight multiplier,
    making unique keywords more discriminating.

    Args:
        patterns: The INTENT_PATTERNS registry.

    Returns:
        Mapping of keyword -> IDF weight.
    """
    total_types = len(patterns)
    keyword_doc_count: dict[str, int] = {}

    for _ptype, config in patterns.items():
        seen: set[str] = set()
        for kw in config["keywords"]:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                keyword_doc_count[kw_lower] = keyword_doc_count.get(kw_lower, 0) + 1

    idf: dict[str, float] = {}
    for kw, count in keyword_doc_count.items():
        idf[kw] = math.log((total_types + 1) / (count + 1)) + 1.0

    return idf


_IDF_WEIGHTS = _compute_idf_weights(INTENT_PATTERNS)


def _score_project_types(text: str) -> dict[str, float]:
    """Score every project type using weighted keyword matching with IDF.

    Args:
        text: Lowercased prompt text.

    Returns:
        Mapping of project_type -> raw score.
    """
    scores: dict[str, float] = {}

    for ptype, config in INTENT_PATTERNS.items():
        score = 0.0
        for keyword, weight in config["keywords"].items():
            kw_lower = keyword.lower()
            if kw_lower in text:
                idf = _IDF_WEIGHTS.get(kw_lower, 1.0)
                score += weight * idf
        scores[ptype] = score

    return scores


def _normalize_confidence(score: float, max_possible: float) -> float:
    """Convert a raw score to a 0.0-1.0 confidence value.

    Uses a sigmoid-like curve so that moderate keyword matches still
    produce reasonable confidence values.

    Args:
        score: The raw score to normalize.
        max_possible: Theoretical maximum score for calibration.

    Returns:
        Confidence in the [0.0, 1.0] range.
    """
    if max_possible <= 0 or score <= 0:
        return 0.0
    ratio = score / max_possible
    # Sigmoid scaling: fast rise near 0.3, saturates toward 1.0
    confidence = 1.0 / (1.0 + math.exp(-10 * (ratio - 0.3)))
    return round(min(confidence, 1.0), 2)


# ---------------------------------------------------------------------------
# Feature extraction helpers
# ---------------------------------------------------------------------------

def _detect_patterns(text: str, patterns: dict[str, list[str]]) -> list[str]:
    """Return all pattern keys whose keywords appear in *text*.

    Args:
        text: Lowercased prompt text.
        patterns: Mapping of label -> keyword list.

    Returns:
        Sorted list of matched labels.
    """
    matched: list[str] = []
    for label, keywords in patterns.items():
        if any(kw in text for kw in keywords):
            matched.append(label)
    return sorted(matched)


def _detect_complexity(text: str) -> str:
    """Detect project complexity from text.

    Args:
        text: Lowercased prompt text.

    Returns:
        One of ``"simple"``, ``"medium"``, ``"complex"``.
    """
    for level, keywords in COMPLEXITY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return level
    return "medium"


def _detect_modules(text: str, project_type: str) -> list[str]:
    """Detect required modules from text plus project type defaults.

    Args:
        text: Lowercased prompt text.
        project_type: The primary detected project type.

    Returns:
        Deduplicated module ID list.
    """
    detected: list[str] = []
    for module, keywords in MODULE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            detected.append(module)

    defaults = TYPE_DEFAULTS.get(project_type, ["auth", "observability"])
    for mod in defaults:
        if mod not in detected:
            detected.append(mod)

    return detected


def _detect_platform(text: str) -> dict[str, bool]:
    """Detect target platform flags.

    Args:
        text: Lowercased prompt text.

    Returns:
        Dict with ``backend``, ``web``, ``mobile`` booleans.
    """
    return {
        "backend": True,
        "web": any(kw in text for kw in ("web", "dashboard", "panel", "frontend", "ui")),
        "mobile": any(kw in text for kw in ("mobile", "flutter", "app", "android", "ios")),
    }


def _enhance_requirements(text: str, project_type: str, modules: list[str]) -> str:
    """Build a structured enhanced-requirements summary from the raw prompt.

    Args:
        text: The original (unmodified) prompt.
        project_type: Detected project type.
        modules: Detected modules list.

    Returns:
        Multi-line string with structured requirement details.
    """
    lines = [
        f"Project type: {project_type}",
        f"Detected modules: {', '.join(modules)}",
    ]

    text_lower = text.lower()

    sources = _detect_patterns(text_lower, DATA_SOURCE_PATTERNS)
    if sources:
        lines.append(f"Data sources: {', '.join(sources)}")

    outputs = _detect_patterns(text_lower, OUTPUT_PATTERNS)
    if outputs:
        lines.append(f"Output destinations: {', '.join(outputs)}")

    industries = _detect_patterns(text_lower, INDUSTRY_PATTERNS)
    if industries:
        lines.append(f"Industry: {', '.join(industries)}")

    compliance = _detect_patterns(text_lower, COMPLIANCE_PATTERNS)
    if compliance:
        lines.append(f"Compliance: {', '.join(compliance)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Context-aware routing — reads user history
# ---------------------------------------------------------------------------

_HISTORY_PATH = os.path.join(os.path.expanduser("~"), ".nexusforge", "history.json")


def _load_history() -> list[dict[str, Any]]:
    """Load project generation history from disk.

    Returns:
        List of past project records, or empty list if unavailable.
    """
    if not os.path.isfile(_HISTORY_PATH):
        return []
    try:
        with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _suggest_from_history(
    project_type: str,
    modules: list[str],
) -> list[str]:
    """Suggest additional modules based on user's past projects.

    Looks at the history of projects with the same type and returns modules
    that the user frequently included but are not in the current selection.

    Args:
        project_type: The detected project type.
        modules: Currently detected modules.

    Returns:
        List of suggested module IDs, sorted by frequency.
    """
    history = _load_history()
    if not history:
        return []

    module_freq: dict[str, int] = {}
    relevant_count = 0

    for record in history:
        if record.get("project_type") == project_type:
            relevant_count += 1
            for mod in record.get("modules", []):
                if mod not in modules:
                    module_freq[mod] = module_freq.get(mod, 0) + 1

    # Only suggest modules that appear in > 50% of relevant past projects
    threshold = max(1, relevant_count // 2)
    suggestions = [
        mod for mod, count in sorted(module_freq.items(), key=lambda x: -x[1])
        if count >= threshold
    ]

    return suggestions


def _save_to_history(intent_result: dict[str, Any]) -> None:
    """Append the current intent result to user history.

    Args:
        intent_result: The full intent dict returned by :func:`route_intent`.
    """
    record = {
        "project_type": intent_result.get("project_type", ""),
        "modules": intent_result.get("modules", []),
        "complexity": intent_result.get("complexity", ""),
        "confidence": intent_result.get("confidence", 0.0),
    }

    history = _load_history()
    history.append(record)

    # Keep last 100 entries
    history = history[-100:]

    history_dir = os.path.dirname(_HISTORY_PATH)
    try:
        os.makedirs(history_dir, exist_ok=True)
        with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except OSError:
        pass  # Non-critical — do not crash if history cannot be saved


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route_intent(prompt: str, save_history: bool = True) -> dict[str, Any]:
    """Analyze a natural language prompt and return a rich structured intent.

    The v1.0 router uses weighted TF-IDF scoring, multi-intent detection,
    confidence scoring, context-aware suggestions from user history, and
    structured requirement extraction.

    Args:
        prompt: The user's natural language project description.
        save_history: Whether to save this intent to ``~/.nexusforge/history.json``.
            Set to False when ``--no-telemetry`` is active.

    Returns:
        Dictionary with the following keys:

        - ``project_type`` (str): Primary detected project type.
        - ``confidence`` (float): Confidence score 0.0-1.0.
        - ``alternative_types`` (list[dict]): Other plausible types with scores.
        - ``complexity`` (str): ``"simple"``, ``"medium"``, or ``"complex"``.
        - ``modules`` (list[str]): Detected + default module IDs.
        - ``data_sources`` (list[str]): Detected data source types.
        - ``outputs`` (list[str]): Detected output destinations.
        - ``industry`` (str): Best-matching industry or ``"general"``.
        - ``scale`` (str): Scale expectation.
        - ``compliance`` (list[str]): Detected compliance requirements.
        - ``description`` (str): The original prompt.
        - ``enhanced_requirements`` (str): Structured requirement summary.
        - ``platform`` (dict): Target platform flags.
        - ``history_suggestions`` (list[str]): Module suggestions from history.
        - ``detected_from`` (str): Always ``"intent_router_v1"``.
    """
    prompt_lower = prompt.lower()

    # --- Score all project types ---
    scores = _score_project_types(prompt_lower)

    # Compute max possible score for confidence calibration
    max_possible = 0.0
    for config in INTENT_PATTERNS.values():
        type_max = sum(
            w * _IDF_WEIGHTS.get(kw.lower(), 1.0)
            for kw, w in config["keywords"].items()
        )
        max_possible = max(max_possible, type_max)

    # Sort by score descending
    ranked = sorted(scores.items(), key=lambda x: -x[1])

    # Primary type
    if ranked and ranked[0][1] > 0:
        project_type = ranked[0][0]
        primary_confidence = _normalize_confidence(ranked[0][1], max_possible)
    else:
        project_type = "agentic_saas"
        primary_confidence = 0.3

    # Alternative types (confidence > 0.1, excluding primary)
    alternative_types: list[dict[str, Any]] = []
    for ptype, score in ranked[1:]:
        conf = _normalize_confidence(score, max_possible)
        if conf >= 0.1:
            alternative_types.append({"type": ptype, "confidence": conf})

    # --- Multi-intent detection ---
    # If the top two types both have high confidence, flag as multi-intent
    multi_intent_types: list[str] = [project_type]
    for alt in alternative_types:
        if alt["confidence"] >= 0.5:
            multi_intent_types.append(alt["type"])

    # --- Feature extraction ---
    complexity = _detect_complexity(prompt_lower)
    modules = _detect_modules(prompt_lower, project_type)
    platform = _detect_platform(prompt_lower)
    data_sources = _detect_patterns(prompt_lower, DATA_SOURCE_PATTERNS)
    outputs = _detect_patterns(prompt_lower, OUTPUT_PATTERNS)

    industries = _detect_patterns(prompt_lower, INDUSTRY_PATTERNS)
    industry = industries[0] if industries else "general"

    scales = _detect_patterns(prompt_lower, SCALE_PATTERNS)
    scale = scales[0] if scales else "small_team"

    compliance = _detect_patterns(prompt_lower, COMPLIANCE_PATTERNS)

    # --- Context-aware suggestions ---
    history_suggestions = _suggest_from_history(project_type, modules)

    # --- Enhanced requirements ---
    enhanced_requirements = _enhance_requirements(prompt, project_type, modules)

    result: dict[str, Any] = {
        "project_type": project_type,
        "confidence": primary_confidence,
        "alternative_types": alternative_types,
        "multi_intent": multi_intent_types if len(multi_intent_types) > 1 else [],
        "complexity": complexity,
        "modules": modules,
        "data_sources": data_sources,
        "outputs": outputs,
        "industry": industry,
        "scale": scale,
        "compliance": compliance,
        "description": prompt,
        "enhanced_requirements": enhanced_requirements,
        "platform": platform,
        "history_suggestions": history_suggestions,
        "detected_from": "intent_router_v1",
    }

    if save_history:
        _save_to_history(result)

    return result
