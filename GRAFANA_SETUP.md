# SchemaAdvisor Grafana Dashboard Setup Guide

## Quick Start

### Option 1: Docker Compose (Recommended)

Run the complete monitoring stack locally:

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

This will start:
- **SchemaAdvisor API**: http://localhost:8000
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin / admin)

Wait ~30 seconds for Prometheus to scrape initial metrics, then:

1. **Login to Grafana**: http://localhost:3000
   - Username: `admin`
   - Password: `admin`

2. **View Dashboard**: 
   - Go to **Dashboards** → **SchemaAdvisor API Monitoring**
   - Auto-imported from `grafana-provisioning/dashboards/`

### Option 2: Manual Grafana Setup

If Grafana is already running:

1. **Add Prometheus Data Source**:
   - Settings → Data Sources → Add
   - Type: Prometheus
   - URL: `http://prometheus:9090` (or `http://localhost:9090`)
   - Click "Save & Test"

2. **Import Dashboard**:
   - Dashboards → Import
   - Upload `GRAFANA_DASHBOARD.json`
   - Select Prometheus as data source
   - Click "Import"

---

## Dashboard Panels

### 1. **Schema Generation Rate** (top-left)
- **Metric**: `rate(schemas_generated_total[5m])`
- **What it shows**: Schemas generated per 5-minute window
- **Use case**: Monitor schema generation throughput

### 2. **Total Schemas Generated** (top-right)
- **Metric**: `schemas_generated_total`
- **What it shows**: Cumulative count of schemas
- **Use case**: Track total volume over time

### 3. **Schema Generation Latency** (middle-left)
- **Metric**: p95, p99 latency from `schema_generation_seconds`
- **What it shows**: 95th and 99th percentile generation times
- **Use case**: Identify slow schemas and SLA violations

### 4. **API Request Rate** (middle-right)
- **Metric**: `rate(flask_http_request_total[5m])`
- **What it shows**: Request volume by endpoint/method
- **Use case**: Monitor API traffic patterns

### 5. **Service Health** (bottom-left, 4 gauges)
- **Neo4j Status**: Connectivity to Neo4j (1=up, 0=down)
- **PostgreSQL Status**: Connectivity to PostgreSQL
- **Redis Status**: Connectivity to Redis cache
- **Anthropic API Status**: LLM API availability
- **Use case**: Quick health check at a glance

### 6. **Admin Login Attempts** (bottom-center)
- **Metric**: `admin_login_attempts_total{status}`
- **What it shows**: Success vs. failure login counts
- **Use case**: Security monitoring, detect brute force

### 7. **LLM API Errors** (bottom-right)
- **Metric**: `rate(llm_api_errors_total[5m])`
- **What it shows**: Error rate by error type
- **Use case**: Monitor API failures and degradation

---

## Customizing the Dashboard

### Adding New Panels

1. Click **Add Panel** button (top-right)
2. Select **Prometheus** as data source
3. Write PromQL query (examples below)
4. Customize visualization
5. Click **Save**

### Useful PromQL Queries

**Cache Hit Rate**:
```promql
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

**Error Rate Percentage**:
```promql
rate(llm_api_errors_total[5m]) / rate(schemas_generated_total[5m]) * 100
```

**Average Schema Generation Time**:
```promql
histogram_quantile(0.5, rate(schema_generation_seconds_bucket[5m]))
```

**Concept Extraction Rate**:
```promql
rate(concepts_extracted_total[5m])
```

**DB Pool Utilization**:
```promql
db_pool_connections_active / db_pool_connections_total * 100
```

---

## Alerting (Optional)

To set up alerts in Prometheus:

1. Create `alerts.yml` with alert rules:

```yaml
groups:
  - name: schemaadvisor
    rules:
      - alert: SchemaGenerationLatencyHigh
        expr: histogram_quantile(0.95, rate(schema_generation_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Schema generation latency > 10s"

      - alert: ServiceDown
        expr: neo4j_connected == 0 OR postgres_connected == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Backend service down"
```

2. Reference in `prometheus.yml`:
```yaml
rule_files:
  - "alerts.yml"
```

---

## Troubleshooting

### Metrics not appearing

1. Check Prometheus is scraping SchemaAdvisor:
   - Go to http://localhost:9090/targets
   - Verify `schemaadvisor` job is UP

2. Verify API metrics endpoint:
   ```bash
   curl http://localhost:8000/metrics
   ```
   Should return Prometheus-format metrics

3. Check Grafana data source:
   - Settings → Data Sources → Prometheus
   - Click "Test" button, verify "Success"

### Dashboard panels showing "No Data"

1. Metrics need to be generated first — make some schema generation requests:
   ```bash
   curl -X POST http://localhost:8000/schema \
     -H "Content-Type: application/json" \
     -d '{"requirements": "Simple user table"}'
   ```

2. Wait 15 seconds for Prometheus scrape (`scrape_interval: 15s`)

3. Refresh Grafana dashboard (Ctrl+Shift+R)

### Out of Memory (Docker)

Increase Docker memory limit:
```bash
docker-compose -f docker-compose.monitoring.yml down
# Increase memory in Docker Desktop settings, then:
docker-compose -f docker-compose.monitoring.yml up -d
```

---

## Production Deployment

For production, edit `docker-compose.monitoring.yml`:

1. **Change Grafana password**:
   ```yaml
   environment:
     GF_SECURITY_ADMIN_PASSWORD: secure_password_here
   ```

2. **Enable persistent volumes** (already done)

3. **Configure alert managers** (optional)

4. **Add authentication** to Prometheus (use reverse proxy like Nginx)

5. **Scale Prometheus retention**:
   ```yaml
   command:
     - "--storage.tsdb.retention.time=30d"  # Keep 30 days of data
   ```

---

##References

- [Prometheus Docs](https://prometheus.io/docs)
- [Grafana Docs](https://grafana.com/docs)
- [PromQL Query Examples](https://prometheus.io/docs/prometheus/latest/querying/examples/)
- [SchemaAdvisor Metrics](./PROGRESS.md#session-2026-04-14--prometheus-metrics)

---

**Version**: 1.0  
**Last Updated**: 2026-04-14  
**Status**: Production Ready ✅
