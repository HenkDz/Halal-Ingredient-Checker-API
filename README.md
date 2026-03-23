# Halal Check API

A production-ready REST API that checks whether food ingredients and products are **halal**, **haram**, or **doubtful**. Built with Python, FastAPI, and a curated ingredient database sourced from major halal certification bodies.

## Features

- **Ingredient checking** — look up individual ingredients or check entire lists by name or E-number
- **Barcode scanning** — scan any EAN/UPC barcode and get a full halal assessment via [Open Food Facts](https://world.openfoodfacts.org/) integration
- **Batch processing** — check up to 50 barcodes in a single request (Pro+)
- **Product search** — search a pre-indexed database of common brand products
- **Freemium model** — free tier for personal use, paid tiers for commercial apps
- **API key auth** — simple key-based authentication with hashed storage
- **Tiered rate limiting** — sliding-window counter with per-minute and daily caps
- **Polar.sh payments** — built-in subscription billing with webhook handling
- **Observability** — structured JSON logging (structlog), Sentry error tracking, Prometheus metrics
- **Health monitoring** — built-in daemon that pings `/health`, fires alerts, and generates weekly reports
- **Docker-ready** — multi-stage Alpine build, docker-compose with monitoring sidecar

## Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | FastAPI 0.115 |
| Runtime | Uvicorn + Gunicorn |
| Language | Python 3.12 |
| Payments | Polar.sh |
| Monitoring | structlog + Sentry + Prometheus |
| Containers | Docker (multi-stage Alpine) |
| CI/CD | GitHub Actions (pytest, ruff, mypy, bandit) |

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/your-org/halal-check-api.git
cd halal-check-api

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set HOST and PORT
```

### 3. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API is now live at `http://localhost:8000`. Interactive docs at `/docs` (Swagger UI) and `/redoc`.

### 4. With Docker

```bash
cp .env.example .env
docker compose up -d
```

## API Overview

All endpoints are under `/api/v1/`. Pass your API key via the `X-API-Key` header.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register and receive an API key |
| GET | `/auth/keys` | View your key info and tier |
| POST | `/auth/key/revoke` | Revoke your API key |
| GET | `/auth/usage` | Check current rate limit usage |
| POST | `/auth/subscribe` | Manually upgrade tier (demo) |
| POST | `/auth/subscribe/polar` | Start a Polar.sh checkout |

### Ingredients

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ingredient/{name}` | Look up a single ingredient |
| POST | `/check` | Check a list of ingredients |

### Barcode

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/barcode/{barcode}` | Scan a single barcode |
| POST | `/barcode/batch` | Scan up to 50 barcodes (Pro+) |

### Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/products/search?q=...` | Search product database |
| GET | `/products/stats` | Database statistics |
| GET | `/products/barcode/{barcode}` | Look up product by barcode |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth required) |

## Example Usage

### Register and get an API key

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "name": "Demo User"}'
```

### Check ingredients

```bash
curl http://localhost:8000/api/v1/check \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ingredients": ["gelatin", "sugar", "E120", "olive oil"]}'
```

Response:

```json
{
  "total": 4,
  "halal": 2,
  "haram": 2,
  "doubtful": 0,
  "unknown": 0,
  "overall_verdict": "haram",
  "results": [
    {"query": "gelatin", "verdict": "haram", "reason": "Usually derived from pork..."},
    {"query": "sugar", "verdict": "halal", "reason": "Pure sugar is halal."},
    {"query": "E120", "verdict": "haram", "reason": "Derived from crushed cochineal insects..."},
    {"query": "olive oil", "verdict": "halal", "reason": "Pure olive oil is halal."}
  ]
}
```

### Scan a barcode

```bash
curl http://localhost:8000/api/v1/barcode/3017620422003 \
  -H "X-API-Key: YOUR_KEY"
```

## Pricing Tiers

| | Free | Pro | Enterprise |
|--|------|-----|------------|
| Price | $0 | $9/mo or $79/yr | Custom |
| Daily requests | 100 | 10,000 | 1,000,000 |
| Per-minute limit | 10 | 100 | 500 |
| Single barcode scan | Yes | Yes | Yes |
| Batch scanning (up to 50) | No | Yes | Yes (200) |
| Detailed results | No | Yes | Yes |

## Ingredient Database

The database contains ingredients sourced from:

- **IFANCA** — Islamic Food and Nutrition Council of America
- **JAKIM** — Malaysian Department of Islamic Development
- **MUI** — Indonesian Ulema Council
- **Halal Monitoring Authority**

Each entry includes the verdict, reasoning, source references, and alternative names/E-numbers. The database covers common additives (E-numbers), emulsifiers, colorants, preservatives, and processing aids.

## Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI application, all endpoints
│   ├── auth.py              # API key auth & subscription management
│   ├── barcode.py           # Open Food Facts integration + parsing
│   ├── ratelimit.py         # Sliding-window rate limiter with tiers
│   ├── polar.py             # Polar.sh payment integration
│   └── observability.py     # Structured logging, Sentry, Prometheus
├── data/
│   ├── ingredients.py       # Ingredient lookup engine
│   ├── ingredients.json     # Ingredient database (~1500 entries)
│   ├── products.py          # Product search engine
│   └── products.json        # Pre-indexed product database (~10000 entries)
├── monitoring/
│   ├── run.py               # Monitoring daemon entry point
│   ├── health_monitor.py    # Health check pinger
│   ├── alerting.py          # Webhook + email alerts
│   └── weekly_report.py     # Weekly uptime/performance reports
├── tests/                   # pytest test suite
├── scripts/
│   └── setup_monitoring_cron.sh
├── Dockerfile               # Multi-stage Alpine build
├── docker-compose.yml       # App + monitoring stack
├── gunicorn.conf.py         # Production Gunicorn config
├── nginx.conf               # Reverse proxy config (optional)
├── .env.example             # Environment variable template
├── pyproject.toml           # Ruff, mypy, pytest, coverage config
└── requirements.txt         # Python dependencies
```

## Development

### Run tests

```bash
pip install -r requirements-dev.txt
pytest
```

### Lint and type-check

```bash
ruff check .
mypy app/ data/
bandit -r app/ data/
```

## License

MIT
