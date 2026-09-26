"""Renders a completed `Story` as a colorful, illustrated PDF "ebook" that
can be downloaded and opened on a phone (or any PDF reader/e-reader app).

Uses reportlab for PDF layout and Pillow to fetch/decode the page images
(downloaded from whichever image provider generated them) before embedding.
"""

from __future__ import annotations

import io

import requests
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PAGE_SIZE = portrait((6 * inch, 9 * inch))
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

# Warm, playful accent colors cycled per page so the ebook itself feels
# colorful and storybook-like, not just the illustrations.
ACCENT_COLORS = [
    colors.HexColor("#FF6B6B"),
    colors.HexColor("#4ECDC4"),
    colors.HexColor("#FFD93D"),
    colors.HexColor("#A78BFA"),
    colors.HexColor("#6BCB77"),
    colors.HexColor("#FF9F5A"),
]


class PdfGenerationError(Exception):
    """Raised when the storybook PDF cannot be built."""


def _fetch_image_reader(url: str):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        return ImageReader(image)
    except Exception:
        return None


def _draw_fitted_image(pdf: canvas.Canvas, image_reader, x, y, max_width, max_height):
    image_width, image_height = image_reader.getSize()
    scale = min(max_width / image_width, max_height / image_height)
    draw_width, draw_height = image_width * scale, image_height * scale
    pdf.drawImage(
        image_reader,
        x + (max_width - draw_width) / 2,
        y + (max_height - draw_height) / 2,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )


def _draw_cover(pdf: canvas.Canvas, story, accent, first_page):
    pdf.setFillColor(colors.HexColor("#FFF8EE"))
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)
    pdf.setFillColor(accent)
    pdf.rect(0, PAGE_HEIGHT - 22, PAGE_WIDTH, 22, fill=True, stroke=False)

    margin = 42
    image_x = margin
    image_y = PAGE_HEIGHT * 0.39
    image_width = PAGE_WIDTH - margin * 2
    image_height = PAGE_HEIGHT * 0.43
    pdf.setFillColor(colors.white)
    pdf.roundRect(image_x - 5, image_y - 5, image_width + 10, image_height + 10, 10, fill=True, stroke=False)
    asset = getattr(first_page, "asset", None)
    image_reader = _fetch_image_reader(asset.url) if asset and asset.url else None
    if image_reader:
        _draw_fitted_image(pdf, image_reader, image_x, image_y, image_width, image_height)
    else:
        pdf.setFillColor(accent)
        pdf.roundRect(image_x, image_y, image_width, image_height, 8, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(PAGE_WIDTH / 2, image_y + image_height / 2, "Your adventure begins here")

    pdf.setFillColor(colors.HexColor("#27304A"))
    title = story.title or f"{story.child_name}'s Story"
    _draw_wrapped_centered(pdf, title, PAGE_WIDTH / 2, PAGE_HEIGHT * 0.29, 23, max_width=PAGE_WIDTH - 64)
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT * 0.14, f"A story made especially for {story.child_name}")
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(PAGE_WIDTH / 2, 38, "Poseidon's Story Book")
    pdf.showPage()


