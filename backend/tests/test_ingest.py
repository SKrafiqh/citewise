from pathlib import Path

import fitz
import pytest

from app.ingest import pdf, slides, video
from app.ingest.store import UnitIn, embedding_text, public_error, unit_id


def test_unit_id_per_modality():
    assert unit_id("textbook", {"page": 87}) == "textbook-p87"
    assert unit_id("slides", {"slide": 14}) == "slides-s14"
    assert unit_id("lec1", {"t_start": 742, "t_end": 808}) == "lec1-t742"


def test_embedding_text_includes_figure_description():
    assert embedding_text(UnitIn({"page": 1}, "body", "a tree diagram")) == "body\na tree diagram"
    assert embedding_text(UnitIn({"page": 1}, "body")) == "body"


def test_parse_page_range():
    assert list(pdf.parse_page_range("2-4", 10)) == [2, 3, 4]
    assert list(pdf.parse_page_range("8-20", 10)) == [8, 9, 10]
    assert list(pdf.parse_page_range(None, 3)) == [1, 2, 3]
    with pytest.raises(ValueError):
        pdf.parse_page_range("5-2", 10)
    with pytest.raises(ValueError):
        pdf.parse_page_range("abc", 10)


@pytest.fixture
def two_page_pdf(tmp_path) -> Path:
    path = tmp_path / "book.pdf"
    doc = fitz.open()
    for text in ("Bayes rule page", "Independence page"):
        doc.new_page().insert_text((72, 72), text)
    doc.save(path)
    return path


def test_pdf_units_keep_original_page_numbers(two_page_pdf):
    units = pdf.build_units(two_page_pdf, "textbook", pages="2-2")
    assert [u.locator for u in units] == [{"page": 2}]
    assert "Independence" in units[0].text
    assert units[0].figure_desc is None


def test_slide_units_use_vision_and_split_reading(two_page_pdf, monkeypatch):
    monkeypatch.setattr(slides, "generate", lambda prompt, images: "TEXT: hello\nVISUALS: a Venn diagram")
    units = slides.build_units(two_page_pdf, "slides")
    assert [u.locator for u in units] == [{"slide": 1}, {"slide": 2}]
    assert units[0].figure_desc == "a Venn diagram"
    assert "Bayes" in units[0].text  # real slide text preferred over the vision TEXT part


def test_slide_vision_failure_keeps_text(two_page_pdf, monkeypatch):
    def boom(prompt, images):
        raise RuntimeError("vision down")

    monkeypatch.setattr(slides, "generate", boom)
    assert len(slides.build_units(two_page_pdf, "slides")) == 2


def test_split_reading_without_visuals():
    assert slides.split_reading("TEXT: only words") == ("only words", None)


VTT = """WEBVTT
Kind: captions

00:00:01.000 --> 00:00:03.000 align:start position:0%
hello <c>world</c>

00:00:03.000 --> 00:00:05.000
hello world
this is Bayes.

00:00:05.000 --> 00:00:07.500
this is Bayes.
next line
"""


def test_parse_vtt_drops_rolling_duplicates():
    segs = video.parse_vtt(VTT)
    assert [s.text for s in segs] == ["hello world", "this is Bayes.", "next line"]
    assert segs[0].start == 1.0 and segs[2].end == 7.5


def test_merge_windows_respects_bounds_and_sentences():
    segs = [video.Segment(i * 10, i * 10 + 10, f"s{i}" + ("." if i == 6 else "")) for i in range(20)]
    windows = video.merge_windows(segs)
    assert windows[0][:2] == (0, 70)  # first sentence end at/after 60 s
    assert all(end - start <= 90 for start, end, _ in windows)
    assert windows[-1][1] == 200


def test_merge_windows_force_cut_without_punctuation():
    segs = [video.Segment(i * 10, i * 10 + 10, "word") for i in range(30)]
    assert all(end - start <= 90 for start, end, _ in video.merge_windows(segs))


def test_pick_keyframes_spacing_and_cap():
    assert video.pick_keyframes([0, 5, 21, 30, 45]) == [0, 2, 4]
    many = [float(i * 25) for i in range(200)]
    assert len(video.pick_keyframes(many)) == video.MAX_KEYFRAMES


def test_attach_keyframes_by_timestamp():
    units = video.attach_keyframes([(0, 60, "a"), (60, 120, "b")], [(30.0, "diagram"), (200.0, "late")])
    assert units[0].figure_desc == "diagram" and units[1].figure_desc is None
    assert units[0].locator == {"t_start": 0, "t_end": 60}


def test_parse_showinfo():
    assert video.parse_showinfo("x pts_time:12.5 y\nz pts_time:30 w") == [12.5, 30.0]


def test_public_error_hides_provider_details():
    assert public_error(ValueError("no content units were extracted")) == "no content units were extracted"
    leaked = public_error(ConnectionError("host db.secret.supabase.co refused"))
    assert "supabase" not in leaked and "server log" in leaked
