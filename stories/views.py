import hashlib
import json
import logging
import os
import re
import secrets
from io import BytesIO

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import StoryForm
from .models import Story, StoryCharacter, StoryReport
from .services.pdf import PdfGenerationError, build_story_pdf
from .tasks import generate_story_task

logger = logging.getLogger(__name__)

def _start_story_generation(story_id):
    return generate_story_task.delay(story_id)
SITE_PAGES = {
    "library": {
        "title": "Story Library",
        "intro": "Browse illustrated adventures made for curious young readers.",
    },
    "auth": {
        "title": "My Books",
        "intro": "Sign in to see your private books, or create a free account to keep them together.",
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
        {"title": "Made with care", "body": "Story generation uses configurable text and illustration providers. Local mock generation needs no AI credentials; reference photos are enabled only for fal.ai image generation with explicit guardian consent."},
    ],
    "privacy": [
        {"title": "Information you provide", "body": "Story details entered into the form are stored by this application so it can generate and display the requested book. Do not submit sensitive personal information."},
        {"title": "Children's privacy", "body": "The service is intended for parents, guardians, and educators. Adults should submit only information they are comfortable using to create a story and should supervise children's use."},
        {"title": "Service providers and reference photos", "body": "When an external text or image provider is configured, story prompts and any consented reference photo may be sent to that provider to generate content. Reference photos are stored privately by this app and removed after successful generation; provider retention is governed by that provider's policies. The mock text provider is local; the mock image provider returns a placeholder URL."},
        {"title": "Retention and contact", "body": "Stories remain in the configured application database until their owner or an administrator removes them. Failed generations may retain a consented reference photo so the owner can retry. Contact the site owner to ask about access or deletion."},
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
        "characters": [
            {"name": character.name, "appearance": character.appearance, "gender": character.gender}
            for character in story.characters.all()
        ],
        "childAppearance": story.child_appearance,
        "favoriteTheme": story.favorite_theme,
        "readingLevel": story.reading_level,
        "moralLesson": story.moral_lesson,
        "artStyle": story.art_style,
        "hasReferencePhoto": bool(story.reference_photo),
        "title": story.title or None,
        "status": story.status,
        "isPublic": story.is_public,
        "moderationStatus": story.moderation_status,
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
    if story.is_public and story.moderation_status != "REJECTED":
        return True
    if request.user.is_authenticated and story.owner_id == request.user.id:
        return True
    supplied_token = request.headers.get("X-Story-Token", "")
    if not supplied_token or not story.publish_token_hash:
        return False
    supplied_hash = hashlib.sha256(supplied_token.encode()).hexdigest()
    return secrets.compare_digest(story.publish_token_hash, supplied_hash)


def _has_owner_control(request, story):
    if request.user.is_authenticated and story.owner_id == request.user.id:
        return True
    supplied_token = request.headers.get("X-Story-Token", "")
    supplied_hash = hashlib.sha256(supplied_token.encode()).hexdigest()
    return bool(story.publish_token_hash and secrets.compare_digest(story.publish_token_hash, supplied_hash))


@require_GET
def health(request):
    return JsonResponse({"status": "ok", "db": "ok"})


def story_form(request):
    return render(request, "stories/story_form.html", {
        "form": StoryForm(),
        "reference_photo_enabled": (
            os.environ.get("IMAGE_PROVIDER", "mock").lower() == "fal"
            and bool(os.environ.get("FAL_KEY"))
        ),
    })


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
        books = Story.objects.filter(is_public=True, status="COMPLETE").exclude(
            moderation_status="REJECTED"
        ).prefetch_related("pages", "pages__asset").order_by("-created_at")
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
    story = (
        Story.objects.filter(
            is_public=True,
            status="COMPLETE",
        )
        .exclude(moderation_status="REJECTED")
        .prefetch_related("pages", "pages__asset")
        .filter(pk=story_id)
        .first()
    )
    if story is None:
        return render(request, "stories/public_book_unavailable.html", status=404)
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
        "art_style": data.get("art_style", data.get("artStyle", "watercolor")),
    }
    form = StoryForm(normalized_data)
    if not form.is_valid():
        return JsonResponse(
            {"error": "Invalid story details", "fields": form.errors.get_json_data()},
            status=400,
        )
    story = form.save(commit=False)
    if request.user.is_authenticated:
        story.owner = request.user
    story.save()
    raw_characters = data.get("characters", [])
    if not isinstance(raw_characters, list) or len(raw_characters) > 3:
        story.delete()
        return JsonResponse({"error": "Add no more than three supporting characters."}, status=400)
    for item in raw_characters:
        if not isinstance(item, dict):
            story.delete()
            return JsonResponse({"error": "Each supporting character must be an object."}, status=400)
        name = str(item.get("name", "")).strip()
        appearance = str(item.get("appearance", "")).strip()
        gender = str(item.get("gender", "unspecified"))
        if not name or len(name) > 80 or len(appearance) > 500 or gender not in dict(Story.GENDER_CHOICES):
            story.delete()
            return JsonResponse({"error": "Check each supporting character's name, appearance, and gender."}, status=400)
        StoryCharacter.objects.create(story=story, name=name, appearance=appearance, gender=gender)
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
    if story.status not in {"QUEUED", "GENERATING"}:
        story.status = "QUEUED"
        story.error_message = ""
        story.save(update_fields=["status", "error_message", "updated_at"])
        try:
            _start_story_generation(story.id)
        except Exception as exc:
            logger.exception("Could not queue story generation for %s", story.id)
            story.status = "FAILED"
            story.error_message = "Generation could not be queued. Please try again shortly."
            story.save(update_fields=["status", "error_message", "updated_at"])
            return JsonResponse({"error": story.error_message, "story": _story_payload(story)}, status=503)
    return JsonResponse({"story": _story_payload(story)}, status=202)


@require_POST
def retry_story_generation(request, story_id):
    story = get_object_or_404(Story, pk=story_id)
    if not _has_story_access(request, story) or story.is_public:
        raise Http404
    if story.status != "FAILED":
        return JsonResponse({"error": "Only failed stories can be retried."}, status=409)
    story.status = "QUEUED"
    story.error_message = ""
    story.save(update_fields=["status", "error_message", "updated_at"])
    try:
        _start_story_generation(story.id)
    except Exception:
        logger.exception("Could not queue retry for story %s", story.id)
        story.status = "FAILED"
        story.error_message = "Retry could not be queued. Please try again shortly."
        story.save(update_fields=["status", "error_message", "updated_at"])
        return JsonResponse({"error": story.error_message}, status=503)
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

    if not _has_owner_control(request, story):
        return JsonResponse({"error": "You cannot change this story's library visibility"}, status=403)
    if is_public and story.status != "COMPLETE":
        return JsonResponse({"error": "Only completed stories can be added to the library"}, status=409)

    story.is_public = is_public
    # Sharing is explicit in the reader, so a completed book becomes public
    # immediately after the creator confirms. Staff can still remove a book.
    story.moderation_status = "APPROVED"
    story.save(update_fields=["is_public", "moderation_status", "updated_at"])
    return JsonResponse({"story": _story_payload(story)})


@require_POST
def delete_story(request, story_id):
    story = get_object_or_404(Story, pk=story_id)
    if not _has_owner_control(request, story):
        raise Http404
    story.delete()
    return HttpResponse(status=204)


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


@require_GET
@login_required
def my_books(request):
    stories = Story.objects.filter(owner=request.user).order_by("-updated_at")
    return render(request, "stories/my_books.html", {"stories": stories})


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("my-books-list")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("my-books-list")
    return render(request, "registration/signup.html", {"form": form})


@require_POST
def upload_reference_photo(request, story_id):
    story = get_object_or_404(Story, pk=story_id)
    if not _has_story_access(request, story) or story.is_public:
        raise Http404
    photo = request.FILES.get("photo")
    if not photo:
        return JsonResponse({"error": "Choose a photo first."}, status=400)
    if not request.POST.get("consent") == "true":
        return JsonResponse({"error": "Photo and provider-processing consent is required."}, status=400)
    if os.environ.get("IMAGE_PROVIDER", "mock").lower() != "fal" or not os.environ.get("FAL_KEY"):
        return JsonResponse({"error": "Photo references require IMAGE_PROVIDER=fal and a configured fal.ai key."}, status=409)
    if photo.size > settings.MAX_REFERENCE_PHOTO_BYTES:
        return JsonResponse({"error": "Photos must be 8 MB or smaller."}, status=400)
    if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        return JsonResponse({"error": "Upload a JPEG, PNG, or WebP image."}, status=400)
    try:
        from PIL import Image, UnidentifiedImageError

        image = Image.open(photo)
        image.verify()
        photo.seek(0)
        with Image.open(photo) as image:
            if image.width * image.height > 25_000_000:
                return JsonResponse({"error": "Photos must be 25 megapixels or smaller."}, status=400)
            image.thumbnail((2048, 2048))
            cleaned_photo = BytesIO()
            image.convert("RGB").save(cleaned_photo, format="JPEG", quality=90, optimize=True)
            photo_bytes = cleaned_photo.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return JsonResponse({"error": "The uploaded file is not a valid supported image."}, status=400)
    if story.reference_photo:
        story.reference_photo.delete(save=False)
    story.reference_photo.save("reference.jpg", ContentFile(photo_bytes), save=False)
    story.reference_photo_consent = True
    story.photo_consent_at = timezone.now()
    story.save(update_fields=["reference_photo", "reference_photo_consent", "photo_consent_at", "updated_at"])
    return JsonResponse({"hasReferencePhoto": True}, status=201)


@require_POST
def report_story(request, story_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in to report a story."}, status=401)
    story = get_object_or_404(
        Story.objects.exclude(moderation_status="REJECTED"),
        pk=story_id,
        is_public=True,
    )
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    reason = data.get("reason")
    details = str(data.get("details", "")).strip()
    if reason not in dict(StoryReport.REASONS) or len(details) > 1000:
        return JsonResponse({"error": "Choose a report reason and keep details under 1000 characters."}, status=400)
    try:
        with transaction.atomic():
            StoryReport.objects.create(story=story, reporter=request.user, reason=reason, details=details)
    except IntegrityError:
        return JsonResponse({"error": "You have already reported this story."}, status=409)
    return JsonResponse({"message": "Thank you. The library team will review this story."}, status=201)