def _draw_wrapped_centered(pdf, text, x_center, y, font_size, max_width, font="Helvetica-Bold", leading=None):
    leading = leading or font_size * 1.25
    words = text.split()
    lines = []
    current = ""
    pdf.setFont(font, font_size)
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdf.stringWidth(candidate, font, font_size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    total_height = leading * len(lines)
    start_y = y + total_height / 2 - leading
    for line in lines:
        pdf.drawCentredString(x_center, start_y, line)
        start_y -= leading


def _draw_wrapped_left(pdf, text, x, y, font_size, max_width, font="Helvetica", leading=None):
    leading = leading or font_size * 1.4
    words = text.split()
    lines = []
    current = ""
    pdf.setFont(font, font_size)
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdf.stringWidth(candidate, font, font_size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    for line in lines:
        pdf.drawString(x, y, line)
        y -= leading
    return y


def _draw_back_cover(pdf: canvas.Canvas, story, accent, last_page):
    pdf.setFillColor(colors.HexColor("#F3F7EF"))
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(5)
    pdf.roundRect(24, 24, PAGE_WIDTH - 48, PAGE_HEIGHT - 48, 14, fill=False, stroke=True)

    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT * 0.83, "The End")
    pdf.setFillColor(colors.HexColor("#27304A"))
    _draw_wrapped_centered(
        pdf,
        "Every great adventure begins with imagination.",
        PAGE_WIDTH / 2,
        PAGE_HEIGHT * 0.72,
        14,
        max_width=PAGE_WIDTH - 100,
        font="Helvetica-Bold",
    )

    image_area = PAGE_WIDTH - 112
    image_y = PAGE_HEIGHT * 0.28
    asset = getattr(last_page, "asset", None)
    image_reader = _fetch_image_reader(asset.url) if asset and asset.url else None
    if image_reader:
        _draw_fitted_image(pdf, image_reader, 56, image_y, image_area, PAGE_HEIGHT * 0.28)
    else:
        pdf.setFillColor(colors.white)
        pdf.roundRect(56, image_y, image_area, PAGE_HEIGHT * 0.22, 10, fill=True, stroke=False)
        pdf.setFillColor(accent)
        pdf.setFont("Helvetica-Oblique", 13)
        pdf.drawCentredString(PAGE_WIDTH / 2, image_y + PAGE_HEIGHT * 0.11, "Keep turning pages together")

    pdf.setFillColor(colors.HexColor("#27304A"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(PAGE_WIDTH / 2, 76, story.title or f"{story.child_name}'s Story")
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(PAGE_WIDTH / 2, 54, "Poseidon's Story Book")
    pdf.showPage()


def _draw_story_page(pdf: canvas.Canvas, page, accent):
    margin = 28
    # Colorful frame/border around the page.
    pdf.setFillColor(colors.HexColor("#FFFDF7"))
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(6)
    pdf.rect(margin / 2, margin / 2, PAGE_WIDTH - margin, PAGE_HEIGHT - margin, fill=False, stroke=True)

    image_area_height = PAGE_HEIGHT * 0.55
    image_top = PAGE_HEIGHT - margin
    image_reader = None
    asset = getattr(page, "asset", None)
    if asset and asset.url:
        image_reader = _fetch_image_reader(asset.url)

    if image_reader is not None:
        img_w, img_h = image_reader.getSize()
        max_w = PAGE_WIDTH - 2 * margin
        max_h = image_area_height
        scale = min(max_w / img_w, max_h / img_h)
        draw_w, draw_h = img_w * scale, img_h * scale
        x = (PAGE_WIDTH - draw_w) / 2
        y = image_top - draw_h
        pdf.saveState()
        pdf.setFillColor(colors.white)
        pdf.roundRect(x - 4, y - 4, draw_w + 8, draw_h + 8, 8, fill=True, stroke=False)
        pdf.drawImage(image_reader, x, y, width=draw_w, height=draw_h, preserveAspectRatio=True, mask="auto")
        pdf.restoreState()
        text_top = y - 24
    else:
        pdf.setFillColor(accent)
        pdf.roundRect(margin, image_top - image_area_height, PAGE_WIDTH - 2 * margin, image_area_height, 12, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-BoldOblique", 14)
        pdf.drawCentredString(PAGE_WIDTH / 2, image_top - image_area_height / 2, "\u2726 illustration coming soon \u2726")
        text_top = image_top - image_area_height - 24

    pdf.setFillColor(colors.HexColor("#24304A"))
    body_text = page.text or page.summary
    _draw_wrapped_left(pdf, body_text, margin + 6, text_top, 13, PAGE_WIDTH - 2 * margin - 12, leading=19)

    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(PAGE_WIDTH / 2, 24, f"Page {page.page_number}")
    pdf.showPage()


def build_story_pdf(story) -> bytes:
    """Render `story` (with prefetched pages/assets) to PDF bytes."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=PAGE_SIZE)

    pages = list(story.pages.all())
    if not pages:
        raise PdfGenerationError("Story has no pages to export yet. Generate the story first.")

    _draw_cover(pdf, story, ACCENT_COLORS[0], pages[0])
    for index, page in enumerate(pages):
        accent = ACCENT_COLORS[index % len(ACCENT_COLORS)]
        _draw_story_page(pdf, page, accent)

    accent = ACCENT_COLORS[len(pages) % len(ACCENT_COLORS)]
    _draw_back_cover(pdf, story, accent, pages[-1])

    pdf.save()
    buffer.seek(0)
    return buffer.read()
