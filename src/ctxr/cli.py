#!/usr/bin/env python3
"""ctxr: context from video, for agents.

YouTube videos -> transcript + unique frames + a Markdown walkthrough that puts each frame next to what was being said.

Per video:  yt-dlp (720p mp4) -> youtube-transcript-api (English captions, local faster-whisper
fallback) -> ffmpeg scene-change frames -> README.md that puts each frame next to what was
being said, plus manifest.json for programmatic use. Index over all videos at the end.
"""
import argparse, json, re, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

__version__ = "0.1.0"
YTDLP = [sys.executable, "-m", "yt_dlp"]  # the module, not a PATH binary, so it works inside any env ctxr is installed in

YT_ID = r"[A-Za-z0-9_-]{11}"
ID_PATTERNS = [
    rf"youtube\.com/watch\?v=({YT_ID})",
    rf"youtu\.be/({YT_ID})",
    rf"youtube(?:-nocookie)?\.com/embed/({YT_ID})",
    rf"i\.ytimg\.com/vi/({YT_ID})",
]
ANY_ID = re.compile("|".join(f"(?:{p})" for p in ID_PATTERNS))
_whisper = None


# ---------- resolve links ----------
def ids_from_html(html):
    seen, out = set(), []
    for m in ANY_ID.finditer(html):
        vid = next(g for g in m.groups() if g)
        if vid not in seen:
            seen.add(vid); out.append(vid)
    return out


def ids_from_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return ids_from_html(urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"))


def ids_from_playlist(url):
    out = subprocess.run(YTDLP + ["--flat-playlist", "-j", url], capture_output=True, text=True, check=True).stdout
    return [json.loads(l)["id"] for l in out.splitlines() if l.strip()]


def parse_id(s):
    m = ANY_ID.search(s)
    if m:
        return next(g for g in m.groups() if g)
    if re.fullmatch(YT_ID, s):
        return s
    sys.exit(f"not a YouTube id/url: {s}")


# ---------- per-video steps ----------
def download(vid, tmp):
    # ponytail: YouTube answers 403 on media URLs when rate-limited; "-t sleep" is yt-dlp's own anti-rate-limit preset
    # (0.75s between requests, 10-20s random pause before each download, 5s before subtitles); on failure back off + switch client
    for attempt, (wait, client) in enumerate([(0, None), (15, "ios"), (45, "android"), (90, None)]):
        time.sleep(wait)
        cmd = YTDLP + ["-q", "--no-warnings", "-t", "sleep", "-f", "bv*[height<=720]+ba/b[height<=720]",
               "--merge-output-format", "mp4", "--write-info-json", "-o", str(tmp / f"{vid}.%(ext)s")]
        if client:
            cmd += ["--extractor-args", f"youtube:player_client={client}"]
        r = subprocess.run(cmd + [f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True)
        if r.returncode == 0:
            break
        err = (r.stderr.strip().splitlines() or ["?"])[-1]
        print(f"    download attempt {attempt + 1} failed: {err}")
    else:
        raise RuntimeError(f"yt-dlp failed after 4 attempts: {err}")
    info = json.loads((tmp / f"{vid}.info.json").read_text())
    video = next(p for p in tmp.glob(f"{vid}.*") if p.suffix != ".json")
    return video, info


def transcript_youtube(vid):
    from youtube_transcript_api import YouTubeTranscriptApi
    fetched = YouTubeTranscriptApi().fetch(vid, languages=["en"])
    return [{"start": s.start, "end": s.start + s.duration, "text": s.text.replace("\n", " ").strip()} for s in fetched]


def transcript_whisper(video, tmp):
    global _whisper
    wav = tmp / "audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    if _whisper is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("no usable English captions and faster-whisper is not installed; install with: uv tool install 'ctxr[whisper]'")
        _whisper = WhisperModel("small", compute_type="int8")  # ponytail: small is cached locally; bump to large-v3 if accuracy matters
    segs, _ = _whisper.transcribe(str(wav), language="en", vad_filter=True)
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs]


def get_transcript(vid, video, tmp, whisper_all):
    if not whisper_all:
        for attempt in (1, 2):
            try:
                return transcript_youtube(vid), "youtube"
            except Exception as e:  # NoTranscriptFound, TranscriptsDisabled, IpBlocked, ...
                reason = type(e).__name__
                if reason in ("NoTranscriptFound", "TranscriptsDisabled", "InvalidVideoId"):
                    break
                time.sleep(5)
        print(f"    captions unavailable ({reason}); using local whisper")
    return transcript_whisper(video, tmp), "whisper-small"


def extract_frames(video, frames_dir, scene, min_gap, every):
    frames_dir.mkdir(exist_ok=True)
    sel = (f"isnan(prev_selected_t)+gte(t-prev_selected_t,{every})" if every
           else f"gt(scene,{scene})*gte(t-prev_selected_t,1.5)+isnan(prev_selected_t)+gte(t-prev_selected_t,{min_gap})")
    # ponytail: 0.05 + 1.5s debounce calibrated on a 2.5-minute product-demo screen recording (23 distinct screens); tune --scene per source
    vf = f"select='{sel}',showinfo,scale=1280:-2"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "info", "-i", str(video), "-vf", vf, "-fps_mode", "vfr",
                        "-q:v", "4", str(frames_dir / "%04d.jpg")], capture_output=True, text=True, check=True)
    times = [float(t) for t in re.findall(r"pts_time:\s*([0-9.]+)", r.stderr)]
    files = sorted(frames_dir.glob("[0-9][0-9][0-9][0-9].jpg"))
    if len(times) != len(files):
        print(f"    warning: {len(times)} timestamps vs {len(files)} frames; zipping")
    frames = []
    for f, t in zip(files, times):
        new = f.with_name(f"{f.stem}_{fmt_file(t)}.jpg")
        f.rename(new)
        frames.append({"t": round(t, 2), "file": new.name})
    return frames


