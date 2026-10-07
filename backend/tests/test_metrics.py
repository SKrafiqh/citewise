from eval.metrics import citation_accuracy, locator_matches
from tests.conftest import call_or_skip


def pdf(page, src="textbook"):
    return {"source_id": src, "modality": "pdf", "locator": {"page": page}}


def video(a, b, src="lecture_03"):
    return {"source_id": src, "modality": "video", "locator": {"t_start": a, "t_end": b}}


def test_pdf_same_page_matches():
    assert call_or_skip(locator_matches, pdf(87), pdf(87)) is True
    assert call_or_skip(locator_matches, pdf(88), pdf(87)) is False


def test_different_source_never_matches():
    assert call_or_skip(locator_matches, pdf(87, "other"), pdf(87)) is False


def test_video_overlap_and_tolerance():
    assert call_or_skip(locator_matches, video(700, 760), video(742, 808)) is True
    assert call_or_skip(locator_matches, video(820, 860), video(742, 808)) is True   # 12 s gap
    assert call_or_skip(locator_matches, video(900, 960), video(742, 808)) is False  # 92 s gap


def test_accuracy_share():
    cited = [pdf(87), pdf(10)]
    gold = [pdf(87)]
    assert call_or_skip(citation_accuracy, cited, gold) == 0.5
    assert call_or_skip(citation_accuracy, [], gold) == 0.0
