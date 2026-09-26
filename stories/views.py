import hashlib
import json
import logging
import re
import secrets
import threading

from django.db import close_old_connections
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import StoryForm
from .models import Story
from .services.pdf import PdfGenerationError, build_story_pdf
from .services.pipeline import StoryGenerationError, generate_story_content

logger = logging.getLogger(__name__)

def _generate_story_in_background(story_id):
    close_old_connections()
    try:
        story = Story.objects.get(pk=story_id)
        generate_story_content(story)
    except StoryGenerationError:
        logger.info("Story generation finished with a handled error for story %s", story_id)
    except Exception:
        logger.exception("Unexpected story generation error for story %s", story_id)
        Story.objects.filter(pk=story_id).update(
            status="FAILED",
            error_message="Story generation failed unexpectedly. Please try again.",
        )
    finally:
        close_old_connections()


def _start_story_generation(story_id):
    threading.Thread(
        target=_generate_story_in_background,
        args=(story_id,),
        daemon=True,
    ).start()
SITE_PAGES = {
    "library": {
        "title": "Story Library",
        "intro": "Browse illustrated adventures made for curious young readers.",
    },
    "auth": {
        "title": "My Books",
        "intro": "Your storybooks belong together. Account sign-in is not connected in this version yet.",
    },
    "pricing": {
        "title": "Simple Pricing",
        "intro": "Create a story for free, then keep it as a downloadable book.",
    },
    "about": {
        "title": "About This Storybook Project",
        "intro": "A small creative project built around a big idea: every child can be the hero of a story.",
    },
    "contact": {
        "title": "Contact Us",
        "intro": "Questions, feedback, or a story idea? Get in touch with the team.",
    },
    "privacy": {
        "title": "Privacy Policy",
        "intro": "Last updated September 2026. This project is designed for adults creating stories for children.",
    },
    "terms": {
        "title": "Terms of Service",
        "intro": "Last updated September 2026. By using this storybook service, you agree to these basic terms.",
    },
    "disclaimer": {
        "title": "Disclaimer",
        "intro": "Please review generated stories and illustrations before sharing them with a child.",
    },
}

SITE_SECTIONS = {
    "about": [
        {"title": "The idea", "body": "This project uses creative technology to help families make personalized stories featuring the people, places, and interests a child loves."},
        {"title": "Our mission", "body": "Encourage imagination, make reading feel personal, and give families a simple way to save a one-of-a-kind adventure."},
        {"title": "Made with care", "body": "Story generation uses configurable text and illustration providers. Local development uses offline mock providers so the experience can be tested without external API keys."},
    ],
    "privacy": [
        {"title": "Information you provide", "body": "Story details entered into the form are stored by this application so it can generate and display the requested book. Do not submit sensitive personal information."},
        {"title": "Children's privacy", "body": "The service is intended for parents, guardians, and educators. Adults should submit only information they are comfortable using to create a story and should supervise children's use."},
        {"title": "Service providers", "body": "When external text or image providers are configured, story prompts are sent to those providers to generate content. The local mock providers do not send data over the network."},
        {"title": "Retention and contact", "body": "Stories remain in the configured application database until an administrator removes them. Contact the site owner to ask about access or deletion."},
    ],
    "terms": [
        {"title": "Who may use the service", "body": "Adults should create and review stories for children. You are responsible for the information you submit and for supervising how generated content is used."},
        {"title": "Generated content", "body": "AI-generated stories and illustrations may contain mistakes or unexpected details. Review each book before sharing it. Generated content is provided for personal, non-commercial use."},
        {"title": "Acceptable use", "body": "Do not submit unlawful, harmful, discriminatory, or adult content, interfere with the service, or use it to violate another person's rights."},
        {"title": "Availability", "body": "The service is provided as-is. Features may change, and uninterrupted availability or permanent storage is not guaranteed."},
    ],
    "disclaimer": [
        {"title": "AI-generated stories", "body": "Automated content can be inaccurate, incomplete, or unsuitable for a particular reader. An adult should review every story and illustration before sharing."},
        {"title": "Not professional advice", "body": "Stories are for entertainment and reading practice. They are not medical, psychological, educational, or parenting advice."},
        {"title": "Third-party services", "body": "If external AI providers are enabled, generation depends on their availability and policies. This local build defaults to mock providers."},
    ],
}


def _story_payload(story):
    return {
        "id": story.id,
        "childName": story.child_name,
        "childGender": story.child_gender,
        "childAppearance": story.child_appearance,
        "favoriteTheme": story.favorite_theme,
        "readingLevel": story.reading_level,
        "moralLesson": story.moral_lesson,
        "title": story.title or None,
        "status": story.status,
        "isPublic": story.is_public,
        "errorMessage": story.error_message or None,
        "createdAt": story.created_at.isoformat(),
        "updatedAt": story.updated_at.isoformat(),
        "pages": [
            {
                "id": page.id,
                "pageNumber": page.page_number,
                "summary": page.summary,
                "text": page.text or None,
                "imagePrompt": page.image_prompt or None,
                "moderationFlag": page.moderation_flag,
                "asset": (
                    {"url": page.asset.url, "provider": page.asset.provider}
                    if getattr(page, "asset", None)
                    else None
                ),
            }
            for page in story.pages.all()
        ],
    }


