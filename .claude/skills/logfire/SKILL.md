---
name: logfire
description: >
  Structured observability with Pydantic Logfire and OpenTelemetry. Use when adding traces/logs to Python APIs,
  instrumenting FastAPI, HTTPX, SQLAlchemy, or LLMs, setting up service metadata,
  configuring sampling or scrubbing sensitive data, or testing observability code.
user-invokable: false
---

# Logfire

Structured observability for Python using Pydantic Logfire - fast setup, powerful features, OpenTelemetry-compatible.

## Quick Start

```bash
uv pip install logfire
```

```python
import logfire

logfire.configure(service_name="my-api", service_version="1.0.0")
logfire.info("Application started")
```

## Core Patterns

### 1. Service Configuration

Always set service metadata at startup:

```python
logfire.configure(
    service_name="backend",
    service_version="1.0.0",
    environment="production",
    console=False,
    send_to_logfire=True,
)
```

### 2. Framework Instrumentation

Instrument frameworks **before** creating clients/apps:

```python
logfire.configure(service_name="backend")
logfire.instrument_fastapi()
logfire.instrument_httpx()
logfire.instrument_sqlalchemy()

app = FastAPI()
```

### 3. Log Levels and Structured Logging

```python
logfire.trace("Detailed trace", step=1)
logfire.debug("Debug context", variable=locals())
logfire.info("User action", action="login", success=True)
logfire.warn("Potential issue", threshold_exceeded=True)
logfire.error("Operation failed", error_code=500)
logfire.fatal("Critical failure", component="database")

# Exception logging with automatic traceback
try:
    risky_operation()
except Exception:
    logfire.exception("Operation failed", context="extra_info")
```

### 4. Manual Spans

```python
with logfire.span("Process order {order_id}", order_id="ORD-123"):
    logfire.info("Validating cart")
    logfire.info("Order complete")

with logfire.span("Database query") as span:
    results = execute_query()
    span.set_attribute("result_count", len(results))
```

### 5. Custom Metrics

```python
request_counter = logfire.metric_counter("http.requests", unit="1")
request_counter.add(1, {"endpoint": "/api/users", "method": "GET"})

temperature = logfire.metric_gauge("temperature", unit="°C")
temperature.set(23.5)

latency = logfire.metric_histogram("request.duration", unit="ms")
latency.record(45.2, {"endpoint": "/api/data"})
```

### 6. Suppress Noisy Instrumentation

```python
logfire.suppress_scopes("google.cloud.bigquery.opentelemetry_tracing")

with logfire.suppress_instrumentation():
    client.get("https://internal-healthcheck.local")
```

### 7. Sensitive Data Scrubbing

```python
logfire.configure(
    scrubbing=logfire.ScrubbingOptions(
        extra_patterns=["api_key", "secret", "token"]
    )
)
```

### 8. Testing

```python
from logfire.testing import CaptureLogfire

def test_user_creation(capfire: CaptureLogfire):
    create_user("Alice", "alice@example.com")
    spans = capfire.exporter.exported_spans
    assert len(spans) >= 1
    capfire.exporter.clear()
```

## Common Pitfalls

| Issue | Symptom | Fix |
|-------|---------|-----|
| Missing service name | Spans hard to find in UI | Set `service_name` in `configure()` |
| Late instrumentation | No spans captured | Call `configure()` before creating clients |
| High-cardinality attrs | Storage explosion | Use IDs, not full payloads as attributes |
| Console noise | Logs pollute stdout | Set `console=False` in production |

## Additional Resources

- For complete configuration options, see [references/configuration.md](references/configuration.md)
- For framework-specific setup, see [references/integrations.md](references/integrations.md)
- For metrics details, see [references/metrics.md](references/metrics.md)
- For sampling, scrubbing, suppression, testing, see [references/advanced.md](references/advanced.md)
- For troubleshooting, see [references/pitfalls.md](references/pitfalls.md)
- [Official Docs](https://logfire.pydantic.dev/docs/)
