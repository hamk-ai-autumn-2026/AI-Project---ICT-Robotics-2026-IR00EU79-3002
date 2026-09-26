"""Image-generation providers, all built on fal.ai's synchronous REST API
(``https://fal.run/<model-id>``, ``Authorization: Key $FAL_KEY``).

Provider/model selection is controlled by environment variables:

- ``IMAGE_PROVIDER=mock`` (default): deterministic placeholder image URL,
  no network call, used for local dev and the test suite.
- ``IMAGE_PROVIDER=fal``: calls fal.ai. ``FAL_MODEL`` picks which model
  endpoint to hit:
    - ``fal-ai/flux/schnell`` (default): extremely fast (~0.76s) and cheap
      (~$0.003/megapixel), ideal for local iteration/testing.
    - ``bytedance/seedream/v5/pro/text-to-image`` (Seedream 5.0 Pro):
      relatively cheap, good default for production, generally unconcerned
      with copyrighted-IP-styled prompts.
    - ``fal-ai/nano-banana-pro`` (Google Nano Banana Pro): highest quality,
      most expensive; reserve for hero/production images.
"""

from __future__ import annotations

import os

import requests

FAL_BASE_URL = "https://fal.run"


class ImageGenerationError(Exception):
    """Raised when an image provider cannot produce an image."""


class MockImageProvider:
    """Deterministic, offline placeholder used for dev/tests."""

    name = "mock"

    def generate_image(self, prompt: str) -> dict:
        digest = abs(hash(prompt)) % 1000
        return {
            "url": f"https://picsum.photos/seed/storybook-{digest}/1024/1024",
            "provider": "mock",
        }


class FalImageProvider:
    """Calls a fal.ai text-to-image model over its synchronous REST API."""

    name = "fal"

    def __init__(self):
        self.api_key = os.environ.get("FAL_KEY", "")
        self.model = os.environ.get("FAL_MODEL", "fal-ai/flux/schnell")
        self.timeout = float(os.environ.get("FAL_TIMEOUT_SECONDS", "60"))
        self.image_size = os.environ.get("FAL_IMAGE_SIZE", "square_hd")

    def generate_image(self, prompt: str) -> dict:
        if not self.api_key:
            raise ImageGenerationError("FAL_KEY is not set")

        payload = {"prompt": prompt}
        # Only flux-family models expose `image_size`; other models (Seedream,
        # Nano Banana Pro) use different sizing params with sane defaults, so
        # we only set it for models known to accept it.
        if "flux" in self.model:
            payload["image_size"] = self.image_size

        try:
            response = requests.post(
                f"{FAL_BASE_URL}/{self.model}",
                headers={
                    "Authorization": f"Key {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ImageGenerationError(f"fal.ai request failed: {exc}") from exc

        body = response.json()
        images = body.get("images") or []
        if not images or not images[0].get("url"):
            raise ImageGenerationError(f"Unexpected fal.ai response shape: {body}")
        return {"url": images[0]["url"], "provider": f"fal:{self.model}"}


def get_image_provider():
    provider_name = os.environ.get("IMAGE_PROVIDER", "mock").lower()
    if provider_name == "fal":
        return FalImageProvider()
    if provider_name == "mock":
        return MockImageProvider()
    raise ImageGenerationError(f"Unknown IMAGE_PROVIDER: {provider_name!r}")
