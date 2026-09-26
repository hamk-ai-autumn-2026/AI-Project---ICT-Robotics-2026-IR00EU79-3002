from django.urls import path

from . import views

urlpatterns = [
    path("", views.story_form, name="story-form"),
    path("library/", views.site_page, {"page": "library"}, name="story-library"),
    path("library/<int:story_id>/", views.public_story_book, name="public-story-book"),
    path("auth/", views.site_page, {"page": "auth"}, name="my-books"),
    path("pricing/", views.site_page, {"page": "pricing"}, name="pricing"),
    path("about/", views.site_page, {"page": "about"}, name="about"),
    path("contact/", views.site_page, {"page": "contact"}, name="contact"),
    path("privacy/", views.site_page, {"page": "privacy"}, name="privacy"),
    path("terms/", views.site_page, {"page": "terms"}, name="terms"),
    path("disclaimer/", views.site_page, {"page": "disclaimer"}, name="disclaimer"),
    path("api/health/", views.health, name="health"),
    path("api/stories/", views.create_story, name="create-story"),
    path("api/stories/<int:story_id>/", views.story_detail, name="story-detail"),
    path("api/stories/<int:story_id>/generate/", views.generate_story, name="generate-story"),
    path("api/stories/<int:story_id>/publish/", views.publish_story, name="publish-story"),
    path("api/stories/<int:story_id>/download/", views.download_story_pdf, name="download-story-pdf"),
]
