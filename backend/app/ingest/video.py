"""Video ingestion: captions (or Whisper) -> 60-90 s windows, plus keyframe descriptions."""
import argparse
import json
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.ingest.store import UnitIn, ingest_source
from app.llm import generate

log = logging.getLogger(__name__)

MIN_WINDOW_S = 60
MAX_WINDOW_S = 90
SCENE_THRESHOLD = 0.3
MIN_KEYFRAME_GAP_S = 20
MAX_KEYFRAMES = 40  # caps vision cost per video
_TIME = re.compile(r"(?:(\d+):)?(\d+):(\d+)[.,](\d+)")
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


def _seconds(stamp: str) -> float:
    h, m, s, ms = _TIME.fullmatch(stamp.strip()).groups()
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


def parse_vtt(text: str) -> list[Segment]:
    """Parse WebVTT; drops the repeated lines of YouTube rolling captions."""
    segments: list[Segment] = []
    last_line = ""
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [ln for ln in block.strip().split("\n") if ln.strip()]
        timing = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if timing is None:
            continue
        start, end = (part.split()[0] for part in lines[timing].split("-->"))
        for raw in lines[timing + 1 :]:
            line = _TAGS.sub("", raw).strip()
            if line and line != last_line:
                segments.append(Segment(_seconds(start), _seconds(end), line))
                last_line = line
    return segments


def load_segments_json(path: Path) -> list[Segment]:
    """Precomputed segments, e.g. from Whisper on Colab: [{"start":0,"end":4.2,"text":"..."}]."""
    return [Segment(float(s["start"]), float(s["end"]), s["text"].strip()) for s in json.loads(path.read_text("utf-8"))]


def transcribe(video: Path) -> list[Segment]:
    from faster_whisper import WhisperModel  # optional dependency (pip install faster-whisper)

    model = WhisperModel(get_settings().whisper_model, compute_type="int8")
    segments, _ = model.transcribe(str(video))
    return [Segment(s.start, s.end, s.text.strip()) for s in segments]


def merge_windows(segments: list[Segment]) -> list[tuple[int, int, str]]:
    """Group segments into 60-90 s windows that end at a sentence boundary when one is available."""
    windows: list[tuple[int, int, str]] = []
    group: list[Segment] = []

    def flush() -> None:
        if group:
            windows.append((int(group[0].start), int(group[-1].end + 0.999), " ".join(s.text for s in group)))
            group.clear()

    for seg in segments:
        if group and seg.end - group[0].start > MAX_WINDOW_S:
            flush()
        group.append(seg)
        if seg.end - group[0].start >= MIN_WINDOW_S and seg.text.rstrip().endswith((".", "?", "!")):
            flush()
    flush()
    return windows


def parse_showinfo(stderr: str) -> list[float]:
    return [float(t) for t in re.findall(r"pts_time:([0-9.]+)", stderr)]


def pick_keyframes(times: list[float]) -> list[int]:
    """Indexes of keyframes to keep: at least MIN_KEYFRAME_GAP_S apart, at most MAX_KEYFRAMES."""
    kept: list[int] = []
    for i, t in enumerate(times):
        if not kept or t - times[kept[-1]] >= MIN_KEYFRAME_GAP_S:
            kept.append(i)
    if len(kept) > MAX_KEYFRAMES:
        step = len(kept) / MAX_KEYFRAMES
        kept = [kept[int(i * step)] for i in range(MAX_KEYFRAMES)]
    return kept


def describe_keyframes(video: Path, workdir: Path) -> list[tuple[float, str]]:
    prompt = (get_settings().prompts_dir / "slide_read.md").read_text(encoding="utf-8")
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
         f"select='gt(scene,{SCENE_THRESHOLD})',showinfo,scale=960:-2", "-fps_mode", "vfr",
         str(workdir / "f%04d.jpg")],
        capture_output=True, text=True, timeout=1800,
    )
    times = parse_showinfo(result.stderr)
    out: list[tuple[float, str]] = []
    for index in pick_keyframes(times):
        frame = workdir / f"f{index + 1:04d}.jpg"
        try:
            out.append((times[index], generate(prompt, images=[frame]).strip()))
        except Exception:
            log.warning("keyframe description failed at %.0fs", times[index], exc_info=True)
    return out


def attach_keyframes(windows: list[tuple[int, int, str]], frames: list[tuple[float, str]]) -> list[UnitIn]:
    units = []
    for start, end, text in windows:
        inside = [desc for t, desc in frames if start <= t < end]
        units.append(UnitIn({"t_start": start, "t_end": end}, text, "\n".join(inside) or None))
    return units


def build_units(video: Path, captions: Path | None, segments_json: Path | None) -> list[UnitIn]:
    if captions:
        segments = parse_vtt(captions.read_text(encoding="utf-8"))
    elif segments_json:
        segments = load_segments_json(segments_json)
    else:
        segments = transcribe(video)
    with tempfile.TemporaryDirectory() as tmp:
        frames = describe_keyframes(video, Path(tmp)) if shutil.which("ffmpeg") else []
    return attach_keyframes(merge_windows(segments), frames)


def ingest_video(
    video: Path, source_id: str, title: str, license: str | None,
    *, captions: Path | None = None, segments_json: Path | None = None, youtube_id: str | None = None,
) -> int:
    uri = f"youtube:{youtube_id}" if youtube_id else f"file:{video.name}"
    return ingest_source(
        source_id, title=title, modality="video", uri=uri, license=license,
        build_units=lambda: build_units(video, captions, segments_json),
    )


def ingest_youtube_url(url: str, source_id: str, title: str, license: str | None) -> int:
    """Download a low-resolution copy and its English captions with yt-dlp, then ingest."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        subprocess.run(
            ["yt-dlp", "--no-config", "-f", "best[height<=360]/worst", "--write-subs", "--write-auto-subs",
             "--sub-langs", "en.*", "--sub-format", "vtt", "--no-playlist",
             "-o", str(folder / "video.%(ext)s"), "--", url],
            check=True, capture_output=True, timeout=1800,
        )
        video = next(p for p in folder.iterdir() if p.suffix in {".mp4", ".webm", ".mkv"})
        captions = next(iter(sorted(folder.glob("*.vtt"))), None)
        match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
        return ingest_video(video, source_id, title, license, captions=captions,
                            youtube_id=match[1] if match else None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a lecture video into the knowledge base")
    parser.add_argument("path", type=Path)
    parser.add_argument("source_id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--license", default=None)
    parser.add_argument("--captions", type=Path, default=None, help="WebVTT captions")
    parser.add_argument("--segments-json", type=Path, default=None, help="precomputed Whisper segments")
    parser.add_argument("--youtube-id", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    count = ingest_video(args.path, args.source_id, args.title, args.license,
                         captions=args.captions, segments_json=args.segments_json, youtube_id=args.youtube_id)
    print(f"ingested {count} units")


if __name__ == "__main__":
    main()
