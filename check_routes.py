"""Diagnostic script to check registered routes in the FastAPI app."""
import os

os.environ["EXEGESIS_AUTH_ALLOW_ANONYMOUS"] = "1"
os.environ["EXEGESIS_ALLOW_INSECURE_STARTUP"] = "1"
os.environ.setdefault("EXEGESIS_ENVIRONMENT", "development")

from exegesis.infrastructure.api.app.bootstrap import create_app

app = create_app()

print("Registered routes:")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = getattr(route, 'methods', set())
        print(f"  {methods} {route.path}")
    elif hasattr(route, 'path'):
        print(f"  {route.path}")

print(f"\nTotal routes: {len(app.routes)}")
