#!/usr/bin/env bash
# Builds the whole knowledge base: slides, 3 lectures, textbook (if present), concept graph, tags.
# Run from the repo root after `bash scripts/download_material.sh`:
#
#   TEXTBOOK_PAGES=120-170 bash scripts/ingest_all.sh
#
# TEXTBOOK_PAGES = PDF page range of OpenStax chapter 3 "Probability Topics" (open the PDF, note the
# first and last page numbers your viewer shows). Every LLM call is cached, so re-running is cheap.
set -euo pipefail
cd "$(dirname "$0")/../backend"
PY=".venv/bin/python"
RAW="../data/raw"
MIT="CC BY-NC-SA 4.0"

$PY -m app.ingest.slides "$RAW/slides/mit6041_lec_slides.pdf" slides \
  --title "MIT 6.041 lecture slides (lectures 1-3)" --license "$MIT" --pages 2-7

# the *.en-en*.vtt files are YouTube's human-made captions (clean, punctuated); *.en.vtt is auto-generated
caption() { ls "$RAW"/captions/"$1".en-en*.vtt | head -1; }
$PY -m app.ingest.video "$RAW/videos/lec01.mp4" lecture_01 --title "MIT 6.041 Lecture 1: Probability Models and Axioms" \
  --license "$MIT" --captions "$(caption lec01)" --youtube-id j9WZyLZCBzs
$PY -m app.ingest.video "$RAW/videos/lec02.mp4" lecture_02 --title "MIT 6.041 Lecture 2: Conditioning and Bayes' Rule" \
  --license "$MIT" --captions "$(caption lec02)" --youtube-id TluTv5V0RmE
$PY -m app.ingest.video "$RAW/videos/lec03.mp4" lecture_03 --title "MIT 6.041 Lecture 3: Independence" \
  --license "$MIT" --captions "$(caption lec03)" --youtube-id 19Ql_Q3l0GA

BOOK="$RAW/textbook/openstax_intro_stats_2e.pdf"
if [ -f "$BOOK" ]; then
  : "${TEXTBOOK_PAGES:?set TEXTBOOK_PAGES to the PDF page range of chapter 3, e.g. TEXTBOOK_PAGES=120-170}"
  $PY -m app.ingest.pdf "$BOOK" textbook --title "OpenStax Introductory Statistics 2e, ch. 3" \
    --license "CC BY 4.0" --pages "$TEXTBOOK_PAGES"
else
  echo "!! $BOOK not found: building the graph from slides and lectures only."
  echo "!! Add the textbook later with: python -m app.ingest.pdf ... then python -m app.kb.concepts --force && python -m app.kb.tagging"
fi

$PY -m app.kb.concepts
$PY -m app.kb.tagging
echo "Knowledge base ready. Next: python -m app.assess.bank --per-concept 4   (needs your app/assess/dedup.py)"
