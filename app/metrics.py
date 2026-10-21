"""Metrics about what the app does, scraped from the API at /metrics/ along with
the request counter in api.py. The dashboard in monitoring/grafana/dashboards
graphs both."""

from prometheus_client import Counter

ITEMS_POSTED = Counter("seekr_items_posted", "Items posted, by lost or found", ["type"])
MATCHES_CONFIRMED = Counter("seekr_matches_confirmed", "Lost/found pairs confirmed as a match")

# Create both label values now so each series reads 0 instead of being missing.
for item_type in ("lost", "found"):
    ITEMS_POSTED.labels(item_type)
