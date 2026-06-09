import os
from opentelemetry import trace
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from autopatch.utils.secrets import get_secret


def setup_phoenix_tracing(project_name: str = "autopatch") -> trace.Tracer:
    """Sets up Arize Phoenix tracing using phoenix.otel.register."""
    print("🔭 Setting up Arize Phoenix tracing...")

    phoenix_api_key = get_secret("arize-phoenix-api-key")

    # Set environment variables for OTLP export
    os.environ["PHOENIX_CLIENT_HEADERS"] = f"api_key={phoenix_api_key}"
    os.environ["PHOENIX_PROJECT_NAME"] = project_name

    from phoenix.otel import register
    tracer_provider = register(
        project_name=project_name,
        endpoint="https://app.phoenix.arize.com/v1/traces",
        batch=True,
    )

    try:
        GoogleADKInstrumentor().instrument(tracer_provider=tracer_provider)
    except Exception:
        pass

    print(f"✅ Phoenix tracing active → project: {project_name}")
    print(f"   View: https://app.phoenix.arize.com/s/likhith0715/projects")

    return tracer_provider.get_tracer(project_name)
