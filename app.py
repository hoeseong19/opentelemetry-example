from flask import Flask, request
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.propagate import inject, extract, set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
import requests
import os

# OpenTelemetry 설정
resource = Resource(attributes={
    ResourceAttributes.SERVICE_NAME: "example-flask-app"
})

# OTLP exporter 설정
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector:4317"),
    insecure=True
)

trace.set_tracer_provider(TracerProvider(resource=resource))
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# TraceContext 프로파게이터 설정
set_global_textmap(TraceContextTextMapPropagator())

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

tracer = trace.get_tracer(__name__)

@app.route("/")
def hello():
    with tracer.start_as_current_span("hello") as span:
        span.set_attribute("custom.attribute", "Hello World")
        return "Hello, World!"

@app.route("/api")
def api():
    with tracer.start_as_current_span("api_request") as span:
        # 외부 API 호출
        headers = {}
        inject(headers)  # context propagation
        response = requests.get(
            "https://jsonplaceholder.typicode.com/todos/1",
            headers=headers
        )
        span.set_attribute("api.status_code", response.status_code)
        return f"API Response: {response.json()}"

@app.route("/parent")
def parent():
    with tracer.start_as_current_span("parent") as parent_span:
        # Context 적용 호출
        headers = {}
        inject(headers)  # 현재 context를 헤더에 주입
        response_with_context = requests.get("http://localhost:5000/child_with_context", headers=headers)

        # Context 미적용 호출
        response_without_context = requests.get("http://localhost:5000/child_without_context")

        return f"With Context: {response_with_context.text}, Without Context: {response_without_context.text}"

@app.route("/child_with_context")
def child_with_context():
    context = extract(request.headers)
    with tracer.start_as_current_span("child_with_context", context=context) as span:
        return f"Child with context, Trace ID: {trace.get_current_span().get_span_context().trace_id:x}"

@app.route("/child_without_context")
def child_without_context():
    with tracer.start_as_current_span("child_without_context") as span:
        return f"Child without context, Trace ID: {trace.get_current_span().get_span_context().trace_id:x}"

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
