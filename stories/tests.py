import json
import hashlib
import re
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from .models import Asset, Page, Story
from .services import image as image_service
from .services import text as text_service
from .services.pipeline import StoryGenerationError, generate_story_content


class StoryApiTests(TestCase):
    def test_create_story(self):
        response = self.client.post(
            reverse("create-story"),
            data=json.dumps(
                {
                    "child_name": "Amara",
                    "child_appearance": "Curly black hair",
                    "favorite_theme": "foxes",
                    "reading_level": "early-reader",
                    "moral_lesson": "Sharing is caring",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Story.objects.count(), 1)
        self.assertEqual(response.json()["story"]["childName"], "Amara")
        self.assertTrue(response.json()["publishToken"])
        self.assertFalse(response.json()["story"]["isPublic"])

    def test_invalid_story_returns_field_errors(self):
        response = self.client.post(
            reverse("create-story"),
            data=json.dumps({"child_name": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("child_name", response.json()["fields"])

    def test_original_camel_case_payload_is_supported(self):
        response = self.client.post(
            reverse("create-story"),
            data=json.dumps(
                {
                    "childName": "Leo",
                    "childAppearance": "Red hat",
                    "favoriteTheme": "space",
                    "readingLevel": "beginner",
                    "moralLesson": "Be curious",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["story"]["childName"], "Leo")

    def test_child_gender_is_persisted_and_defaults_when_missing(self):
        response = self.client.post(
            reverse("create-story"),
            data=json.dumps(
                {
                    "child_name": "Leo",
                    "child_appearance": "Red hat",
                    "favorite_theme": "space",
                    "reading_level": "beginner",
                    "moral_lesson": "Be curious",
                    "child_gender": "boy",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["story"]["childGender"], "boy")

        response2 = self.client.post(
            reverse("create-story"),
            data=json.dumps(
                {
                    "child_name": "Sam",
                    "child_appearance": "Green shirt",
                    "favorite_theme": "robots",
                    "reading_level": "beginner",
                    "moral_lesson": "Be kind",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response2.status_code, 201)
        self.assertEqual(response2.json()["story"]["childGender"], "unspecified")


class SitePageTests(TestCase):
    def test_reference_site_pages_render(self):
        pages = {
            "story-library": ("/library/", "Story Library"),
            "my-books": ("/auth/", "My Books"),
            "pricing": ("/pricing/", "Simple Pricing"),
            "about": ("/about/", "About This Storybook Project"),
            "contact": ("/contact/", "Contact Us"),
            "privacy": ("/privacy/", "Privacy Policy"),
            "terms": ("/terms/", "Terms of Service"),
            "disclaimer": ("/disclaimer/", "Disclaimer"),
        }
        for name, (url, heading) in pages.items():
            with self.subTest(page=name):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, heading)
                self.assertContains(response, 'href="/library/"')

    def test_homepage_keeps_story_form_and_site_navigation(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="story-form"')
        self.assertContains(response, 'id="book-reader"')
        self.assertContains(response, 'id="new-book-button"')
        self.assertContains(response, 'data-reader-next')
        self.assertContains(response, "Poseidon's Story Book")
        self.assertContains(response, "How it works")
        self.assertContains(response, "Frequently asked questions")

    def test_pricing_discloses_checkout_is_unavailable(self):
        response = self.client.get("/pricing/")
        self.assertContains(response, "checkout are not enabled")

    def test_contact_page_has_mail_form_fields(self):
        response = self.client.get("/contact/")
        self.assertContains(response, 'id="contact-form"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, "poseidonhamk@gmail.com")
        self.assertContains(response, "Prepare email")


def _make_story(**overrides):
    defaults = dict(
        child_name="Amara",
        child_appearance="Curly black hair, brown eyes",
        favorite_theme="foxes",
        reading_level="early-reader",
        moral_lesson="Sharing is caring",
    )
    defaults.update(overrides)
    return Story.objects.create(**defaults)


def _set_story_token(story):
    token = "private-story-token"
    story.publish_token_hash = hashlib.sha256(token.encode()).hexdigest()
    story.save(update_fields=["publish_token_hash"])
    return token


class StoryLibraryTests(TestCase):
    def setUp(self):
        self.publish_token = "one-time-story-publish-token"
        self.story = _make_story(
            status="COMPLETE",
            title="Amara and the Moon Fox",
            publish_token_hash=hashlib.sha256(self.publish_token.encode()).hexdigest(),
        )

    def set_visibility(self, is_public, token=None):
        return self.client.post(
            reverse("publish-story", args=[self.story.id]),
            data=json.dumps({"isPublic": is_public}),
            content_type="application/json",
            HTTP_X_STORY_TOKEN=token or self.publish_token,
        )

    def test_publish_requires_the_creation_token(self):
        response = self.set_visibility(True, token="wrong-token")
        self.assertEqual(response.status_code, 403)
        self.story.refresh_from_db()
        self.assertFalse(self.story.is_public)

    def test_only_completed_stories_can_be_published(self):
        self.story.status = "DRAFT"
        self.story.save(update_fields=["status"])
        response = self.set_visibility(True)
        self.assertEqual(response.status_code, 409)
        self.story.refresh_from_db()
        self.assertFalse(self.story.is_public)

    def test_published_story_appears_in_library_and_can_be_removed(self):
        Page.objects.create(
            story=self.story,
            page_number=1,
            summary="Amara meets the moon fox.",
            text="Amara followed the moon fox into the silver forest.",
        )
        response = self.set_visibility(True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["story"]["isPublic"])
        library = self.client.get(reverse("story-library"))
        self.assertContains(library, self.story.title)
        self.assertContains(library, f"/library/{self.story.id}/")
        self.assertContains(library, f"/api/stories/{self.story.id}/download/")
        book = self.client.get(reverse("public-story-book", args=[self.story.id]))
        self.assertEqual(book.status_code, 200)
        self.assertContains(book, "Amara followed the moon fox")
        self.assertContains(book, 'data-book-data-id="public-book-pages"')
        self.assertContains(book, f"/api/stories/{self.story.id}/download/")

        response = self.set_visibility(False)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["story"]["isPublic"])
        self.assertNotContains(self.client.get(reverse("story-library")), self.story.title)

    def test_private_story_book_is_not_available_publicly(self):
        response = self.client.get(reverse("public-story-book", args=[self.story.id]))
        self.assertEqual(response.status_code, 404)

    def test_public_library_story_can_download_pdf_without_token(self):
        self.story.is_public = True
        self.story.save(update_fields=["is_public"])
        Page.objects.create(
            story=self.story,
            page_number=1,
            summary="Amara meets the moon fox.",
            text="Amara followed the moon fox into the silver forest.",
        )
        response = self.client.get(reverse("download-story-pdf", args=[self.story.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")


class MockProviderTests(TestCase):
    """The mock providers must work fully offline (no network calls)."""

    def test_toddler_level_uses_short_story_length_and_guidance(self):
        story = _make_story(reading_level="toddler")
        provider = text_service.MockTextProvider()
        outline = provider.generate_story(story, text_service.page_count_for("toddler"))
        self.assertEqual(len(outline.pages), 4)
        self.assertEqual(text_service.READING_LEVEL_GUIDANCE["toddler"], "very simple words and only a few words per page, for ages 0-2")

    def test_mock_text_provider_returns_expected_page_count(self):
        story = _make_story(reading_level="beginner")
        provider = text_service.MockTextProvider()
        outline = provider.generate_story(story, text_service.page_count_for(story.reading_level))
        self.assertEqual(len(outline.pages), 5)
        self.assertTrue(outline.title)
        self.assertIn(story.child_name, outline.pages[0].text)

    def test_mock_image_provider_returns_url(self):
        provider = image_service.MockImageProvider()
        result = provider.generate_image("a fox in a forest")
        self.assertTrue(result["url"].startswith("https://"))
        self.assertEqual(result["provider"], "mock")

    def test_get_text_provider_defaults_to_mock(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            os_environ = __import__("os").environ
            os_environ.pop("TEXT_PROVIDER", None)
            provider = text_service.get_text_provider()
            self.assertIsInstance(provider, text_service.MockTextProvider)

    def test_get_image_provider_defaults_to_mock(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            os_environ = __import__("os").environ
            os_environ.pop("IMAGE_PROVIDER", None)
            provider = image_service.get_image_provider()
            self.assertIsInstance(provider, image_service.MockImageProvider)


class PipelineTests(TestCase):
    """End-to-end pipeline test using the network-free mock providers."""

    def test_generate_story_content_creates_pages_and_assets(self):
        story = _make_story()
        with mock.patch.dict("os.environ", {"TEXT_PROVIDER": "mock", "IMAGE_PROVIDER": "mock"}):
            result = generate_story_content(story)

        self.assertEqual(result.status, "COMPLETE")
        self.assertTrue(result.title)
        pages = list(result.pages.all())
        self.assertEqual(len(pages), text_service.page_count_for(story.reading_level))
        for page in pages:
            self.assertTrue(hasattr(page, "asset"))
            self.assertTrue(page.asset.url)

    def test_generate_story_content_marks_failed_on_text_error(self):
        story = _make_story()
        with mock.patch.dict("os.environ", {"TEXT_PROVIDER": "openrouter"}, clear=False):
            os_environ = __import__("os").environ
            os_environ.pop("OPENROUTER_API_KEY", None)
            with self.assertRaises(StoryGenerationError):
                generate_story_content(story)
        story.refresh_from_db()
        self.assertEqual(story.status, "FAILED")
        self.assertIn("OPENROUTER_API_KEY", story.error_message)

    def test_generate_story_content_replaces_existing_pages_on_retry(self):
        story = _make_story()
        Page.objects.create(story=story, page_number=1, summary="stale")
        with mock.patch.dict("os.environ", {"TEXT_PROVIDER": "mock", "IMAGE_PROVIDER": "mock"}):
            generate_story_content(story)
        pages = list(story.pages.all())
        self.assertEqual(len(pages), text_service.page_count_for(story.reading_level))
        self.assertNotEqual(pages[0].summary, "stale")


class GenerateStoryEndpointTests(TestCase):
    @mock.patch("stories.views._start_story_generation")
    def test_generate_endpoint_accepts_background_generation(self, start_generation):
        story = _make_story()
        token = _set_story_token(story)
        response = self.client.post(
            reverse("generate-story", args=[story.id]),
            HTTP_X_STORY_TOKEN=token,
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["story"]["status"], "GENERATING")
        self.assertEqual(response.json()["story"]["pages"], [])
        start_generation.assert_called_once_with(story.id)

    def test_background_generation_completes_story_with_mock_providers(self):
        from .views import _generate_story_in_background

        story = _make_story()
        with mock.patch.dict("os.environ", {"TEXT_PROVIDER": "mock", "IMAGE_PROVIDER": "mock"}):
            _generate_story_in_background(story.id)
        story.refresh_from_db()
        self.assertEqual(story.status, "COMPLETE")
        self.assertEqual(story.pages.count(), text_service.page_count_for(story.reading_level))

    def test_background_worker_records_generation_errors(self):
        from .views import _generate_story_in_background

        story = _make_story()
        with mock.patch.dict("os.environ", {"TEXT_PROVIDER": "openrouter"}, clear=False):
            os_environ = __import__("os").environ
            os_environ.pop("OPENROUTER_API_KEY", None)
            _generate_story_in_background(story.id)
        story.refresh_from_db()
        self.assertEqual(story.status, "FAILED")
        self.assertIn("OPENROUTER_API_KEY", story.error_message)

    def test_generate_endpoint_requires_post(self):
        story = _make_story()
        response = self.client.get(reverse("generate-story", args=[story.id]))
        self.assertEqual(response.status_code, 405)

    def test_private_story_cannot_be_generated_without_its_token(self):
        story = _make_story()
        response = self.client.post(reverse("generate-story", args=[story.id]))
        self.assertEqual(response.status_code, 404)


class DownloadStoryPdfTests(TestCase):
    def test_download_returns_pdf_after_generation(self):
        story = _make_story()
        token = _set_story_token(story)
        with mock.patch.dict("os.environ", {"TEXT_PROVIDER": "mock", "IMAGE_PROVIDER": "mock"}):
            generate_story_content(story)

        with mock.patch("stories.services.pdf._fetch_image_reader", return_value=None):
            response = self.client.get(
                reverse("download-story-pdf", args=[story.id]),
                HTTP_X_STORY_TOKEN=token,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        pdf_page_count = len(re.findall(rb"/Type\s*/Page\b", response.content))
        self.assertEqual(
            pdf_page_count,
            text_service.page_count_for(story.reading_level) + 2,
        )

    def test_download_without_pages_returns_conflict(self):
        story = _make_story()
        token = _set_story_token(story)
        response = self.client.get(
            reverse("download-story-pdf", args=[story.id]),
            HTTP_X_STORY_TOKEN=token,
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())

    def test_private_story_cannot_be_downloaded_without_its_token(self):
        story = _make_story()
        response = self.client.get(reverse("download-story-pdf", args=[story.id]))
        self.assertEqual(response.status_code, 404)

    def test_private_story_token_is_not_accepted_in_download_url(self):
        story = _make_story()
        token = _set_story_token(story)
        response = self.client.get(
            f"{reverse('download-story-pdf', args=[story.id])}?token={token}"
        )
        self.assertEqual(response.status_code, 404)
