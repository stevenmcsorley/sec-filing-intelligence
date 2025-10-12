# TheStox Observability Stack

Comprehensive monitoring and logging infrastructure for TheStox using Prometheus, Grafana, and Loki.

## 📊 Overview

The observability stack provides:

- **Prometheus** - Metrics collection and time-series storage
- **Grafana** - Visualization dashboards for metrics and logs
- **Loki** - Log aggregation and querying
- **Promtail** - Log collection agent for Docker containers
- **Redis Exporter** - Redis metrics exporter for Prometheus
- **PostgreSQL Exporter** - PostgreSQL metrics exporter for Prometheus

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- TheStox main stack running (`docker compose up` from `ops/compose/`)
- Network `secnet` must exist (created by main stack)

### Starting the Observability Stack

```bash
# From the observability directory
cd ops/compose/observability

# Copy environment file and customize if needed
cp .env.example .env

# Start all observability services
docker compose -f docker-compose.observability.yml up -d

# Verify services are running
docker compose -f docker-compose.observability.yml ps
```

### Accessing Services

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | No auth |
| Loki | http://localhost:3100 | No auth |

## 📈 Pre-configured Dashboards

Grafana comes with three pre-configured dashboards:

### 1. Groq AI Workers
**Path:** Dashboards → TheStox → Groq AI Workers

Monitors AI worker performance:
- Completion rates for summarization, entity extraction, and diff workers
- Latency percentiles (p95) per worker type
- Token budget usage and remaining quota
- Token consumption by service and type
- Error rates by worker and error type
- Budget exhaustion events and deferred jobs

**Key Metrics:**
- `sec_summarization_completions_total`
- `sec_entity_extraction_completions_total`
- `sec_diff_completions_total`
- `sec_groq_budget_usage_tokens`
- `sec_groq_budget_remaining_tokens`
- `sec_groq_budget_deferred_jobs_total`

### 2. SEC Filing Ingestion Pipeline
**Path:** Dashboards → TheStox → SEC Filing Ingestion Pipeline

Tracks the ingestion pipeline:
- Total filings discovered from SEC EDGAR
- Queue depths (download, parse, chunk)
- Filing discovery rate by form type
- Download completion and failure rates
- Download and parse latency (p95)
- Backpressure status

**Key Metrics:**
- `sec_edgar_filings_discovered_total`
- `sec_edgar_download_queue_depth`
- `sec_edgar_parse_queue_depth`
- `sec_chunk_queue_depth`
- `sec_edgar_downloads_completed_total`
- `sec_edgar_backpressure_paused`

### 3. Infrastructure (Redis & PostgreSQL)
**Path:** Dashboards → TheStox → Infrastructure

Infrastructure health monitoring:
- Service uptime status (Redis, PostgreSQL, Backend)
- Redis connected clients
- Redis memory usage
- Redis command throughput
- PostgreSQL active connections
- PostgreSQL transaction rate (commits/rollbacks)
- Redis total keys

**Key Metrics:**
- `redis_connected_clients`
- `redis_memory_used_bytes`
- `redis_commands_processed_total`
- `pg_stat_database_numbackends`
- `pg_stat_database_xact_commit`

## 🔧 Configuration

### Prometheus Scrape Configs

Prometheus is configured to scrape metrics from:

| Job | Target | Metrics Path | Purpose |
|-----|--------|--------------|---------|
| `backend` | `backend:8000` | `/metrics` | FastAPI app metrics |
| `redis` | `redis-exporter:9121` | `/metrics` | Redis stats |
| `postgres` | `postgres-exporter:9187` | `/metrics` | PostgreSQL stats |
| `keycloak` | `keycloak:8080` | `/metrics` | Keycloak stats (if exposed) |
| `opa` | `opa:8181` | `/metrics` | OPA stats (if exposed) |
| `prometheus` | `localhost:9090` | `/metrics` | Prometheus self-monitoring |
| `grafana` | `grafana:3000` | `/metrics` | Grafana self-monitoring |

Configuration file: `prometheus.yml`

### Loki Retention

Logs are retained for **7 days** by default. To change retention:

1. Edit `loki.yml`
2. Update `limits_config.retention_period` (e.g., `168h` for 7 days)
3. Restart Loki: `docker compose -f docker-compose.observability.yml restart loki`

### Grafana Provisioning

Dashboards and datasources are automatically provisioned on startup:

- **Datasources:** `grafana/provisioning/datasources/datasources.yml`
- **Dashboard Provider:** `grafana/provisioning/dashboards/dashboards.yml`
- **Dashboard JSONs:** `grafana/dashboards/*.json`

To add a new dashboard:

1. Create dashboard in Grafana UI
2. Export as JSON (Settings → JSON Model)
3. Save to `grafana/dashboards/my-dashboard.json`
4. Restart Grafana or wait for auto-reload

## 🐛 Troubleshooting

