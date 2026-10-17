from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db.models.signals import pre_delete
from django.dispatch import receiver
import uuid


def private_reference_upload_path(instance, filename):
    return f"story-references/{instance.id or uuid.uuid4()}/{uuid.uuid4().hex}.jpg"


class Story(models.Model):
    ART_STYLES = (
        ("watercolor", "Warm watercolor"),
        ("pencil", "Pencil illustration"),
        ("anime", "Semi-realistic anime"),
        ("3d-animation", "Polished 3D animation"),
    )
    READING_LEVELS = (
        ("toddler", "Toddlers (ages 0-2)"),
        ("beginner", "Beginner (ages 3-5)"),
        ("early-reader", "Early reader (ages 6-9)"),
        ("confident-reader", "Confident reader (ages 10+)"),
    )
    GENDER_CHOICES = (
        ("girl", "Girl"),
        ("boy", "Boy"),
        ("nonbinary", "Non-binary / other"),
        ("unspecified", "Prefer not to say"),
    )
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("QUEUED", "Queued"),
        ("OUTLINE_READY", "Outline ready"),
        ("GENERATING", "Generating"),
        ("COMPLETE", "Complete"),
        ("FAILED", "Failed"),
    )

    child_name = models.CharField(max_length=80)
    child_gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="unspecified")
    child_appearance = models.CharField(max_length=500)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="stories",
    )
    favorite_theme = models.CharField(max_length=200)
    reading_level = models.CharField(max_length=32, choices=READING_LEVELS)
    moral_lesson = models.CharField(max_length=300)
    art_style = models.CharField(max_length=20, choices=ART_STYLES, default="watercolor")
    reference_photo = models.ImageField(
        upload_to=private_reference_upload_path, blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    reference_photo_consent = models.BooleanField(default=False)
    photo_consent_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    is_public = models.BooleanField(default=False)
    publish_token_hash = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True)
    failed_stage = models.CharField(max_length=20, blank=True, default="")
    moderation_status = models.CharField(
        max_length=20,
        choices=(("APPROVED", "Approved"), ("PENDING", "Pending review"), ("REJECTED", "Rejected")),
        default="APPROVED",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"{self.child_name}'s story"


class StoryCharacter(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="characters")
    name = models.CharField(max_length=80)
    appearance = models.CharField(max_length=500, blank=True)
    gender = models.CharField(max_length=20, choices=Story.GENDER_CHOICES, default="unspecified")

    def __str__(self):
        return f"{self.name} in {self.story}"


class Page(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="pages")
    page_number = models.PositiveIntegerField()
    summary = models.TextField()
    text = models.TextField(blank=True)
    image_prompt = models.TextField(blank=True)
    moderation_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ["page_number"]
        constraints = [
            models.UniqueConstraint(fields=["story", "page_number"], name="unique_story_page")
        ]


class Asset(models.Model):
    page = models.OneToOneField(Page, on_delete=models.CASCADE, related_name="asset")
    url = models.URLField()
    provider = models.CharField(max_length=100)
    storage_path = models.CharField(max_length=500)


class StoryReport(models.Model):
    REASONS = (
        ("inappropriate", "Inappropriate content"),
        ("personal_info", "Personal information"),
        ("copyright", "Copyright concern"),
        ("other", "Other concern"),
    )
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="story_reports",
    )
    reason = models.CharField(max_length=30, choices=REASONS)
    details = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["story", "reporter"], name="unique_user_story_report")
        ]
        ordering = ["is_resolved", "-created_at"]


@receiver(pre_delete, sender=Story)
def remove_private_reference_on_story_delete(sender, instance, **kwargs):
    if instance.reference_photo:
        instance.reference_photo.delete(save=False)
