import logging

from celery import Task, shared_task
from django.utils import timezone

from .models import Story
from .services.pipeline import generate_story_content

logger = logging.getLogger(__name__)


class StoryGenerationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if args:
            Story.objects.filter(pk=args[0]).update(
                status="FAILED",
                error_message="Generation failed after automatic retries. Use Retry to try again.",
                updated_at=timezone.now(),
            )
        logger.exception("Generation task %s failed: %s", task_id, exc, exc_info=einfo)


@shared_task(
    bind=True,
    base=StoryGenerationTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def generate_story_task(self, story_id):
    story = Story.objects.get(pk=story_id)
    result = generate_story_content(story, retry_only=True)
    if result.status == "COMPLETE" and story.reference_photo:
        # Remove the private reference once it has served its purpose.
        story.reference_photo.delete(save=True)
    return result.status
