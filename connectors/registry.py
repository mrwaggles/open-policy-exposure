"""Shared registry loader: per-company source config lives in data/registry.json.
Connectors fall back to their hardcoded lists when the registry is absent."""
import json, os

def load():
    p = os.path.join(os.path.dirname(__file__), "..", "data", "registry.json")
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p)).get("companies", {})
    except Exception:
        return {}
