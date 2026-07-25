"""
Tiny local AI agent, instrumented with OpenTelemetry so every step
shows up as a trace in SigNoz.

Flow: ask a question -> (maybe call a tool) -> ask local LLM (via Ollama) -> print answer
"""

import os
import sys
import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
import requests

# --- OpenTelemetry setup ("installing the cameras") ---
# This tells the app: package up trace data and ship it to the OTel
# collector that Foundry started for you, listening on localhost:4317.
resource = Resource(attributes={"service.name": "my-local-agent"})
provider = TracerProvider(resource=resource)
OTLP_ENDPOINT = os.getenv("SIGNOZ_OTLP_ENDPOINT", "localhost:4317")
exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("agent.tracer")

# --- Ollama config ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
# Set MODEL_NAME to an entry from `ollama list`, or pass it at launch, e.g.
# MODEL_NAME=llama3.2:3b python agent.py.
MODEL_NAME = os.getenv("MODEL_NAME", "DeepSeek-R1:1.5b")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120"))


def call_local_llm(prompt: str) -> str:
    """Sends a prompt to your local Ollama model. Wrapped in its own span
    so SigNoz shows exactly how long the model took and how big the reply was."""
    with tracer.start_as_current_span("call_llm") as span:
        span.set_attribute("llm.model", MODEL_NAME)
        span.set_attribute("llm.prompt_length", len(prompt))

        start = time.time()
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("response", "")
            if not isinstance(answer, str):
                raise ValueError("Ollama returned a non-string response")
            span.set_attribute("llm.response_length", len(answer))
            return answer
        except (requests.RequestException, ValueError) as exc:
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            span.set_attribute("error.type", type(exc).__name__)
            raise
        finally:
            span.set_attribute("llm.duration_seconds", round(time.time() - start, 3))


def get_time_tool() -> str:
    """A deliberately trivial 'tool' the agent can call. Its own span shows
    up as a separate step in the trace, before the LLM call."""
    with tracer.start_as_current_span("tool.get_time") as span:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        span.set_attribute("tool.name", "get_time")
        span.set_attribute("tool.result", now)
        return now


def run_agent(user_question: str) -> str:
    """The top-level span. Everything above (tool call, LLM call) becomes
    a child of this one, which is what gives you the nice waterfall view."""
    with tracer.start_as_current_span("agent_request") as span:
        span.set_attribute("user.question", user_question)

        if "time" in user_question.lower():
            tool_result = get_time_tool()
            # The model is still called so this request has the complete
            # tool -> LLM trace.  DeepSeek can otherwise ignore a casual
            # time prefix and answer with its generic no-real-time disclaimer.
            prompt = f"""You are answering a user with an authoritative tool result.
Do not claim that you lack real-time access. Use the tool result below.

TOOL: get_time
TOOL RESULT: {tool_result}

User question: {user_question}

Reply in one short sentence that states the local time from TOOL RESULT."""
            llm_answer = call_local_llm(prompt).strip()

            # Keep the visible answer correct even if a small model ignores
            # the supplied tool context. The LLM call is still traced.
            if tool_result in llm_answer and "don't have" not in llm_answer.lower():
                answer = llm_answer
                span.set_attribute("agent.time_answer_source", "call_llm")
            else:
                answer = f"The current local time is {tool_result}."
                span.set_attribute("agent.time_answer_source", "tool_fallback")
        else:
            answer = call_local_llm(user_question)
            span.set_attribute("agent.answer_source", "call_llm")

        span.set_attribute("agent.answer_length", len(answer))
        return answer


if __name__ == "__main__":
    # Windows consoles may use a legacy encoding that cannot render model output such
    # as emoji. Replacing unsupported glyphs keeps the demo loop and trace export alive.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        print("Local agent ready. Type a question (or 'quit' to exit).")
        while True:
            q = input("> ")
            if q.lower() in ("quit", "exit"):
                break
            try:
                print(run_agent(q))
            except (requests.RequestException, ValueError) as exc:
                print(f"Request failed: {exc}")
    finally:
        # Ensure queued spans are sent even if terminal output fails unexpectedly.
        provider.shutdown()
