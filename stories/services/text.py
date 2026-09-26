"""Text-generation providers: turn story form inputs into a full outline
(title + per-page summary/text/illustration prompt) in a single structured
JSON call.

Provider selection is controlled by the ``TEXT_PROVIDER`` environment
variable:

- ``mock`` (default): deterministic, network-free generator used for local
  dev and the test suite so nothing requires a paid API key.
- ``openrouter``: calls the OpenRouter chat-completions API. Defaults to
  ``moonshotai/kimi-k2`` (Kimi K2), which is a good first candidate for this
  child-friendly, short-story task; swap ``OPENROUTER_MODEL`` to A/B test
  creativity against other models (e.g. ``anthropic/claude-3.5-sonnet``,
  ``openai/gpt-4o-mini``, ``google/gemini-2.0-flash-001``) without touching
  code.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import requests

READING_LEVEL_GUIDANCE = {
    "toddler": "very simple words and only a few words per page, for ages 0-2",
    "beginner": "very short sentences (5-8 words), simple everyday vocabulary, for ages 3-5",
    "early-reader": "short sentences and paragraphs, familiar vocabulary with a little challenge, for ages 6-9",
    "confident-reader": "richer vocabulary and longer paragraphs, for ages 10+",
}

PAGE_COUNT_BY_READING_LEVEL = {
    "toddler": 4,
    "beginner": 5,
    "early-reader": 6,
    "confident-reader": 8,
}

DEFAULT_PAGE_COUNT = 6

GENDER_PRONOUNS = {
    "girl": ("she", "her", "her", "a girl"),
    "boy": ("he", "him", "his", "a boy"),
    "nonbinary": ("they", "them", "their", "a child"),
    "unspecified": ("they", "them", "their", "a child"),
}


class TextGenerationError(Exception):
    """Raised when a text provider cannot produce a usable story outline."""


@dataclass
class GeneratedPage:
    page_number: int
    summary: str
    text: str
    image_prompt: str


@dataclass
class GeneratedStory:
    title: str
    pages: list


def page_count_for(reading_level: str) -> int:
    return PAGE_COUNT_BY_READING_LEVEL.get(reading_level, DEFAULT_PAGE_COUNT)


def _build_prompt(story, page_count: int):
    level_guidance = READING_LEVEL_GUIDANCE.get(
        story.reading_level, READING_LEVEL_GUIDANCE["early-reader"]
    )
    subject, obj, possessive, noun = GENDER_PRONOUNS.get(
        getattr(story, "child_gender", "unspecified"), GENDER_PRONOUNS["unspecified"]
    )
    system_prompt = (
        "You are a warm, imaginative children's book author and illustrator "
        "art director. You always respond with a single valid JSON object and "
        "nothing else: no markdown, no code fences, no commentary."
    )
    user_prompt = f"""Write a personalized, wholesome children's storybook.

Child's name: {story.child_name}
Child's gender: {noun} (use the pronouns {subject}/{obj}/{possessive} consistently in the story text)
Child's appearance (keep this consistent in every illustration prompt): {story.child_appearance}
Favorite theme/animal: {story.favorite_theme}
Moral or lesson the story should teach: {story.moral_lesson}
Reading level: {story.reading_level} ({level_guidance})
Number of pages: {page_count}

Respond with ONLY a JSON object matching exactly this shape:
{{
  "title": "<short, delightful story title>",
  "pages": [
    {{
      "page_number": 1,
      "summary": "<one sentence beat of what happens on this page>",
      "text": "<the full page text a child would read, matching the reading level, using the correct pronouns above>",
      "image_prompt": "<a vivid illustration prompt for a single children's-book-style image capturing this page, always explicitly describing {story.child_name} as {noun} using their appearance details above, no on-image text or words>"
    }}
  ]
}}

The "pages" array must contain exactly {page_count} entries, numbered 1 to {page_count} in order,
telling one complete story arc that ends with the moral above naturally woven in."""
    return system_prompt, user_prompt


def _extract_json(content: str) -> dict:
    cleaned = content.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned.strip()).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise TextGenerationError(f"Model response did not contain JSON: {content[:300]!r}")
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise TextGenerationError(f"Model response was not valid JSON: {exc}") from exc


def _to_generated_story(data: dict, expected_page_count: int) -> GeneratedStory:
    title = (data.get("title") or "").strip()
    raw_pages = data.get("pages") or []
    if not title or not isinstance(raw_pages, list) or not raw_pages:
        raise TextGenerationError("Model response was missing a title or pages")

    pages = []
    for index, raw_page in enumerate(raw_pages[:expected_page_count], start=1):
        pages.append(
            GeneratedPage(
                page_number=raw_page.get("page_number", index) or index,
                summary=str(raw_page.get("summary", "")).strip(),
                text=str(raw_page.get("text", "")).strip(),
                image_prompt=str(raw_page.get("image_prompt", "")).strip(),
            )
        )
    return GeneratedStory(title=title, pages=pages)


class MockTextProvider:
    """Deterministic, offline story generator used for dev/tests."""

    name = "mock"

    def generate_story(self, story, page_count: int) -> GeneratedStory:
        _, _, _, noun = GENDER_PRONOUNS.get(
            getattr(story, "child_gender", "unspecified"), GENDER_PRONOUNS["unspecified"]
        )
        pages = []
        for page_number in range(1, page_count + 1):
            pages.append(
                GeneratedPage(
                    page_number=page_number,
                    summary=f"{story.child_name} has an adventure with {story.favorite_theme} (page {page_number}).",
                    text=(
                        f"{story.child_name} took another step into the world of {story.favorite_theme}. "
                        f"Page {page_number} of {page_count}: a little more of the lesson '{story.moral_lesson}' "
                        "became clear."
                    ),
                    image_prompt=(
                        f"Children's book illustration of {story.child_name}, {noun}, ({story.child_appearance}) "
                        f"surrounded by {story.favorite_theme}, warm colorful watercolor style, page {page_number}, "
                        "no text or words in the image"
                    ),
                )
            )
        return GeneratedStory(title=f"{story.child_name} and the {story.favorite_theme.title()}", pages=pages)


class OpenRouterTextProvider:
    """Calls the OpenRouter chat-completions API (https://openrouter.ai/docs)."""

    name = "openrouter"

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("OPENROUTER_MODEL", "moonshotai/kimi-k2")
        self.base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.timeout = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "60"))
        self.temperature = float(os.environ.get("OPENROUTER_TEMPERATURE", "0.9"))

    def generate_story(self, story, page_count: int) -> GeneratedStory:
        if not self.api_key:
            raise TextGenerationError("OPENROUTER_API_KEY is not set")

        system_prompt, user_prompt = _build_prompt(story, page_count)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        referer = os.environ.get("OPENROUTER_SITE_URL")
        title = os.environ.get("OPENROUTER_SITE_NAME")
        if referer:
            headers["HTTP-Referer"] = referer
        if title:
            headers["X-Title"] = title

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TextGenerationError(f"OpenRouter request failed: {exc}") from exc

        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TextGenerationError(f"Unexpected OpenRouter response shape: {body}") from exc

        data = _extract_json(content)
        return _to_generated_story(data, page_count)


def get_text_provider():
    provider_name = os.environ.get("TEXT_PROVIDER", "mock").lower()
    if provider_name == "openrouter":
        return OpenRouterTextProvider()
    if provider_name == "mock":
        return MockTextProvider()
    raise TextGenerationError(f"Unknown TEXT_PROVIDER: {provider_name!r}")
