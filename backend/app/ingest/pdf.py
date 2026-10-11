"""PDF ingestion: one unit per page, with page images and vision descriptions of figures."""
import argparse
import logging
import re
from pathlib import Path

import fitz  # PyMuPDF

from app.config import get_settings
from app.ingest.store import UnitIn, ingest_source
from app.llm import generate

log = logging.getLogger(__name__)

MIN_FIGURE_PX = 150
MAX_FIGURES_PER_PAGE = 3
PAGE_ZOOM = 1.4  # render scale; JPEG keeps page images small enough to commit and serve


def parse_page_range(spec: str | None, total: int) -> range:
    """'150-200' (1-based, inclusive) -> range of 1-based page numbers, clipped to the document."""
    if not spec:
        return range(1, total + 1)
    match = re.fullmatch(r"(\d+)-(\d+)", spec.strip())
    if not match or int(match[1]) > int(match[2]) or int(match[1]) < 1:
        raise ValueError(f"invalid page range {spec!r}; use START-END, e.g. 150-200")
    return range(int(match[1]), min(int(match[2]), total) + 1)


def render_page(page: "fitz.Page", out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(matrix=fitz.Matrix(PAGE_ZOOM, PAGE_ZOOM)).save(out, jpg_quality=70)


def describe_figures(doc: "fitz.Document", page: "fitz.Page", figures_dir: Path, prompt: str) -> str | None:
    """Vision-describe the larger embedded images on a page; a failed figure is skipped."""
    descriptions: list[str] = []
    for index, info in enumerate(page.get_images(full=True)[:MAX_FIGURES_PER_PAGE], start=1):
        pix = fitz.Pixmap(doc, info[0])
        if pix.width < MIN_FIGURE_PX or pix.height < MIN_FIGURE_PX:
            continue
        if pix.alpha or pix.colorspace is None or pix.colorspace.n > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        path = figures_dir / f"p{page.number + 1}_{index}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(path)
        try:
            descriptions.append(generate(prompt, images=[path]).strip())
        except Exception:  # TRD §7: store the unit without this figure description
            log.warning("figure description failed for %s", path, exc_info=True)
    return "\n".join(descriptions) or None


def build_units(pdf_path: Path, source_id: str, pages: str | None = None) -> list[UnitIn]:
    settings = get_settings()
    prompt = (settings.prompts_dir / "figure_describe.md").read_text(encoding="utf-8")
    base = settings.derived_dir / source_id
    units: list[UnitIn] = []
    with fitz.open(pdf_path) as doc:
        for number in parse_page_range(pages, doc.page_count):
            page = doc[number - 1]
            render_page(page, base / "pages" / f"{number}.jpg")
            figure_desc = describe_figures(doc, page, base / "figures", prompt)
            text = page.get_text().strip()
            if text or figure_desc:
                units.append(UnitIn({"page": number}, text, figure_desc))
    return units


def ingest_pdf(pdf_path: Path, source_id: str, title: str, license: str | None, pages: str | None = None) -> int:
    return ingest_source(
        source_id,
        title=title,
        modality="pdf",
        uri=f"file:{pdf_path.name}",
        license=license,
        build_units=lambda: build_units(pdf_path, source_id, pages),
        prune=pages is None,  # a page range updates those pages only
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a PDF into the knowledge base")
    parser.add_argument("path", type=Path)
    parser.add_argument("source_id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--license", default=None)
    parser.add_argument("--pages", default=None, help="1-based inclusive PDF page range, e.g. 150-200")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(f"ingested {ingest_pdf(args.path, args.source_id, args.title, args.license, args.pages)} units")


if __name__ == "__main__":
    main()
