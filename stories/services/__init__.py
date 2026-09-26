"""AI pipeline services: text (outline/page) generation and image generation.

Providers are selected at runtime via environment variables so the same code
can run against a real API or a network-free mock during local dev/tests.
See `text.py` and `image.py` for the provider interfaces, and `pipeline.py`
for the orchestration that ties them together and persists results.
"""