# ---------- align + render ----------
def align(frames, segments):
    """Each segment goes under the last frame shown at or before the segment starts."""
    out = [dict(f, segments=[]) for f in frames]
    if not out:
        return out
    j = 0
    for seg in sorted(segments, key=lambda s: s["start"]):
        while j + 1 < len(out) and out[j + 1]["t"] <= seg["start"]:
            j += 1
        out[j]["segments"].append(seg)
    return out


def fmt_ts(t):
    t = int(t); h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_file(t):
    t = int(t); h, m, s = t // 3600, t % 3600 // 60, t % 60
    return (f"{h}h" if h else "") + f"{m:02d}m{s:02d}s"


def fmt_srt(t):
    ms = int(round(t * 1000)); h, r = divmod(ms, 3600000); m, r = divmod(r, 60000); s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render(vid, info, source, aligned, page=None):
    date = info.get("upload_date", "")
    L = [f"# {info.get('title', vid)}", "",
         f"- YouTube: https://youtu.be/{vid}",
         *([f"- Source page: {page}"] if page else []),
         f"- Channel: {info.get('channel') or info.get('uploader', '')}",
         f"- Published: {date[:4]}-{date[4:6]}-{date[6:]}" if len(date) == 8 else f"- Published: {date}",
         f"- Duration: {fmt_ts(info.get('duration') or 0)}",
         f"- Transcript source: {source}",
         f"- Frames: {len(aligned)}", "",
         "## Description", "", (info.get("description") or "").strip() or "_(none)_", "",
         "## Walkthrough", "",
         "Each frame is followed by what is being said while it is on screen.", ""]
    for f in aligned:
        ts = fmt_ts(f["t"])
        text = " ".join(s["text"] for s in f["segments"]).strip()
        L += [f"### {ts} ([watch](https://youtu.be/{vid}?t={int(f['t'])}))", "",
              f"![{ts}](frames/{f['file']})", "", text or "_(no narration)_", ""]
    return "\n".join(L)


def write_transcript(folder, segments):
    (folder / "transcript.json").write_text(json.dumps(segments, indent=1))
    (folder / "transcript.txt").write_text("\n".join(f"[{fmt_ts(s['start'])}] {s['text']}" for s in segments) + "\n")
    srt = [f"{i}\n{fmt_srt(s['start'])} --> {fmt_srt(s['end'])}\n{s['text']}\n" for i, s in enumerate(segments, 1)]
    (folder / "transcript.srt").write_text("\n".join(srt))


