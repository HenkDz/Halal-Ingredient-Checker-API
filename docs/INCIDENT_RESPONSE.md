# Incident Response Procedures

## Halal Check API — Operations Runbook

---

## 1. Alert Severity Levels

| Level | Condition | Response Time |
|-------|-----------|---------------|
| **CRITICAL** | API completely down (consecutive failures >= 5) | Immediate (within 5 min) |
| **HIGH** | Error rate > 10%, or consecutive failures >= 3 | Within 15 minutes |
| **WARNING** | Error rate > 5%, or latency > 2s | Within 30 minutes |
| **INFO** | Recovered from degradation | Next business hours |

---

## 2. Common Incident Scenarios

### 2.1 API Completely Down

**Symptoms:** Health check returns connection refused / timeout. All endpoints return 502/504.

**Diagnosis:**
```bash
# Check if the process is running
docker ps | grep halal-check
# or
ps aux | grep uvicorn

# Check server logs
docker logs halal-check-api --tail 100
# or
journalctl -u halal-check-api --since "1 hour ago"

# Check if port is listening
ss -tlnp | grep 8000

# Check system resources
free -h
df -h
top -bn1 | head -20
```

**Resolution:**
1. If process crashed, restart: `docker restart halal-check-api`
2. If OOM killed, check memory usage and increase limits
3. If disk full, clear logs/temp files
4. Check for recent deployments that may have introduced a bug

### 2.2 High Error Rate (> 5%)

**Symptoms:** Mix of 200 and 5xx responses. Some requests succeed, others fail.

**Diagnosis:**
```bash
# Check recent error logs
docker logs halal-check-api --tail 500 | grep -i error

# Check if external API (Open Food Facts) is having issues
curl -s -o /dev/null -w "%{http_code}" "https://world.openfoodfacts.org/api/v2/product/3017620422003.json"

# Check rate limiter stats
curl -s http://localhost:8000/api/v1/auth/usage
```

**Resolution:**
1. **OFF API down:** Barcode/product endpoints will degrade gracefully (502). Ingredient endpoints are unaffected. Wait for OFF to recover — cached results still serve.
2. **Database issue:** Check ingredient/product JSON files are intact.
3. **Rate limiter issue:** Restart clears in-memory state.
4. **Auth store issue:** Restart clears in-memory user store (acceptable for MVP).

### 2.3 High Latency (> 2s)

**Symptoms:** All responses are slow. Health check takes > 2s.

**Diagnosis:**
```bash
# Check response time directly
curl -o /dev/null -s -w "time_total: %{time_total}s\n" http://localhost:8000/api/v1/health

# Check if it's OFF causing slowdown
curl -o /dev/null -s -w "time_total: %{time_total}s\n" "https://world.openfoodfacts.org/api/v2/product/3017620422003.json"

# Check system load
uptime
iostat -x 1 3
```

**Resolution:**
1. **OFF latency:** Barcode endpoints will be slow but ingredient endpoints are fast. Consider increasing OFF timeout or adding circuit breaker.
2. **System resources:** Check CPU, memory, disk I/O.
3. **Connection pool exhaustion:** Restart the service.
4. **Gunicorn worker starvation:** Check worker count, increase if needed.

### 2.4 Open Food Facts API Down

**Impact:**
- `/api/v1/barcode/*` — Returns 502 Bad Gateway
- `/api/v1/barcode/batch` — Returns partial results (errors for OFF-dependent items)
- `/api/v1/ingredient/*` — **UNAFFECTED** (local DB)
- `/api/v1/check` — **UNAFFECTED** (local DB)
- `/api/v1/products/*` — **UNAFFECTED** (local DB)
- `/api/v1/health` — **UNAFFECTED**

**Resolution:**
1. Check OFF status: https://status.openfoodfacts.org/
2. Cached results (24h TTL) continue to serve known products
3. No action needed for ingredient/product endpoints
4. Monitor OFF recovery — service auto-recovers

---

## 3. Communication Protocol

### During Active Incident:
1. Acknowledge alert within **5 minutes** (CRITICAL) or **15 minutes** (HIGH)
2. Update status within **30 minutes** with:
   - Current impact
   - Root cause (if known)
   - ETA for resolution
3. Send all-clear when resolved with:
   - Root cause summary
   - Actions taken
   - Preventive measures

### Post-Incident:
1. Write incident report within **24 hours**
2. Include: timeline, root cause, impact, resolution, prevention
3. Update this runbook if new scenario discovered

---

## 4. Monitoring Setup

### Health Check Endpoint
```
GET /api/v1/health
```
Returns: `{"status": "ok", "version": "0.5.0", "database_entries": N}`

### Monitoring Configuration
- **Check interval:** Every 60 seconds
- **Alert: API Down** — 3 consecutive failures → alert within 5 min
- **Alert: Error Rate** — > 5% over rolling window → alert within 30 min
- **Alert: Latency** — > 2s per-check → alert within 15 min
- **Weekly Report** — Auto-generated every Monday at 00:00 UTC

### Running the Monitor

```bash
# As a daemon
python -m monitoring.run

# Single check
python -m monitoring.run --once

# Generate report
python -m monitoring.run --report

# With webhook alerts
WEBHOOK_URL=https://hooks.slack.com/services/xxx python -m monitoring.run

# With email alerts
SMTP_HOST=smtp.gmail.com SMTP_USER=xxx@gmail.com SMTP_PASSWORD=app-password \
SMTP_TO=oncall@example.com python -m monitoring.run
```

### Cron Job for Weekly Reports

```cron
# Every Monday at 00:00 UTC — generate weekly report
0 0 * * 1 cd /path/to/project && python -m monitoring.run --report >> /var/log/halal-check-monitor.log 2>&1

# Every 5 minutes — single check (alternative to daemon)
*/5 * * * * cd /path/to/project && python -m monitoring.run --once >> /var/log/halal-check-monitor.log 2>&1
```

---

## 5. Escalation Path

1. **Automated alerts** → Console log + Webhook/Email (if configured)
2. **No response in 15 min** → Page on-call engineer
3. **No response in 30 min** → Escalate to team lead
4. **Production data at risk** → Immediate escalation regardless of time

---

## 6. Recovery Checklist

After any incident, verify:

- [ ] Health endpoint returns 200
- [ ] Ingredient lookup works: `POST /api/v1/check` with known ingredients
- [ ] Barcode lookup works: `GET /api/v1/barcode/3017620422003`
- [ ] Batch endpoint works (if pro tier): `POST /api/v1/barcode/batch`
- [ ] Auth endpoints work: `POST /api/v1/auth/register`
- [ ] Response times are back to normal (< 500ms for local endpoints)
- [ ] Error rate is back below 1%
- [ ] Monitoring alerts have cleared