def _has_story_access(request, story):
    if story.is_public:
        return True
    supplied_token = request.headers.get("X-Story-Token", "")
    if not supplied_token or not story.publish_token_hash:
        return False
    supplied_hash = hashlib.sha256(supplied_token.encode()).hexdigest()
    return secrets.compare_digest(story.publish_token_hash, supplied_hash)


@require_GET
def health(request):
    return JsonResponse({"status": "ok", "db": "ok"})


def story_form(request):
    return render(request, "stories/story_form.html", {"form": StoryForm()})


def site_page(request, page):
    content = SITE_PAGES.get(page)
    if content is None:
        raise Http404
    context = {
        "page": page,
        **content,
        "sections": SITE_SECTIONS.get(page, []),
    }
    if page == "library":
        books = Story.objects.filter(is_public=True, status="COMPLETE").prefetch_related(
            "pages", "pages__asset"
        ).order_by("-created_at")
        context["books"] = [
            {
                "id": book.id,
                "title": book.title or "A new adventure",
                "reading_level": book.get_reading_level_display(),
                "cover_url": (
                    book.pages.first().asset.url
                    if book.pages.exists() and hasattr(book.pages.first(), "asset")
                    else None
                ),
            }
            for book in books
        ]
    return render(
        request,
        "stories/site_page.html",
        context,
    )


@require_GET
def public_story_book(request, story_id):
    story = get_object_or_404(
        Story.objects.filter(is_public=True, status="COMPLETE").prefetch_related(
            "pages", "pages__asset"
        ),
        pk=story_id,
    )
    book_pages = [
        {
            "pageNumber": page.page_number,
            "summary": page.summary,
            "text": page.text,
            "asset": {"url": page.asset.url} if hasattr(page, "asset") else None,
        }
        for page in story.pages.all()
    ]
    return render(
        request,
        "stories/public_book.html",
        {"story": story, "book_pages": book_pages},
    )


@require_POST
def create_story(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON"}, status=400)

    # Accept the original frontend's camelCase contract while using Django's
    # conventional snake_case field names internally.
    normalized_data = {
        "child_name": data.get("child_name", data.get("childName")),
        "child_gender": data.get("child_gender", data.get("childGender", "unspecified")),
        "child_appearance": data.get("child_appearance", data.get("childAppearance")),
        "favorite_theme": data.get("favorite_theme", data.get("favoriteTheme")),
        "reading_level": data.get("reading_level", data.get("readingLevel")),
        "moral_lesson": data.get("moral_lesson", data.get("moralLesson")),
    }
    form = StoryForm(normalized_data)
    if not form.is_valid():
        return JsonResponse(
            {"error": "Invalid story details", "fields": form.errors.get_json_data()},
            status=400,
        )
    story = form.save()
    publish_token = secrets.token_urlsafe(32)
    story.publish_token_hash = hashlib.sha256(publish_token.encode()).hexdigest()
    story.save(update_fields=["publish_token_hash"])
    return JsonResponse(
        {"story": _story_payload(story), "publishToken": publish_token}, status=201
    )


@require_http_methods(["GET"])
def story_detail(request, story_id):
    story = get_object_or_404(
        Story.objects.prefetch_related("pages", "pages__asset"), pk=story_id
    )
    if not _has_story_access(request, story):
        raise Http404
    return JsonResponse({"story": _story_payload(story)})


@require_POST
def generate_story(request, story_id):
    story = get_object_or_404(Story, pk=story_id)
    if not _has_story_access(request, story) or story.is_public:
        raise Http404
    if story.status != "GENERATING":
        story.status = "GENERATING"
        story.error_message = ""
        story.save(update_fields=["status", "error_message", "updated_at"])
        _start_story_generation(story.id)
    return JsonResponse({"story": _story_payload(story)}, status=202)


@require_POST
def publish_story(request, story_id):
    story = get_object_or_404(Story, pk=story_id)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON"}, status=400)
    is_public = data.get("isPublic")
    if not isinstance(is_public, bool):
        return JsonResponse({"error": "isPublic must be true or false"}, status=400)

    supplied_token = request.headers.get("X-Story-Token", "")
    supplied_hash = hashlib.sha256(supplied_token.encode()).hexdigest()
    if not story.publish_token_hash or not secrets.compare_digest(
        story.publish_token_hash, supplied_hash
    ):
        return JsonResponse({"error": "You cannot change this story's library visibility"}, status=403)
    if is_public and story.status != "COMPLETE":
        return JsonResponse({"error": "Only completed stories can be added to the library"}, status=409)

    story.is_public = is_public
    story.save(update_fields=["is_public", "updated_at"])
    return JsonResponse({"story": _story_payload(story)})


@require_GET
def download_story_pdf(request, story_id):
    story = get_object_or_404(
        Story.objects.prefetch_related("pages", "pages__asset"), pk=story_id
    )
    if not _has_story_access(request, story):
        raise Http404
    try:
        pdf_bytes = build_story_pdf(story)
    except PdfGenerationError as exc:
        return JsonResponse({"error": str(exc)}, status=409)

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", story.child_name or "storybook").strip("-") or "storybook"
    filename = f"{safe_name}-storybook.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
