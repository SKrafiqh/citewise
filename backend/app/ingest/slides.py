"""Slide ingestion: one unit per slide; each slide image is read by the vision model."""
import argparse
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from app.config import get_settings
from app.ingest.pdf import parse_page_range, render_page
from app.ingest.store import UnitIn, ingest_source
from app.llm import generate

log = logging.getLogger(__name__)
_VISUALS = re.compile(r"^\s*VISUALS:\s*", re.MULTILINE)
_TEXT = re.compile(r"^\s*TEXT:\s*", re.MULTILINE)


def split_reading(raw: str) -> tuple[str, str | None]:
    """Split the slide_read prompt output into (text, visuals)."""
    parts = _VISUALS.split(raw, maxsplit=1)
    text = _TEXT.sub("", parts[0], count=1).strip()
    visuals = parts[1].strip() if len(parts) > 1 else ""
    return text, (visuals or None)


def to_pdf(path: Path, workdir: Path) -> Path:
    """PPTX -> PDF with LibreOffice; PDFs pass through."""
    if path.suffix.lower() == ".pdf":
        return path
    soffice = shutil.which("soffice")
    if soffice is None:
        raise RuntimeError("LibreOffice (soffice) is required to ingest PPTX; upload a PDF export instead")
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(workdir), str(path)],
        check=True, capture_output=True, timeout=300,
    )
    return workdir / f"{path.stem}.pdf"


def build_units(slides_pdf: Path, source_id: str, pages: str | None = None) -> list[UnitIn]:
    settings = get_settings()
    prompt = (settings.prompts_dir / "slide_read.md").read_text(encoding="utf-8")
    base = settings.derived_dir / source_id / "slides"
    units: list[UnitIn] = []
    with fitz.open(slides_pdf) as doc:
        for number in parse_page_range(pages, doc.page_count):
            page = doc[number - 1]
            image = base / f"{number}.jpg"
            render_page(page, image)
            try:
                text, visuals = split_reading(generate(prompt, images=[image]))
            except Exception:
                log.warning("vision read failed for slide %d", number, exc_info=True)
                text, visuals = "", None
            text = page.get_text().strip() or text
            if text or visuals:
                units.append(UnitIn({"slide": number}, text or "(figure only)", visuals))
    return units


def ingest_slides(path: Path, source_id: str, title: str, license: str | None, pages: str | None = None) -> int:
    def build() -> list[UnitIn]:
        with tempfile.TemporaryDirectory() as tmp:
            return build_units(to_pdf(path, Path(tmp)), source_id, pages)

    return ingest_source(
        source_id, title=title, modality="slide", uri=f"file:{path.name}", license=license, build_units=build,
        prune=pages is None,  # a page range updates those slides only
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest slides (PPTX or PDF) into the knowledge base")
    parser.add_argument("path", type=Path)
    parser.add_argument("source_id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--license", default=None)
    parser.add_argument("--pages", default=None, help="1-based inclusive page range, e.g. 1-60")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(f"ingested {ingest_slides(args.path, args.source_id, args.title, args.license, args.pages)} units")


if __name__ == "__main__":
    main()
