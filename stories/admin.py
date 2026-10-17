from django.contrib import admin
from django.utils import timezone

from .models import Asset, Page, Story, StoryCharacter, StoryReport


class CharacterInline(admin.TabularInline):
    model = StoryCharacter
    extra = 0


@admin.action(description="Approve selected community books")
def approve_stories(modeladmin, request, queryset):
    queryset.update(moderation_status="APPROVED", is_public=True)


@admin.action(description="Reject and remove selected community books")
def reject_stories(modeladmin, request, queryset):
    queryset.update(moderation_status="REJECTED", is_public=False)


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("title", "child_name", "owner", "status", "is_public", "moderation_status", "created_at")
    list_filter = ("status", "is_public", "moderation_status", "created_at")
    search_fields = ("title", "child_name", "owner__username")
    actions = (approve_stories, reject_stories)
    inlines = (CharacterInline,)
    readonly_fields = ("publish_token_hash", "created_at", "updated_at")


class PageInline(admin.TabularInline):
    model = Page
    extra = 0
    readonly_fields = ("page_number", "summary", "text", "image_prompt")


@admin.register(StoryReport)
class StoryReportAdmin(admin.ModelAdmin):
    list_display = ("story", "reason", "reporter", "is_resolved", "created_at")
    list_filter = ("reason", "is_resolved", "created_at")
    search_fields = ("story__title", "details", "reporter__username")
    actions = ("mark_resolved",)

    @admin.action(description="Mark selected reports resolved")
    def mark_resolved(self, request, queryset):
        queryset.update(is_resolved=True, resolved_at=timezone.now())


admin.site.register(Asset)