def slug(s, n=50):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n].rstrip("-")


# ---------- orchestration ----------
def process(vid, out, args, page=None):
    existing = next(out.glob(f"*-{vid}"), None)
    if existing and (existing / "manifest.json").exists() and not args.force:
        print(f"  skip (done): {existing.name}"); return existing
    with tempfile.TemporaryDirectory(dir=out, prefix=".tmp-") as td:
        tmp = Path(td)
        video, info = download(vid, tmp)
        d = info.get("upload_date") or "00000000"
        folder = out / f"{d[:4]}-{d[4:6]}-{d[6:8]}-{slug(info.get('title', vid))}-{vid}"
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        try:
            return _build(vid, info, video, folder, tmp, args, page)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)  # no half-written folders; a rerun redoes this video
            raise


def _build(vid, info, video, folder, tmp, args, page):
    (folder / "info.json").write_text(json.dumps({k: info.get(k) for k in
        ("id", "title", "channel", "uploader", "upload_date", "duration", "description", "webpage_url", "categories", "tags")}, indent=1))
    segments, source = get_transcript(vid, video, tmp, args.whisper_all)
    write_transcript(folder, segments)
    frames = extract_frames(video, folder / "frames", args.scene, args.min_gap, args.every)
    aligned = align(frames, segments)
    (folder / "README.md").write_text(render(vid, info, source, aligned, page))
    (folder / "manifest.json").write_text(json.dumps({
        "id": vid, "title": info.get("title"), "url": f"https://youtu.be/{vid}", "page": page,
        "upload_date": info.get("upload_date"), "duration": info.get("duration"),
        "transcript_source": source, "frame_params": {"scene": args.scene, "min_gap": args.min_gap, "every": args.every},
        "frames": aligned}, indent=1))
    if args.keep_video:
        shutil.move(str(video), folder / video.name)
    print(f"  ok: {folder.name}  transcript={source} segments={len(segments)} frames={len(frames)}")
    return folder


def write_index(out, pending=()):
    rows, docs = [], []
    for mf in sorted(out.glob("*/manifest.json")):
        m = json.loads(mf.read_text()); d = mf.parent
        date = m.get("upload_date") or ""
        rows.append((date, f"| {date[:4]}-{date[4:6]}-{date[6:]} | [{m['title']}]({d.name}/README.md) | {fmt_ts(m.get('duration') or 0)} | {len(m['frames'])} | {m['transcript_source']} |"))
        docs.append((date, (d / "README.md").read_text().replace("](frames/", f"]({d.name}/frames/")))
    rows.sort(); docs.sort(key=lambda x: x[0])
    (out / "INDEX.md").write_text("# Demo videos\n\n| Date | Title | Length | Frames | Transcript |\n|---|---|---|---|---|\n" + "\n".join(r for _, r in rows) + "\n")
    (out / "ALL-DEMOS.md").write_text("\n\n---\n\n".join(doc for _, doc in docs) + "\n")
    still = f", {len(pending)} still pending" if pending else ""
    pend = ("\n## Pending\n\n" + "".join(f"- {t} (`{v}`)\n" for v, t in pending)) if pending else ""
    (out / "README.md").write_text(f"""# How to learn from this folder

{len(rows)} demo videos processed{still}. Each video is one folder named `<date>-<title>-<youtube-id>/`.

Start with `INDEX.md` (one row per video, newest last). For a single video open its `README.md`: the header gives title, link, date, length and the description, then a `## Walkthrough` with one section per distinct screen. Each section is a timestamp linked to that second on YouTube, the frame image, and the words spoken while that frame was on screen. Read it top to bottom and you get the whole demo, visuals and narration, in order.

`ALL-DEMOS.md` is every README joined into one file (image paths already rewritten relative to this folder) for one-shot ingestion.

Machine-readable, per video:
- `manifest.json`: `frames[]` with `t` (seconds), `file`, and the `segments[]` (`start`, `end`, `text`) aligned under that frame; plus `transcript_source` (`youtube` captions or `whisper-small` local transcription).
- `transcript.json` / `.srt` / `.txt`: the full transcript with timestamps.
- `info.json`: YouTube metadata (title, channel, upload date, duration, description, tags).
- `frames/NNNN_MMmSSs.jpg`: 1280px-wide frames captured on visible screen changes, at least one every 10 seconds.

Transcripts are automatic (YouTube captions or Whisper), so expect occasional misheard product terms; the frames are the ground truth for UI labels.
{pend}""")
    return len(rows)


