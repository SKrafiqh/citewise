#!/usr/bin/env bash
# Downloads the course material into data/raw/. Run from the repo root.
# Needs: curl, and yt-dlp for captions (pip install yt-dlp).
set -euo pipefail

RAW="data/raw"
mkdir -p "$RAW/videos" "$RAW/captions" "$RAW/slides" "$RAW/textbook"

# MIT OCW 6.041 Fall 2010 (CC BY-NC-SA 4.0), lectures 1-3
# (plain function instead of `declare -A`, which macOS's bash 3.2 does not support)
lecture_id() {
  case "$1" in
    lec01) echo "j9WZyLZCBzs" ;;   # Probability Models and Axioms
    lec02) echo "TluTv5V0RmE" ;;   # Conditioning and Bayes' Rule
    lec03) echo "19Ql_Q3l0GA" ;;   # Independence
  esac
}

echo "== Lecture slides (all lectures, one PDF) =="
curl -fL -o "$RAW/slides/mit6041_lec_slides.pdf" \
  "https://ocw.mit.edu/courses/6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010/60eede37f87fd886d4ba574e1cf26617_MIT6_041F10_lec_slides.pdf"

for lec in lec01 lec02 lec03; do
  id="$(lecture_id "$lec")"
  echo "== $lec video (archive.org mirror) =="
  curl -fL -o "$RAW/videos/$lec.mp4" \
    "https://archive.org/download/MIT6.041F10/MIT6_041F11_${lec}_300k.mp4" \
    || echo "!! $lec video download failed; download it from the OCW lecture page instead"

  echo "== $lec captions (YouTube) =="
  if command -v yt-dlp >/dev/null 2>&1; then
    yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "en.*" \
      --sub-format vtt -o "$RAW/captions/$lec.%(ext)s" "https://www.youtube.com/watch?v=$id" \
      || echo "!! captions failed for $lec; video.py will fall back to Whisper"
  else
    echo "!! yt-dlp not installed; skipping captions (pip install yt-dlp)"
  fi
done

cat <<'MSG'

Done. One manual step left:
  Textbook: OpenStax "Introductory Statistics 2e" (CC BY 4.0)
  1. Open https://openstax.org/details/books/introductory-statistics-2e
  2. Click "Download a PDF" and save it as data/raw/textbook/openstax_intro_stats_2e.pdf
  3. Note the PDF page range of Chapter 3 "Probability Topics" for --pages

YouTube ids (for --youtube-id): lec01 j9WZyLZCBzs, lec02 TluTv5V0RmE, lec03 19Ql_Q3l0GA
MSG
