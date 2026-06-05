import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from autopatch.utils.secrets import get_secret

PHOENIX_ENDPOINT = "https://app.phoenix.arize.com/v1/traces"


def setup_phoenix_tracing(project_name: str = "autopatch") -> trace.Tracer:
    """
    Sets up OpenTelemetry tracing to send all agent
    decisions to Arize Phoenix Cloud.
    """
    print("🔭 Setting up Arize Phoenix tracing...")

    phoenix_api_key = get_secret("arize-phoenix-api-key")

    # Phoenix Cloud uses Authorization Bearer header format
    exporter = OTLPSpanExporter(
        endpoint=PHOENIX_ENDPOINT,
        headers={
            "Authorization": f"Bearer {phoenix_api_key}",
            "project": project_name,
        }
    )

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument Google ADK
    GoogleADKInstrumentor().instrument()

    print(f"✅ Phoenix tracing active → project: {project_name}")
    print(f"   View traces at: https://app.phoenix.arize.com/s/likhith0715/projects")

    return trace.get_tracer(project_name)
