import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from autopatch.utils.secrets import get_secret

# Phoenix Cloud endpoint
PHOENIX_ENDPOINT = "https://app.phoenix.arize.com/v1/traces"


def setup_phoenix_tracing(project_name: str = "autopatch") -> trace.Tracer:
    """
    Sets up OpenTelemetry tracing to send all agent
    decisions to Arize Phoenix Cloud.

    Every tool call, every Gemini decision, every MR
    creation gets recorded as a span inside a trace.
    This is what lets us replay exactly what AutoPatch
    did and why.

    Args:
        project_name: Phoenix project to send traces to

    Returns:
        A tracer instance ready to use
    """
    print("🔭 Setting up Arize Phoenix tracing...")

    # Get Phoenix API key from Secret Manager
    phoenix_api_key = get_secret("arize-phoenix-api-key")

    # Configure the OTLP exporter to send traces to Phoenix Cloud
    exporter = OTLPSpanExporter(
        endpoint=PHOENIX_ENDPOINT,
        headers={
            "api_key": phoenix_api_key,
            "project": project_name,
        }
    )

    # Set up the tracer provider with batch processing
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument Google ADK — this automatically traces
    # every Gemini call and tool invocation without extra code
    GoogleADKInstrumentor().instrument()

    print(f"✅ Phoenix tracing active → project: {project_name}")
    print(f"   View traces at: https://app.phoenix.arize.com/s/likhith0715/projects")

    return trace.get_tracer(project_name)


def create_span(tracer, span_name: str, attributes: dict = None):
    """
    Creates a custom span for tracking a specific
    AutoPatch action like "detect_schema_drift" or
    "calculate_business_impact".

    Use as a context manager:
        with create_span(tracer, "detect_drift", {...}) as span:
            # your code here

    Args:
        tracer: The tracer instance from setup_phoenix_tracing
        span_name: Name of this action e.g. "detect_schema_drift"
        attributes: Extra metadata to attach to this span

    Returns:
        A span context manager
    """
    span = tracer.start_span(span_name)

    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, str(value))

    return span
