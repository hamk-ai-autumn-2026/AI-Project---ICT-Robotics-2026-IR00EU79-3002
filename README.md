# Personalized AI Storybook Generator

A Django-based web app where a parent or teacher enters a child's details and
creates a personalized storybook draft. The UI is server-rendered with
vanilla JavaScript, making the MVP a single service that is straightforward to
deploy.

## Layout

```
manage.py, storybook_project/, stories/   Django application
templates/, static/                       Server-rendered UI and vanilla JS
backend/, frontend/                       Legacy React/Express implementation
```

The original React/Express implementation remains as a legacy reference while
the migration is completed. The runnable MVP is the Django service.

## Included in the Django MVP

- Story creation form with browser-side async submission.
- A multi-page site at `/`, `/library/`, `/pricing/`, `/about/`, `/contact/`,
  `/auth/`, `/privacy/`, `/terms/`, and `/disclaimer/`.
- Four age-based reading levels, from toddlers through confident readers.
- Pricing and account pages that clearly indicate checkout and sign-in are not
  configured in this build. The community library stays empty until public
  visibility and consent are implemented; private stories are not exposed.
- SQLite by default for a zero-configuration local demo.
- JSON endpoints at `/api/health/`, `/api/stories/`, `/api/stories/<id>/`,
  `/api/stories/<id>/generate/`, and `/api/stories/<id>/download/`.
- Django models for stories, pages, and illustration assets.
- Field validation compatible with both snake_case and the original camelCase
  request payload, including the child's gender (used for correct pronouns
  and illustration accuracy).
- An outline -> page text -> illustration prompt -> image AI pipeline
  (`stories/services/`) with swappable, env-configured providers (see
  "AI pipeline" below). Defaults to network-free mock providers so the app
  and test suite run with zero API keys.
- A colorful, playful children's-book themed UI, and a one-click "Download
  as eBook (PDF)" button that renders the illustrated storybook as a PDF
  (`stories/services/pdf.py`) readable on a phone or any e-reader app.

## Setup

Prerequisite: Python 3.10+.

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000. The default `.env` uses network-free mock text
and image providers, so story creation and generation both work offline
with no API keys. See "AI pipeline" below to switch on real providers.

Run validation with:

```powershell
python manage.py check
python manage.py test stories
```

For production, set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`,
`DJANGO_ALLOWED_HOSTS`, and `DATABASE_PATH`. PostgreSQL can be enabled by
changing the database configuration in `storybook_project/settings.py`.

## AI pipeline

`POST /api/stories/<id>/generate/` runs the full pipeline synchronously and
persists the results:

1. Generate a story outline (title + per-page summary/text/illustration
   prompt) with a text model in one structured JSON call.
2. Persist each outline beat as a `Page`.
3. Generate an illustration per page's prompt with an image model and store
   it as an `Asset`.

Both stages use swappable providers selected via environment variables (see
`.env.example`); copy it to `.env` to configure real providers, or leave the
defaults (`mock`) for a zero-API-key local demo.

### Text generation (`TEXT_PROVIDER`)

- `mock` (default): deterministic, offline outline generator.
- `openrouter`: calls the OpenRouter chat-completions API
  (`stories/services/text.py`). Defaults to `moonshotai/kimi-k2` (**Kimi
  K2**) as our first hunch for creative, child-friendly short stories.
  Swap `OPENROUTER_MODEL` to A/B test other models (Claude, GPT-4o-mini,
  Gemini, etc.) for creativity without touching code, since the
  child-friendly, short-story task is short enough that many models can
  likely do it well.

### Image generation (`IMAGE_PROVIDER`)

- `mock` (default): deterministic placeholder image URL, no network call.
- `fal`: calls a fal.ai text-to-image model over its synchronous REST API
  (`stories/services/image.py`). `FAL_MODEL` selects which model:
  - `fal-ai/flux/schnell` (default): extremely fast (~0.76s) and cheap
    (~$0.003 per megapixel image) -- ideal for local testing/iteration.
  - `bytedance/seedream/v5/pro/text-to-image` (**Seedream 5.0 Pro**):
    relatively cheap, good production default, doesn't worry about
    copyrighted IPs in prompts.
  - `fal-ai/nano-banana-pro` (**Google Nano Banana Pro**): highest quality,
    most expensive; reserve for hero/production images.

## Downloading the storybook as an eBook

Once a story finishes generating, the reader opens directly to its
illustrated pages with page-turn controls, keyboard navigation, and a PDF
download action. The "Download book (PDF)" button (and
`GET /api/stories/<id>/download/`) renders a 6x9in illustrated PDF with a
front cover, one page per story beat with its illustration and text framed in
a rotating accent color, and a matching back cover. The
PDF opens directly in any phone's default PDF/eBook viewer (Apple Books,
Google Play Books, Adobe Acrobat, etc.) or desktop PDF reader. Returns
`409` if the story hasn't been generated yet.

Storybooks are private by default. After generation, the creator can opt in
to the community library; the title, story text, and illustrations become
public and can be removed again from the creation page.

Generation returns immediately while a background worker builds the book.
The browser polls for story updates, so page text appears after the outline is
ready and illustrations fill in while generation continues. This prototype
uses a daemon thread; production deployment should use a durable task queue.

### Remaining planned work

- Page regeneration, moderation, and an account dashboard.

