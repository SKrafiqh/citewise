"""Turn a retrieved unit into a citation the frontend can deep-link (GR-2)."""
from app.qa.retrieve import Hit

EXCERPT_CHARS = 280


def label(modality: str, locator: dict) -> str:
    if modality == "pdf":
        return f"p. {locator['page']}"
    if modality == "slide":
        return f"slide {locator['slide']}"
    seconds = int(locator["t_start"])
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def asset_url(source_id: str, modality: str, locator: dict) -> str | None:
    if modality == "pdf":
        return f"/assets/{source_id}/pages/{locator['page']}.jpg"
    if modality == "slide":
        return f"/assets/{source_id}/slides/{locator['slide']}.jpg"
    return None


def youtube_id(uri: str) -> str | None:
    return uri.removeprefix("youtube:") if uri.startswith("youtube:") else None


def build_citation(hit: Hit) -> dict:
    return {
        "unit_id": hit.unit_id,
        "source_id": hit.source_id,
        "source_title": hit.source_title,
        "modality": hit.modality,
        "locator": hit.locator,
        "label": label(hit.modality, hit.locator),
        "excerpt": " ".join(hit.text.split())[:EXCERPT_CHARS],
        "asset_url": asset_url(hit.source_id, hit.modality, hit.locator),
        "youtube_id": youtube_id(hit.source_uri),
    }