def self_test():
    frames = [{"t": 0.0, "file": "a.jpg"}, {"t": 10.0, "file": "b.jpg"}, {"t": 25.0, "file": "c.jpg"}]
    segs = [{"start": 0.5, "end": 3, "text": "one"}, {"start": 9.9, "end": 12, "text": "two"},
            {"start": 10.0, "end": 14, "text": "three"}, {"start": 30, "end": 31, "text": "four"}]
    a = align(frames, segs)
    assert [[s["text"] for s in f["segments"]] for f in a] == [["one", "two"], ["three"], ["four"]], a
    assert parse_id("https://youtu.be/abcdefghijk?t=3") == "abcdefghijk"
    assert parse_id("https://www.youtube.com/watch?v=abcdefghijk&list=x") == "abcdefghijk"
    html = '<img src="https://i.ytimg.com/vi/o56Lz_J1V2o/max.jpg"><a href="https://www.youtube.com/watch?v=o56Lz_J1V2o"><a href="https://youtu.be/ESVG7uGPYPQ">'
    assert ids_from_html(html) == ["o56Lz_J1V2o", "ESVG7uGPYPQ"], ids_from_html(html)
    assert (fmt_ts(83), fmt_ts(3725), fmt_file(83), fmt_srt(83.5)) == ("01:23", "1:02:05", "01m23s", "00:01:23,500"), (fmt_ts(83), fmt_ts(3725), fmt_file(83), fmt_srt(83.5))
    md = render("abcdefghijk", {"title": "T", "upload_date": "20260921", "duration": 40}, "youtube", a)
    assert "### 00:10 ([watch](https://youtu.be/abcdefghijk?t=10))" in md and "![00:10](frames/b.jpg)\n\nthree" in md, md
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser(prog="ctxr", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"ctxr {__version__}")
    ap.add_argument("items", nargs="*", help="video ids or urls")
    ap.add_argument("--page", action="append", default=[], help="scrape every YouTube id from this page")
    ap.add_argument("--playlist", action="append", default=[], help="expand a playlist/channel url")
    ap.add_argument("--out", default="./ctxr-out", help="output folder (default ./ctxr-out)")
    ap.add_argument("--scene", type=float, default=0.05, help="scene-change threshold 0..1 (lower = more frames); 0.05 suits UI screen recordings")
    ap.add_argument("--min-gap", type=float, default=10, help="also take a frame at least every N seconds")
    ap.add_argument("--every", type=float, default=None, help="fixed grid every N seconds instead of scene detection")
    ap.add_argument("--keep-video", action="store_true")
    ap.add_argument("--whisper-all", action="store_true", help="transcribe locally even when captions exist")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cooldown", type=float, default=5, help="seconds to pause after each video, on top of yt-dlp's sleep preset")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH (brew install ffmpeg / apt install ffmpeg)")

    ids = []
    for p in args.page:
        found = ids_from_page(p); print(f"{p}: {len(found)} videos"); ids += [(v, p) for v in found]
    for p in args.playlist:
        ids += [(v, p) for v in ids_from_playlist(p)]
    ids += [(parse_id(s), None) for s in args.items]
    seen = set(); ids = [x for x in ids if not (x[0] in seen or seen.add(x[0]))][: args.limit]
    if not ids:
        ap.error("nothing to do: pass ids/urls, --page or --playlist")
    out = Path(args.out).expanduser(); out.mkdir(parents=True, exist_ok=True)

    failures = []
    for i, (vid, page) in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {vid}", flush=True)
        try:
            process(vid, out, args, page)
        except Exception as e:
            failures.append((vid, f"{type(e).__name__}: {e}")); print(f"  FAILED {vid}: {type(e).__name__}: {e}", flush=True)
        time.sleep(args.cooldown)
    n = write_index(out, [(v, v) for v, _ in failures])
    print(f"\ndone: {n} videos indexed in {out}; {len(failures)} failed")
    for vid, err in failures:
        print(f"  {vid}: {err}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
