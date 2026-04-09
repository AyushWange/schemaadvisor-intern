# SchemaAdvisor Production Deployment Guide

## Overview
SchemaAdvisor is now production-ready with comprehensive security, error handling, monitoring, and deployment configurations.

---

## 1. Environment Setup

### Required Environment Variables (.env)
```bash
# API Configuration
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
API_WORKERS=4

# LLM
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here

# Neo4j (Knowledge Graph)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password

# PostgreSQL (Validation)
PG_HOST=your-postgres-host
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=your-secure-password
PG_DB=schema_test

# Logging
LOG_LEVEL=INFO
```

---

## 2. Security Features

### ✅ Implemented
- **Input Validation**: All requests validated with Pydantic with max length constraints
- **XSS Protection**: HTML escaping on user inputs
- **Rate Limiting**: 30 req/min per IP for `/schema`, 60 req/min for admin endpoints
- **CORS**: Restricted to specific origins (not wildcard)
- **Request Timeout**: 120-second timeout for schema generation
- **Error Handling**: Custom error handlers prevent information leakage
- **Logging**: All requests logged with unique request IDs

### Configuration
Update `ALLOWED_ORIGINS` in `.env` for your domain:
```bash
ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
```

---

## 3. Deployment Options

### Option A: Docker (Recommended)
```bash
# Build
docker build -t schemaadvisor:2.8.0 .

# Run with compose
docker-compose up -d

# Verify
curl http://localhost:8000/health
```

### Option B: Systemd Service (Linux)
```ini
[Unit]
Description=SchemaAdvisor API
After=network.target

[Service]
Type=notify
User=schemaadvisor
WorkingDirectory=/opt/schemaadvisor
ExecStart=/opt/schemaadvisor/.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Option C: Gunicorn + Nginx
```bash
# Install
pip install gunicorn

# Run
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app

# Nginx config (reverse proxy on :80/:443)
```

---

## 4. Monitoring & Observability

### Health Checks
```bash
# Check service health
curl http://localhost:8000/health

# Response includes:
# - status: ok/degraded
# - llm_ready: API key status
# - neo4j_ready: Graph DB status
# - uptime_seconds: Service uptime
```

### Logging
- **Location**: `schemaadvisor.log` (rotating)
- **Format**: Timestamp, level, request ID, message
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

Example log:
```
2026-04-08 10:15:23,456 - root - INFO - [abc1d2e3] POST /schema → 200 (2.341s)
2026-04-08 10:16:45,789 - root - WARNING - [xyz9w8v7] Admin: Attempt to add duplicate concept: user_management
```

### Metrics to Monitor
- Request latency (X-Response-Time header)
- Error rate (% of 4xx/5xx responses)
- Rate limit hits (429 responses)
- Pipeline success rate
- Neo4j connectivity
- Database validation rate

---

## 5. Performance Tuning

### API Workers
```bash
# production (docker-compose or multi-process)
API_WORKERS=4  # CPU cores for CPU-bound work
```

### Connection Pooling
- Neo4j: Automatic connection pooling
- PostgreSQL: Psycopg2 connection caching

### Caching Opportunities
- Concept registry (`/admin/concepts`) — consider Redis cache
- Dependency graphs — cache for 1 hour
- Candidate lists (`/admin/candidates`) — Neo4j queries cached

---

## 6. Disaster Recovery

### Backup Strategy
```bash
# Neo4j backup
docker exec schemaadvisor-neo4j neo4j-admin backup --backup-dir=/backups --database=neo4j

# Database dumps
pg_dump schema_test > schema_test_backup.sql
```

### Failover
- Neo4j: Use clustering for HA
- PostgreSQL: Use replication or managed RDS
- API: Multiple instances behind load balancer

### Circuit Breakers
- Automatically trigger if LLM fails 3+ times
- Automatically trigger if Neo4j fails 5+ times  
- Prevents cascading failures to users

---

## 7. Update Procedure

### Rolling Deployment
```bash
# 1. Pull new code
git pull origin main

# 2. Run tests
pytest tests/ -v

# 3. Update deps
pip install -r requirements.txt

# 4. Restart (one at a time with load balancer draining)
systemctl restart schemaadvisor-api
```

### Backwards Compatibility
- API contract is stable (v2.8.0)
- Database schema versioning via Neo4j
- Gradual rollout with canary deployment

---

## 8. Troubleshooting

### Service Won't Start
```bash
# Check logs
tail -f schemaadvisor.log

# Check syntax
python -m py_compile api.py

# Check ports
lsof -i :8000
```

### High Latency
```bash
# Check request headers for X-Response-Time
time curl http://localhost:8000/api

# Check Neo4j/PostgreSQL latency separately
```

### Rate Limit Issues
```bash
# Adjust in api.py
# @limiter.limit("30/minute") → @limiter.limit("120/minute")

# Or use environment variable (implement if needed)
```

---

## 9. Checklist Before Production

- [ ] ANTHROPIC_API_KEY set and valid
- [ ] ALLOWED_ORIGINS updated to your domain
- [ ] Neo4j configured and reachable
- [ ] PostgreSQL configured and reachable  
- [ ] All 53 tests pass
- [ ] Logging configured (rotation, retention)
- [ ] Monitoring alerts set up
- [ ] Backup strategy in place
- [ ] Rate limits tested and adjusted
- [ ] Health check integrated with load balancer
- [ ] SSL/TLS configured at reverse proxy
- [ ] CORS headers verified in browser

---

## Support & Logs

For issues:
1. Check `schemaadvisor.log` for request ID
2. Search logs by request ID for full request/response trace
3. Check health endpoint: `GET /health`
4. Check circuit breaker status (internal monitoring)

---

**Version**: 2.8.0  
**Last Updated**: 2026-04-08  
**Status**: Production-Ready ✅
