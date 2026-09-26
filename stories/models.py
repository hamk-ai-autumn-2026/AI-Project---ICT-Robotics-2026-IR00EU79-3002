from django.db import models


class Story(models.Model):
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
        ("OUTLINE_READY", "Outline ready"),
        ("GENERATING", "Generating"),
        ("COMPLETE", "Complete"),
        ("FAILED", "Failed"),
    )

    child_name = models.CharField(max_length=80)
    child_gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="unspecified")
    child_appearance = models.CharField(max_length=500)
    favorite_theme = models.CharField(max_length=200)
    reading_level = models.CharField(max_length=32, choices=READING_LEVELS)
    moral_lesson = models.CharField(max_length=300)
    title = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    is_public = models.BooleanField(default=False)
    publish_token_hash = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"{self.child_name}'s story"


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
