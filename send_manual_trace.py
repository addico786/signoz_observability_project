"""Send one standalone trace to verify SigNoz OTLP ingestion.

Set SIGNOZ_OTLP_ENDPOINT when localhost forwarding is intercepted by WSL, for example:
SIGNOZ_OTLP_ENDPOINT=192.168.1.39:4317 python send_manual_trace.py
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


endpoint = os.getenv("SIGNOZ_OTLP_ENDPOINT", "localhost:4317")
provider = TracerProvider(
    resource=Resource.create({"service.name": "signoz-ingestion-smoke-test"})
)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
tracer = provider.get_tracer("signoz.smoke-test")

with tracer.start_as_current_span("manual_ingestion_test") as span:
    span.set_attribute("test.kind", "manual-otlp-smoke-test")
    span.set_attribute("test.endpoint", endpoint)

provider.shutdown()
print(f"Exported manual_ingestion_test to {endpoint}")
