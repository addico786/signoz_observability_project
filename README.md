# Local AI Agent Observability with SigNoz

A small offline-capable Python agent using Ollama, instrumented with OpenTelemetry and
observed through a self-hosted SigNoz installation. The project demonstrates trace
waterfalls, service-level metrics, a dashboard, and a repeatable OTLP ingestion check.

## What is included

- `my_project/agent.py` — interactive Ollama agent.
- `my_project/send_manual_trace.py` — standalone OTLP ingestion smoke test.
- `my_project/requirements.txt` — Python dependencies.
- `my_project/casting.yaml` and `casting.yaml.lock` — Foundry deployment configuration.
- `my_project/pours/deployment/compose.yaml` — generated SigNoz Compose deployment.

## Run it

Start SigNoz:

```powershell
cd my_project
docker compose -f pours/deployment/compose.yaml up -d
```

Verify the UI at `http://localhost:8080` and install dependencies:

```powershell
C:\Users\adnan\AppData\Local\Programs\Python\Python313\python.exe -m pip install -r requirements.txt
```

On this Windows/WSL setup, `localhost:4317` is intercepted by WSL forwarding. Export
to the host LAN address instead:

```powershell
$env:SIGNOZ_OTLP_ENDPOINT="192.168.1.39:4317"
C:\Users\adnan\AppData\Local\Programs\Python\Python313\python.exe send_manual_trace.py
C:\Users\adnan\AppData\Local\Programs\Python\Python313\python.exe agent.py
```

Ask normal and time-related questions. Each request emits an `agent_request` root span;
every request has a `call_llm` child span and time requests additionally have a
`tool.get_time` child span. `call_llm` records model, prompt length, duration, and
response length attributes.

## Verification

1. `docker ps` shows `signoz-signoz-0` healthy and the `ingester` exposes 4317/4318.
2. `http://localhost:8080/api/v1/health` returns `{"status":"ok"}`.
3. Run `send_manual_trace.py`; in SigNoz, the service
   `signoz-ingestion-smoke-test` appears.
4. Run the agent with at least one question containing `time`; in Traces, verify the
   parent/child span hierarchy and attributes above.
5. Open **Local AI Agent Observability** in Dashboards to inspect the saved panels.

## AI-use disclosure

This project used AI coding assistants (Claude and Codex) for planning, debugging,
instrumentation, and documentation. All runtime checks listed above were performed on
the local deployment.


