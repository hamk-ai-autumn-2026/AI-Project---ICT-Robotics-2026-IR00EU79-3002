"""Orchestrates the full "planned AI pipeline" from the README:

1. Generate a story outline (title + per-page summary/text/illustration
   prompt) with the configured text provider.
2. Persist a `Page` row for each outline beat.
3. Generate an illustration for each page's image prompt with the
   configured image provider and persist it as an `Asset`.

Runs inside a Celery worker and updates `Story.status` as it goes, so the
frontend can poll `/api/stories/<id>/` for progress.
"""

from __future__ import annotations

import logging

from django.db import transaction

from ..models import Asset, Page, Story
from .image import ImageGenerationError, apply_art_style, get_image_provider
from .text import TextGenerationError, get_text_provider, page_count_for

logger = logging.getLogger(__name__)


class StoryGenerationError(Exception):
    """Raised when the pipeline cannot complete generation for a story."""


def generate_story_content(story: Story, retry_only: bool = False) -> Story:
    """Run the outline -> pages -> images pipeline for `story`, in place.

    Safe to call more than once. Initial generation replaces the outline;
    image retries can preserve completed pages and only fill missing assets.
    """
    story.status = "GENERATING"
    story.error_message = ""
    story.save(update_fields=["status", "error_message", "updated_at"])

    pages_exist = story.pages.exists()
    if not (retry_only and pages_exist and story.failed_stage == "image"):
        text_provider = get_text_provider()
        page_count = page_count_for(story.reading_level)
        try:
            outline = text_provider.generate_story(story, page_count)
        except TextGenerationError as exc:
            logger.warning("Text generation failed for story %s: %s", story.id, exc)
            story.status = "FAILED"
            story.failed_stage = "text"
            story.error_message = f"Story text generation failed: {exc}"
            story.save(update_fields=["status", "failed_stage", "error_message", "updated_at"])
            raise StoryGenerationError(str(exc)) from exc

        with transaction.atomic():
            story.title = outline.title
            story.pages.all().delete()
            pages = [
                Page(
                    story=story,
                    page_number=generated_page.page_number,
                    summary=generated_page.summary,
                    text=generated_page.text,
                    image_prompt=generated_page.image_prompt,
                )
                for generated_page in outline.pages
            ]
            Page.objects.bulk_create(pages)
            story.status = "OUTLINE_READY"
            story.failed_stage = ""
            story.save(update_fields=["title", "status", "failed_stage", "updated_at"])

    image_provider = get_image_provider()
    had_image_failure = False
    for page in story.pages.all():
        if not page.image_prompt:
            continue
        if retry_only and hasattr(page, "asset"):
            continue
        try:
            result = image_provider.generate_image(
                apply_art_style(page.image_prompt, story.art_style),
                reference_photo=story.reference_photo.path if story.reference_photo else None,
            )
        except ImageGenerationError as exc:
            logger.warning("Image generation failed for page %s: %s", page.id, exc)
            page.moderation_flag = False
            had_image_failure = True
            continue
        Asset.objects.update_or_create(
            page=page,
            defaults={
                "url": result["url"],
                "provider": result["provider"],
                "storage_path": "",
            },
        )

    story.refresh_from_db()
    story.status = "FAILED" if had_image_failure else "COMPLETE"
    if had_image_failure:
        story.failed_stage = "image"
        story.error_message = "One or more page illustrations failed to generate."
    else:
        story.failed_stage = ""
    story.save(update_fields=["status", "error_message", "updated_at"])
    if had_image_failure:
        raise StoryGenerationError(story.error_message)
    return story
