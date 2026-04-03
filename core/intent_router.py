"""Intent Router — classifies natural language descriptions into project types."""

import re

# Keywords that map to project types
INTENT_PATTERNS = {
    "ticket_system": {
        "keywords": ["ticket", "soporte", "support", "triage", "helpdesk", "mesa de ayuda", "clasificar tickets", "customer service", "incidencias"],
        "description": "Ticket triage and customer support automation",
    },
    "invoice_processor": {
        "keywords": ["factura", "invoice", "pdf", "ocr", "extracción", "extraction", "datos de factura", "procesamiento de facturas", "billing"],
        "description": "Document/invoice processing pipeline",
    },
    "email_responder": {
        "keywords": ["email", "correo", "auto-responder", "respuesta automática", "inbox", "bandeja de entrada", "reply", "auto-reply"],
        "description": "Smart email auto-response system",
    },
    "approval_workflow": {
        "keywords": ["aprobación", "approval", "solicitud", "request", "autorización", "authorization", "vacaciones", "compras", "gastos", "expenses", "reembolso"],
        "description": "Request approval and authorization pipeline",
    },
    "report_generator": {
        "keywords": ["reporte", "report", "resumen", "summary", "kpi", "dashboard", "métricas", "analytics", "ejecutivo", "executive"],
        "description": "Automated report and analytics generator",
    },
    "data_sync": {
        "keywords": ["sincronizar", "sync", "migrar", "migrate", "crm", "erp", "integrar sistemas", "data pipeline", "etl"],
        "description": "Data synchronization between systems",
    },
    "monitoring": {
        "keywords": ["monitoreo", "monitoring", "alertas", "alerts", "sla", "uptime", "anomalías", "anomaly", "vigilar"],
        "description": "Operations monitoring and alerting",
    },
    "agentic_saas": {
        "keywords": ["saas", "plataforma", "platform", "multi-agent", "orquestación", "orchestration", "nexusforge", "agentes ia"],
        "description": "Full AI agent orchestration SaaS platform",
    },
}

COMPLEXITY_KEYWORDS = {
    "simple": ["simple", "básico", "basic", "sencillo", "rápido", "quick", "minimal", "3 agentes", "3 agents"],
    "medium": ["medio", "medium", "moderado", "moderate", "estándar", "standard", "5 agentes", "5 agents"],
    "complex": ["complejo", "complex", "avanzado", "advanced", "enterprise", "empresarial", "7 agentes", "7 agents", "full"],
}

MODULE_KEYWORDS = {
    "auth": ["auth", "login", "registro", "authentication", "jwt", "oauth", "sesión", "session"],
    "billing": ["billing", "pago", "payment", "suscripción", "subscription", "stripe", "plan", "premium"],
    "analytics": ["analytics", "analítica", "métricas", "metrics", "tracking", "telemetría"],
    "ai_chat": ["chat", "chatbot", "asistente", "assistant", "conversación", "llm"],
    "notifications": ["notificación", "notification", "email", "slack", "webhook", "alerta", "alert"],
    "connectors": ["conector", "connector", "integración", "integration", "api", "gmail", "drive", "notion"],
    "observability": ["observabilidad", "observability", "logs", "tracing", "monitoring"],
    "admin_panel": ["admin", "panel", "dashboard", "configuración", "settings"],
}


def route_intent(prompt: str) -> dict:
    """Analyze a natural language prompt and return structured intent."""
    prompt_lower = prompt.lower()

    # Detect project type
    project_type = _detect_project_type(prompt_lower)

    # Detect complexity
    complexity = _detect_complexity(prompt_lower)

    # Detect modules
    modules = _detect_modules(prompt_lower, project_type)

    # Detect platform
    platform = _detect_platform(prompt_lower)

    return {
        "project_type": project_type,
        "complexity": complexity,
        "modules": modules,
        "platform": platform,
        "description": prompt,
        "detected_from": "intent_router",
    }


def _detect_project_type(text: str) -> str:
    """Find the best matching project type."""
    scores = {}
    for ptype, config in INTENT_PATTERNS.items():
        score = sum(1 for kw in config["keywords"] if kw in text)
        if score > 0:
            scores[ptype] = score

    if not scores:
        return "agentic_saas"  # default

    return max(scores, key=scores.get)


def _detect_complexity(text: str) -> str:
    """Detect project complexity."""
    for level, keywords in COMPLEXITY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return level
    return "medium"  # default


def _detect_modules(text: str, project_type: str) -> list:
    """Detect required modules from text + project type defaults."""
    detected = []
    for module, keywords in MODULE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            detected.append(module)

    # Add defaults based on project type
    TYPE_DEFAULTS = {
        "ticket_system": ["auth", "notifications", "connectors", "observability"],
        "invoice_processor": ["auth", "connectors", "observability"],
        "email_responder": ["auth", "connectors", "notifications"],
        "approval_workflow": ["auth", "notifications", "admin_panel"],
        "report_generator": ["auth", "analytics", "connectors"],
        "data_sync": ["auth", "connectors", "observability"],
        "monitoring": ["auth", "notifications", "observability", "analytics"],
        "agentic_saas": ["auth", "billing", "analytics", "ai_chat", "notifications", "connectors", "observability", "admin_panel"],
    }

    defaults = TYPE_DEFAULTS.get(project_type, ["auth", "observability"])
    for mod in defaults:
        if mod not in detected:
            detected.append(mod)

    return detected


def _detect_platform(text: str) -> dict:
    """Detect target platform."""
    return {
        "backend": True,
        "web": "web" in text or "dashboard" in text or "panel" in text or "frontend" in text,
        "mobile": "mobile" in text or "flutter" in text or "app" in text,
    }
