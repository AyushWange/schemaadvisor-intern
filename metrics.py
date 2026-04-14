import logging
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
import time

logger = logging.getLogger(__name__)

# ── Custom Metrics ─────────────────────────────────────────────────────────────

# Business Logic Metrics
schemas_generated_total = Counter(
    'schemas_generated_total',
    'Total number of schemas generated',
    ['decision_profile'],  # e.g. 'single_tenant', 'multi_tenant', etc.
)

schema_generation_seconds = Histogram(
    'schema_generation_seconds',
    'Time taken to generate a schema (seconds)',
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

concepts_extracted_total = Counter(
    'concepts_extracted_total',
    'Total number of concepts extracted from requirements',
)

decisions_confirmed_total = Counter(
    'decisions_confirmed_total',
    'Total number of user-confirmed decisions',
    ['decision_type'],  # e.g. 'tenancy_model', 'versioning', etc.
)

conflicts_detected_total = Counter(
    'conflicts_detected_total',
    'Total number of conflict warnings detected',
    ['conflict_type'],  # e.g. 'hard_incompatibility', 'tradeoff_warning'
)

table_count_summary = Histogram(
    'generated_tables_count',
    'Distribution of table counts in generated schemas',
    buckets=(1, 5, 10, 20, 50, 100),
)

# API Route Metrics
admin_login_attempts_total = Counter(
    'admin_login_attempts_total',
    'Total admin login attempts (success/failure)',
    ['status'],  # 'success', 'failure'
)

api_calls_total = Counter(
    'api_calls_total',
    'Total number of API calls',
    ['endpoint', 'method', 'status_code'],
)

api_latency_seconds = Histogram(
    'api_latency_seconds',
    'API endpoint latency (seconds)',
    ['endpoint', 'method'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
)

# Backend Service Health Metrics
neo4j_connected = Gauge(
    'neo4j_connected',
    'Neo4j connectivity status (1=up, 0=down)',
)

postgres_connected = Gauge(
    'postgres_connected',
    'PostgreSQL connectivity status (1=up, 0=down)',
)

redis_connected = Gauge(
    'redis_connected',
    'Redis connectivity status (1=up, 0=down)',
)

anthropic_api_available = Gauge(
    'anthropic_api_available',
    'Anthropic API availability (1=available, 0=unavailable)',
)

db_pool_connections_active = Gauge(
    'db_pool_connections_active',
    'Number of active connections in PostgreSQL pool',
)

db_pool_connections_total = Gauge(
    'db_pool_connections_total',
    'Total connections in PostgreSQL pool (max)',
)

# Cache Metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type'],  # 'redis', 'memory'
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type'],
)

cache_size_bytes = Gauge(
    'cache_size_bytes',
    'Current cache size (bytes)',
    ['cache_type'],
)

# Error Metrics
llm_api_errors_total = Counter(
    'llm_api_errors_total',
    'Total LLM API errors',
    ['error_type'],  # e.g. '401_unauthorized', 'timeout', 'rate_limited'
)

pipeline_errors_total = Counter(
    'pipeline_errors_total',
    'Total pipeline execution errors',
    ['stage', 'error_type'],  # stage: S1, S2, ..., S8
)

validation_errors_total = Counter(
    'validation_errors_total',
    'Total schema validation errors',
    ['error_type'],  # e.g. 'fk_violation', 'constraint_violation'
)

# ── Prometheus Instrumentator Setup ────────────────────────────────────────────

def setup_prometheus_metrics(app):
    """
    Initialize Prometheus metrics collection for FastAPI application
    
    Args:
        app: FastAPI application instance
    
    Returns:
        Instrumentator instance
    """
    logger.info("Setting up Prometheus metrics instrumentation")
    
    try:
        instrumentator = Instrumentator()
        instrumentator.instrument(app).expose(
            app,
            endpoint='/metrics',
            include_in_schema=False  # Don't show in OpenAPI schema
        )
        logger.info("Prometheus metrics exposed at /metrics")
        return instrumentator
    except Exception as e:
        logger.warning(f"Failed to setup Prometheus: {e}. Continuing without metrics.")
        return None


# ── Metric Helpers ────────────────────────────────────────────────────────────

def record_schema_generation(generation_time: float, table_count: int, decision_profile: str = "unspecified"):
    """Record a schema generation event"""
    schema_generation_seconds.observe(generation_time)
    schemas_generated_total.labels(decision_profile=decision_profile).inc()
    table_count_summary.observe(table_count)


def record_concept_extraction(concept_count: int = 1):
    """Record concept extraction event"""
    concepts_extracted_total.inc(concept_count)


def record_decision_confirmation(decision_type: str, decision_count: int = 1):
    """Record user decision confirmation"""
    decisions_confirmed_total.labels(decision_type=decision_type).inc(decision_count)


def record_conflict_detection(conflict_type: str = "hard_incompatibility"):
    """Record conflict detection event"""
    conflicts_detected_total.labels(conflict_type=conflict_type).inc()


def record_login_attempt(success: bool):
    """Record admin login attempt"""
    status = "success" if success else "failure"
    admin_login_attempts_total.labels(status=status).inc()


def record_llm_error(error_type: str):
    """Record LLM API error"""
    llm_api_errors_total.labels(error_type=error_type).inc()


def record_pipeline_error(stage: str, error_type: str):
    """Record pipeline execution error"""
    pipeline_errors_total.labels(stage=stage, error_type=error_type).inc()


def record_validation_error(error_type: str):
    """Record schema validation error"""
    validation_errors_total.labels(error_type=error_type).inc()


def update_service_health(service: str, is_healthy: bool):
    """Update service health status (1=up, 0=down)"""
    status = 1 if is_healthy else 0
    
    if service == "neo4j":
        neo4j_connected.set(status)
    elif service == "postgres":
        postgres_connected.set(status)
    elif service == "redis":
        redis_connected.set(status)
    elif service == "anthropic":
        anthropic_api_available.set(status)


def update_cache_metrics(cache_type: str, hit: bool, size_bytes: int = None):
    """Update cache hit/miss and optional size metrics"""
    if hit:
        cache_hits_total.labels(cache_type=cache_type).inc()
    else:
        cache_misses_total.labels(cache_type=cache_type).inc()
    
    if size_bytes is not None:
        cache_size_bytes.labels(cache_type=cache_type).set(size_bytes)


def update_pool_metrics(active_connections: int, max_connections: int):
    """Update database pool connection metrics"""
    db_pool_connections_active.set(active_connections)
    db_pool_connections_total.set(max_connections)
