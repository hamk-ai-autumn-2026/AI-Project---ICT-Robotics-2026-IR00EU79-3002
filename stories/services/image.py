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

ART_STYLE_GUIDANCE = {
    "watercolor": "warm watercolor children's-book illustration, soft washes and gentle colors",
    "pencil": "hand-drawn pencil illustration, visible graphite lines, delicate cross-hatching, softly colored details",
    "anime": "semi-realistic anime illustration, expressive faces, cinematic light, richly painted backgrounds, original character design",
    "3d-animation": "polished 3D animated family-film illustration, appealing expressive characters, tactile materials, cinematic soft lighting",
}


def apply_art_style(prompt: str, art_style: str) -> str:
    """Add the selected visual direction to every generated image prompt."""
    guidance = ART_STYLE_GUIDANCE.get(art_style, ART_STYLE_GUIDANCE["watercolor"])
    return f"{prompt.rstrip('. ')}. Visual style: {guidance}. Keep the same style across the storybook."


class ImageGenerationError(Exception):
    """Raised when an image provider cannot produce an image."""


class MockImageProvider:
    """Deterministic, offline placeholder used for dev/tests."""

    name = "mock"

    def generate_image(self, prompt: str, reference_photo: str | None = None) -> dict:
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
        self.reference_model = os.environ.get("FAL_REFERENCE_MODEL", "fal-ai/flux-pro/kontext")
        self._reference_url = None

    def generate_image(self, prompt: str, reference_photo: str | None = None) -> dict:
        if not self.api_key:
            raise ImageGenerationError("FAL_KEY is not set")

        model = self.reference_model if reference_photo else self.model
        payload = {"prompt": prompt}
        # Only flux-family models expose `image_size`; other models (Seedream,
        # Nano Banana Pro) use different sizing params with sane defaults, so
        # we only set it for models known to accept it.
        if "flux" in model and not reference_photo:
            payload["image_size"] = self.image_size
        if reference_photo:
            try:
                import fal_client

                if not self._reference_url:
                    self._reference_url = fal_client.upload_file(reference_photo)
                payload["image_url"] = self._reference_url
            except Exception as exc:
                raise ImageGenerationError(f"fal.ai reference photo upload failed: {exc}") from exc

        try:
            response = requests.post(
                f"{FAL_BASE_URL}/{model}",
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
        return {"url": images[0]["url"], "provider": f"fal:{model}"}


def get_image_provider():
    provider_name = os.environ.get("IMAGE_PROVIDER", "mock").lower()
    if provider_name == "fal":
        return FalImageProvider()
    if provider_name == "mock":
        return MockImageProvider()
    raise ImageGenerationError(f"Unknown IMAGE_PROVIDER: {provider_name!r}")
