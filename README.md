# Poseidon's Story Book Generator

## Short description

Poseidon's Story Book Generator creates personalized children's stories using
a child's name, appearance, favorite theme, reading level, and a lesson. After
submission, story pages and illustrations generate in the background and
appear in an interactive, page-by-page reader as they become ready. Readers
can download a PDF with front and back covers or choose to share the completed
book in the community library.

Stories can include one main character and up to three supporting characters.
Private books are tied to an account; anonymous books use a one-time access
token. A completed book enters the community library only after the creator
opts in and a staff member approves it. Consented photo references are
available when fal.ai image generation is configured. Paid checkout is not
implemented because the product's payment model is still undecided.

## Technologies

- **Backend:** Python and Django
- **Database:** SQLite for local development
- **Frontend:** HTML, CSS, and JavaScript
- **Story generation:** Configurable OpenRouter provider; mock provider is the
  default
- **Illustration generation:** Configurable fal.ai provider; placeholder mock
  provider is the default
- **PDF generation:** ReportLab and Pillow
- **Testing:** Django test framework

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
  configured in this build. Stories stay private unless their creator opts in
  to the community library.
- SQLite by default for a zero-configuration local demo.
- JSON endpoints at `/api/health/`, `/api/stories/`, `/api/stories/<id>/`,
  `/api/stories/<id>/generate/`, and `/api/stories/<id>/download/`.
- Django models for stories, pages, and illustration assets.
- Field validation compatible with both snake_case and the original camelCase
  request payload, including the child's gender (used for correct pronouns
  and illustration accuracy).
- Illustration style choices: warm watercolor, pencil illustration,
  semi-realistic anime, and polished 3D animation.
- An outline -> page text -> illustration prompt -> image AI pipeline
  (`stories/services/`) with swappable, environment-configured providers
  (see "AI pipeline" below). Mock providers are the default, so no AI API keys
  are needed for local development.
- A colorful, playful children's-book themed UI, and a one-click "Download
  as eBook (PDF)" button that renders the illustrated storybook as a PDF
  (`stories/services/pdf.py`) readable on a phone or any e-reader app.

## Setup

Prerequisite: Python 3.10+.

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
docker compose up --build
```

Open http://127.0.0.1:8000. Compose starts PostgreSQL, Redis, the Django web
service, and a Celery worker. The default `.env` uses mock text and image
providers, so story generation needs no AI API keys. The image mock uses a
placeholder URL, which requires internet access to display. See "AI pipeline"
below to switch on real providers.

Run validation with:

```powershell
python manage.py check
python manage.py test stories
```

For production, set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`,
`DJANGO_ALLOWED_HOSTS`, and `DATABASE_PATH`. PostgreSQL can be enabled by
changing the database configuration in `storybook_project/settings.py`.

## AI pipeline

`POST /api/stories/<id>/generate/` returns immediately and starts story
generation in a background thread. The browser polls for updates while the
pipeline persists results:

1. Generate a story outline (title + per-page summary/text/illustration
   prompt) with a text model in one structured JSON call.
2. Persist each outline beat as a `Page`.
3. Generate an illustration per page's prompt with an image model and store
   it as an `Asset`.

Both stages use swappable providers selected via environment variables (see
`.env.example`); copy it to `.env` to configure real providers, or leave the
defaults (`mock`) for a no-API-key local demo. The image mock returns a
placeholder image URL; it does not generate artwork.

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

When `IMAGE_PROVIDER=fal` and `FAL_KEY` is set, an adult may provide an
optional photo reference after confirming they are the child's parent or
guardian. The photo is stripped of metadata, resized, stored outside public
static files, and removed from this app after successful generation. fal.ai
receives the photo through its file upload service and may retain it under its
own policies. `FAL_REFERENCE_MODEL` defaults to `fal-ai/flux-pro/kontext`.

## Accounts, privacy, and community sharing

Create an account at `/accounts/signup/` and sign in at `/accounts/login/`.
Signed-in stories appear in `/accounts/books/`; owners can delete them there.
Anonymous private stories remain accessible with the creation token held by
the creating browser.

Publishing a completed book makes it appear in `/library/` immediately after
the creator confirms public sharing. Shared books may include the child's name.
Staff can remove a reported book and review reports at `/admin/`. Signed-in
readers can report a community book once. Create a staff account with
`python manage.py createsuperuser` (or run it in the `web` container).

## Durable generation and retries

Generation jobs are queued through Celery and Redis. Workers retry transient
failures with backoff up to three times. The reader offers a manual retry
after a failed job; image retries keep completed pages and illustrations.
Redis uses append-only persistence in the Compose setup. Run at least one
Celery worker alongside the web service.

For a local deployment with persistent PostgreSQL, Redis, and private photo
storage, copy `.env.example` to `.env` and run:

```powershell
docker compose up --build
```

Open http://127.0.0.1:8000. Set `DJANGO_SECRET_KEY`, explicit
`DJANGO_ALLOWED_HOSTS`, `POSTGRES_PASSWORD`, and `DJANGO_DEBUG=false` before
exposing a deployment to the internet. Production settings refuse the sample
secret, wildcard hosts, SQLite, or a missing Redis broker. The named volumes
persist PostgreSQL data, Redis jobs, and private reference photos. Configure
real OpenRouter/fal.ai keys only when you want paid external generation.

The CI workflow runs Django checks/tests and both legacy TypeScript builds.
To run the browser flow against a staging deployment, set the repository
variable `STAGING_URL` to a disposable staging site configured with mock
providers and run the `hosted-e2e` workflow job. The test creates a book,
checks the reader and PDF, shares the book in the community library, then
deletes its book.
The project does not have a hosted URL configured here, so the hosted test
still needs a deployed staging target.

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

Generation returns immediately while a durable worker builds the book. The
browser polls for story updates, so page text appears after the outline is
ready and illustrations fill in while generation continues.

Checkout remains intentionally disconnected pending a product decision about
paid downloads or subscriptions. Usability sessions with people unfamiliar
with the project and the hosted staging run remain external project steps.

## Weekly schedule

### Week 5: Generation reliability and core experience — 17 hours

- Improve background generation and progress updates.
- Review story and illustration persistence.
- Improve error handling and retry behavior.
- Test the complete story-to-reader-to-PDF flow.

### Week 6: Library, safety, and interface polish — 18 hours

- Add moderation and reporting plans for shared books.
- Refine the library and book-reader experience.
- Explore multiple characters and photo references, including consent and
  privacy requirements.
- Revisit any unfinished Week 5 priorities first.

### Week 7: Testing and optimization — 16 hours

- Ask people unfamiliar with the project to create and read a book.
- Observe where they get confused.
- Prioritize crashes and issues that block story generation, reading,
  sharing, or PDF download.
- Test across browsers and devices.

### Week 8: Final polish and demo preparation — 14 hours

- Fix critical bugs.
- Finalize setup and deployment documentation.
- Prepare a demo showing story creation, progressive page generation,
  reading, PDF download, and sharing.