### Services Not Starting

```bash
# Check logs
docker compose -f docker-compose.observability.yml logs -f

# Check specific service
docker compose -f docker-compose.observability.yml logs prometheus
```

### Prometheus Not Scraping Targets

1. Access Prometheus UI: http://localhost:9090
2. Navigate to Status → Targets
3. Check if targets are UP
4. Review error messages for DOWN targets

Common issues:
- Network connectivity: Ensure `secnet` network exists
- Service names: Verify service names match main docker-compose.yml
- Firewall rules: Ensure ports are accessible

### Grafana Dashboards Not Loading

```bash
# Check Grafana logs
docker compose -f docker-compose.observability.yml logs grafana

# Verify provisioning files
ls -la grafana/provisioning/dashboards/
ls -la grafana/dashboards/
```

### Loki Not Receiving Logs

```bash
# Check Promtail logs
docker compose -f docker-compose.observability.yml logs promtail

# Verify Promtail can access Docker socket
docker exec thestox-promtail ls -la /var/run/docker.sock

# Test Loki API
curl http://localhost:3100/ready
```

## 📊 Example Queries

### PromQL (Prometheus)

```promql
# Percentage of budget remaining
100 * sec_groq_budget_remaining_tokens{service="summarizer"} /
  (sec_groq_budget_usage_tokens{service="summarizer"} + sec_groq_budget_remaining_tokens{service="summarizer"})

# Jobs deferred in last hour
rate(sec_groq_budget_deferred_jobs_total[1h])

# Average download latency
rate(sec_edgar_download_duration_seconds_sum[5m]) / rate(sec_edgar_download_duration_seconds_count[5m])

# Filing discovery rate by form type
sum by (form_type) (rate(sec_edgar_filings_discovered_total[5m]))
```

### LogQL (Loki)

```logql
# All logs from backend service
{service="backend"}

# Error logs from all services
{} |= "ERROR"

# Summarization worker logs
{service="backend"} |= "summarization"

# Budget exhaustion events
{service="backend"} |= "budget exhausted"

# Parse logs as JSON and filter
{service="backend"} | json | level="ERROR"
```

## 🔐 Security Considerations

### Production Deployment

Before deploying to production:

1. **Change default Grafana password:**
   ```bash
   # Edit .env file
   GRAFANA_ADMIN_PASSWORD=your-secure-password
   ```

2. **Enable authentication for Prometheus:**
   - Add HTTP basic auth via reverse proxy (nginx, Traefik)
   - Use Prometheus native auth (requires config changes)

3. **Secure Loki:**
   - Enable `auth_enabled: true` in `loki.yml`
   - Configure tenant ID management
   - Use reverse proxy for access control

4. **Network isolation:**
   - Consider using a separate observability network
   - Restrict port exposure (bind to 127.0.0.1 only)

5. **TLS/SSL:**
   - Terminate SSL at reverse proxy
   - Use valid certificates (Let's Encrypt)

## 🧹 Maintenance

### Stopping Services

```bash
# Stop all observability services
docker compose -f docker-compose.observability.yml down

# Stop and remove volumes (will delete metrics and logs)
docker compose -f docker-compose.observability.yml down -v
```

### Updating Services

```bash
# Pull latest images
docker compose -f docker-compose.observability.yml pull

# Recreate containers with new images
docker compose -f docker-compose.observability.yml up -d
```

### Backup and Restore

#### Prometheus Data

```bash
# Backup
docker run --rm -v ops_compose_observability_prometheus-data:/data -v $(pwd):/backup alpine tar czf /backup/prometheus-backup.tar.gz /data

# Restore
docker run --rm -v ops_compose_observability_prometheus-data:/data -v $(pwd):/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/prometheus-backup.tar.gz -C /"
```

#### Grafana Data

```bash
# Backup
docker run --rm -v ops_compose_observability_grafana-data:/data -v $(pwd):/backup alpine tar czf /backup/grafana-backup.tar.gz /data

# Restore
docker run --rm -v ops_compose_observability_grafana-data:/data -v $(pwd):/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/grafana-backup.tar.gz -C /"
```

## 📚 Further Reading

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Loki Documentation](https://grafana.com/docs/loki/latest/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [LogQL Guide](https://grafana.com/docs/loki/latest/logql/)

## 🤝 Contributing

To add new metrics or dashboards:

1. Expose metrics in application code (using Prometheus client library)
2. Update `prometheus.yml` if new scrape target needed
3. Create/update Grafana dashboard
4. Export dashboard JSON and commit to `grafana/dashboards/`
5. Document new metrics in this README

## 📝 Notes

- The observability stack is designed to run alongside the main TheStox stack
- All services use the `secnet` network (external, created by main stack)
- Metrics are retained for 30 days in Prometheus
- Logs are retained for 7 days in Loki
- Dashboards are automatically provisioned on Grafana startup
