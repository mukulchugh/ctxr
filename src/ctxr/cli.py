#!/usr/bin/env python3
"""ctxr: context from video, for agents.

Videos (YouTube, Vimeo, Loom, Wistia, X, TikTok, any site yt-dlp supports, direct media links, or local files)
-> transcript + unique frames + a Markdown walkthrough that puts each frame next to what was being said.

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
    rf"youtube\.com/shorts/({YT_ID})",
    rf"i\.ytimg\.com/vi/({YT_ID})",
]
ANY_ID = re.compile("|".join(f"(?:{p})" for p in ID_PATTERNS))
# other embeds a page may carry; each pattern's group 1 becomes a canonical url via EMBED_URL
EMBED_PATTERNS = {
    "vimeo": re.compile(r"(?:player\.)?vimeo\.com/(?:video/)?(\d{6,})"),
    "loom": re.compile(r"loom\.com/(?:share|embed)/([0-9a-f]{32})"),
    "wistia": re.compile(r"(?:wistia\.com/medias|wistia\.net/embed/iframe|wistia\.com/embed/iframe)/([a-z0-9]{10})"),
    "media": re.compile(r"""(?:src|href)=["'](https?://[^"'\s]+\.(?:mp4|webm|mov|m3u8)(?:\?[^"'\s]*)?)["']""", re.I),
}
EMBED_URL = {"vimeo": "https://vimeo.com/{}", "loom": "https://www.loom.com/share/{}",
             "wistia": "https://fast.wistia.net/embed/iframe/{}", "media": "{}"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
_whisper = None


# ---------- resolve links ----------
def ids_from_html(html):
    """Every video a page embeds, in document order: YouTube ids, plus canonical urls for other platforms."""
    seen, out = set(), []
    found = [(m.start(), next(g for g in m.groups() if g)) for m in ANY_ID.finditer(html)]
    for name, pat in EMBED_PATTERNS.items():
        found += [(m.start(), EMBED_URL[name].format(m.group(1))) for m in pat.finditer(html)]
    for _, item in sorted(found):
        if item not in seen:
            seen.add(item); out.append(item)
    return out


def ids_from_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return ids_from_html(urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"))


def ids_from_playlist(url):
    out = subprocess.run(YTDLP + ["--flat-playlist", "-j", url], capture_output=True, text=True, check=True).stdout
    entries = [json.loads(l) for l in out.splitlines() if l.strip()]
    return [e.get("url") or e["id"] for e in entries]


def parse_item(s):
    """What the user gave us: ("youtube", id) | ("url", url) | ("file", Path)."""
    m = ANY_ID.search(s)
    if m:
        return "youtube", next(g for g in m.groups() if g)
    if re.fullmatch(YT_ID, s):
        return "youtube", s
    if re.match(r"https?://", s):
        return "url", s
    p = Path(s).expanduser()
    if p.is_file() and p.suffix.lower() in VIDEO_EXT:
        return "file", p.resolve()
    sys.exit(f"not a video url, YouTube id, or local video file: {s}")


def parse_id(s):  # kept for callers that only understand YouTube ids
    kind, ref = parse_item(s)
    return ref if kind == "youtube" else s


# ---------- per-video steps ----------
SUB_EXT = (".json3", ".vtt", ".srt")


def download(kind, ref, tmp, proxy=None, cookies_from_browser=None):
    """Fetch the video and its captions into tmp. Returns (video_path, info, caption_files)."""
    if kind == "file":
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ref)],
                             capture_output=True, text=True).stdout.strip()
        info = {"id": ref.stem, "title": ref.stem, "extractor_key": "Local", "webpage_url": ref.as_uri(),
                "duration": int(float(dur or 0)), "upload_date": time.strftime("%Y%m%d", time.localtime(ref.stat().st_mtime))}
        subs = [p for p in ref.parent.glob(f"{ref.stem}*") if p.suffix.lower() in SUB_EXT]  # sidecar captions, if any
        return ref, info, subs
    url = f"https://www.youtube.com/watch?v={ref}" if kind == "youtube" else ref
    # ponytail: sites answer 403/429 on media URLs when rate-limited; "-t sleep" is yt-dlp's own anti-rate-limit preset
    # (0.75s between requests, 10-20s random pause before each download, 5s before subtitles); on failure back off and retry.
    # Retries stay on the default client: YouTube's ios/android clients need a PO token ctxr does not generate (docs/RATE-LIMITS.md).
    # Captions ride along in the same call (json3 on YouTube, vtt/srt elsewhere), so no separate caption requests are needed.
    for attempt, wait in enumerate([0, 15, 45, 90]):
        time.sleep(wait)
        cmd = YTDLP + ["-q", "--no-warnings", "-t", "sleep", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
               "--merge-output-format", "mp4", "--write-info-json",
               "--write-subs", "--write-auto-subs", "--sub-langs", "en.*", "--sub-format", "json3/vtt/srt/best",
               "-o", str(tmp / "v.%(ext)s")]
        if proxy:
            cmd += ["--proxy", proxy]
        if cookies_from_browser:  # some sites (Vimeo, at the time of writing) only serve logged-in clients
            cmd += ["--cookies-from-browser", cookies_from_browser]
        # -i: a failed caption download (the endpoint YouTube throttles first) must not fail the video
        r = subprocess.run(cmd + ["-i", url], capture_output=True, text=True)
        video = next((p for p in tmp.glob("v.*") if p.suffix.lower() in VIDEO_EXT), None)
        if video and (tmp / "v.info.json").exists():
            break
        err = (r.stderr.strip().splitlines() or ["?"])[-1]
        print(f"    download attempt {attempt + 1} failed: {err}")
    else:
        raise RuntimeError(f"yt-dlp failed after 4 attempts: {err}")
    return video, json.loads((tmp / "v.info.json").read_text()), [p for p in tmp.glob("v.*") if p.suffix in SUB_EXT]


def captions_json3(path):
    """Segments from a YouTube json3 caption file (what yt-dlp writes for --sub-format json3)."""
    segs = []
    for e in json.loads(path.read_text()).get("events", []):
        text = "".join(s.get("utf8", "") for s in e.get("segs", [])).replace("\n", " ").strip()
        if text and "tStartMs" in e:
            start = e["tStartMs"] / 1000
            segs.append({"start": start, "end": start + e.get("dDurationMs", 0) / 1000, "text": text})
    return segs


def captions_srt_vtt(path):
    """Segments from an SRT or WebVTT file (yt-dlp subtitles from most sites, or a sidecar next to a local file)."""
    ts = r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})"
    cue = re.compile(rf"{ts}\s*-->\s*{ts}")
    sec = lambda h, m, s, ms: (int(h) if h else 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    segs = []
    for block in re.split(r"\n\s*\n", path.read_text(errors="replace")):
        m = cue.search(block)
        if not m:
            continue
        text = " ".join(l.strip() for l in block[m.end():].splitlines() if l.strip())
        text = re.sub(r"<[^>]+>", "", text).replace("&nbsp;", " ").strip()
        if text and not (segs and segs[-1]["text"] == text):  # rolling captions repeat the previous line
            segs.append({"start": sec(*m.groups()[:4]), "end": sec(*m.groups()[4:]), "text": text})
    return segs


def captions_from(path):
    return captions_json3(path) if path.suffix == ".json3" else captions_srt_vtt(path)


def rank_captions(files):
    """Best first: json3 over vtt over srt; plain en over en-orig over other English variants."""
    def key(p):
        lang = p.name.split(".")[-2] if p.name.count(".") >= 2 else ""
        return (SUB_EXT.index(p.suffix.lower()) if p.suffix.lower() in SUB_EXT else 9, {"en": 0, "en-orig": 1}.get(lang, 2))
    return sorted(files, key=key)


def transcript_youtube(vid, proxy=None):
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import GenericProxyConfig
    api = YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy) if proxy else None)
    fetched = api.fetch(vid, languages=["en"])
    return [{"start": s.start, "end": s.start + s.duration, "text": s.text.replace("\n", " ").strip()} for s in fetched]


def has_audio(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def transcript_whisper(video, tmp):
    global _whisper
    if not has_audio(video):
        print("    no audio track; frames only")
        return []
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


_captions_blocked = False


def get_transcript(kind, ref, video, subs, tmp, args):
    global _captions_blocked
    if not args.whisper_all:
        for path in rank_captions(subs):
            segs = captions_from(path)
            if segs:
                return segs, "captions"
        if kind == "youtube" and not _captions_blocked:
            try:
                return transcript_youtube(ref, args.proxy), "youtube-transcript-api"
            except Exception as e:  # NoTranscriptFound, TranscriptsDisabled, IpBlocked, RequestBlocked, ...
                reason = type(e).__name__
                if reason in ("IpBlocked", "RequestBlocked"):
                    _captions_blocked = True  # ponytail: one block means the IP is flagged; stop asking for the rest of the batch
                print(f"    captions unavailable ({reason}); using local whisper")
        elif kind == "youtube":
            print("    caption endpoint blocked earlier in this run; using local whisper")
    segs = transcript_whisper(video, tmp)
    return segs, "whisper-small" if segs else "none"


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


def watch_url(url, t):
    """A link that opens the video at second t, or None for local files."""
    t = int(t)
    if not url or url.startswith("file:"):
        return None
    if "youtu" in url:
        return f"{url}?t={t}"
    if "vimeo.com" in url:
        return f"{url}#t={t}s"
    if "loom.com" in url:
        return f"{url}?t={t}"
    return f"{url}#t={t}"  # media fragment; honoured by direct files and several players


def video_url(kind, ref, info):
    if kind == "youtube":
        return f"https://youtu.be/{ref}"
    return info.get("webpage_url") or (ref if kind == "url" else Path(ref).as_uri())


def render(vid, info, source, aligned, page=None, url=None):
    url = url or f"https://youtu.be/{vid}"
    date = info.get("upload_date", "")
    L = [f"# {info.get('title', vid)}", "",
         f"- Video: {url}",
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
        link = watch_url(url, f["t"])
        L += [f"### {ts} ([watch]({link}))" if link else f"### {ts}", "",
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
def item_key(kind, ref, info=None):
    """Stable folder suffix: the YouTube id, or <platform>-<id> elsewhere, or the file stem."""
    if kind == "youtube":
        return ref
    if kind == "file":
        return slug(Path(ref).stem)
    if info:
        return f"{slug(info.get('extractor_key', 'video'))}-{slug(str(info.get('id', '')))}"
    return None


def process(item, out, args, page=None):
    kind, ref = parse_item(item) if isinstance(item, str) else item
    key = item_key(kind, ref)
    existing = next(out.glob(f"*-{key}"), None) if key else None
    if existing and (existing / "manifest.json").exists() and not args.force:
        print(f"  skip (done): {existing.name}"); return existing
    with tempfile.TemporaryDirectory(dir=out, prefix=".tmp-") as td:
        tmp = Path(td)
        video, info, subs = download(kind, ref, tmp, args.proxy, getattr(args, "cookies_from_browser", None))
        key = item_key(kind, ref, info)
        existing = next(out.glob(f"*-{key}"), None)
        if existing and (existing / "manifest.json").exists() and not args.force:
            print(f"  skip (done): {existing.name}"); return existing
        d = info.get("upload_date") or "00000000"
        name = slug(info.get("title") or key)
        folder = out / (f"{d[:4]}-{d[4:6]}-{d[6:8]}-{key}" if name in key else f"{d[:4]}-{d[4:6]}-{d[6:8]}-{name}-{key}")
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        try:
            return _build(kind, ref, key, info, video, subs, folder, tmp, args, page)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)  # no half-written folders; a rerun redoes this video
            raise


def _build(kind, ref, key, info, video, subs, folder, tmp, args, page):
    url = video_url(kind, ref, info)
    (folder / "info.json").write_text(json.dumps({k: info.get(k) for k in
        ("id", "title", "channel", "uploader", "upload_date", "duration", "description", "webpage_url", "extractor_key", "categories", "tags")}, indent=1))
    segments, source = get_transcript(kind, ref, video, subs, tmp, args)
    write_transcript(folder, segments)
    frames = extract_frames(video, folder / "frames", args.scene, args.min_gap, args.every)
    aligned = align(frames, segments)
    (folder / "README.md").write_text(render(key, info, source, aligned, page, url))
    (folder / "manifest.json").write_text(json.dumps({
        "id": key, "title": info.get("title"), "url": url, "platform": info.get("extractor_key", "Youtube"), "page": page,
        "upload_date": info.get("upload_date"), "duration": info.get("duration"),
        "transcript_source": source, "frame_params": {"scene": args.scene, "min_gap": args.min_gap, "every": args.every},
        "frames": aligned}, indent=1))
    if args.keep_video and kind != "file":
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
    assert parse_item("https://youtu.be/abcdefghijk?t=3") == ("youtube", "abcdefghijk")
    assert parse_item("https://www.youtube.com/watch?v=abcdefghijk&list=x") == ("youtube", "abcdefghijk")
    assert parse_item("https://vimeo.com/76979871") == ("url", "https://vimeo.com/76979871")
    html = ('<img src="https://i.ytimg.com/vi/o56Lz_J1V2o/max.jpg"><a href="https://www.youtube.com/watch?v=o56Lz_J1V2o">'
            '<iframe src="https://player.vimeo.com/video/76979871"></iframe><a href="https://www.loom.com/share/0123456789abcdef0123456789abcdef">'
            '<iframe src="https://fast.wistia.net/embed/iframe/abcde12345"></iframe><video src="https://cdn.example.com/a.mp4?x=1"></video>'
            '<a href="https://youtu.be/ESVG7uGPYPQ">')
    assert ids_from_html(html) == ["o56Lz_J1V2o", "https://vimeo.com/76979871", "https://www.loom.com/share/0123456789abcdef0123456789abcdef",
                                   "https://fast.wistia.net/embed/iframe/abcde12345", "https://cdn.example.com/a.mp4?x=1", "ESVG7uGPYPQ"], ids_from_html(html)
    assert (watch_url("https://youtu.be/x", 83), watch_url("https://vimeo.com/1", 83), watch_url("https://www.loom.com/share/a", 83),
            watch_url("https://cdn/a.mp4", 83.9), watch_url("file:///v.mp4", 5)) == \
           ("https://youtu.be/x?t=83", "https://vimeo.com/1#t=83s", "https://www.loom.com/share/a?t=83", "https://cdn/a.mp4#t=83", None)
    assert (fmt_ts(83), fmt_ts(3725), fmt_file(83), fmt_srt(83.5)) == ("01:23", "1:02:05", "01m23s", "00:01:23,500"), (fmt_ts(83), fmt_ts(3725), fmt_file(83), fmt_srt(83.5))
    with tempfile.TemporaryDirectory() as td:
        j = Path(td) / "abcdefghijk.en-orig.json3"
        j.write_text(json.dumps({"events": [{"tStartMs": 0, "wWinId": 1}, {"tStartMs": 500, "dDurationMs": 2000, "segs": [{"utf8": "hello"}, {"utf8": " there", "tOffsetMs": 300}]},
                                            {"tStartMs": 2500, "dDurationMs": 100, "aAppend": 1, "segs": [{"utf8": "\n"}]}]}))
        (Path(td) / "abcdefghijk.en.json3").write_text(json.dumps({"events": []}))
        assert captions_json3(j) == [{"start": 0.5, "end": 2.5, "text": "hello there"}], captions_json3(j)
        v = Path(td) / "v.en.vtt"
        v.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.500\n<c>Hello</c> world\n\n00:00:03.500 --> 00:00:05.000\nHello world\n\n00:01:02.000 --> 00:01:03.000\nnext\n")
        assert captions_srt_vtt(v) == [{"start": 1.0, "end": 3.5, "text": "Hello world"}, {"start": 62.0, "end": 63.0, "text": "next"}], captions_srt_vtt(v)
        srt = Path(td) / "v.srt"
        srt.write_text("1\n01:00:00,000 --> 01:00:01,000\nan hour in\n\n2\n01:00:01,000 --> 01:00:02,000\n\n")
        assert captions_srt_vtt(srt) == [{"start": 3600.0, "end": 3601.0, "text": "an hour in"}]
        assert [p.name for p in rank_captions([srt, v, j])] == ["abcdefghijk.en-orig.json3", "v.en.vtt", "v.srt"]
    md = render("abcdefghijk", {"title": "T", "upload_date": "20260921", "duration": 40}, "youtube", a)
    assert "### 00:10 ([watch](https://youtu.be/abcdefghijk?t=10))" in md and "![00:10](frames/b.jpg)\n\nthree" in md, md
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser(prog="ctxr", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"ctxr {__version__}")
    ap.add_argument("items", nargs="*", help="video urls (YouTube, Vimeo, Loom, Wistia, X, TikTok, direct mp4/m3u8, any yt-dlp site), YouTube ids, or local video files")
    ap.add_argument("--page", action="append", default=[], help="scrape every embedded video from this page")
    ap.add_argument("--playlist", action="append", default=[], help="expand a playlist/channel url (any yt-dlp site)")
    ap.add_argument("--out", default="./ctxr-out", help="output folder (default ./ctxr-out)")
    ap.add_argument("--scene", type=float, default=0.05, help="scene-change threshold 0..1 (lower = more frames); 0.05 suits UI screen recordings")
    ap.add_argument("--min-gap", type=float, default=10, help="also take a frame at least every N seconds")
    ap.add_argument("--every", type=float, default=None, help="fixed grid every N seconds instead of scene detection")
    ap.add_argument("--keep-video", action="store_true")
    ap.add_argument("--whisper-all", action="store_true", help="transcribe locally even when captions exist")
    ap.add_argument("--proxy", default=None, metavar="URL", help="HTTP/HTTPS/SOCKS proxy for yt-dlp and the caption client, e.g. a rotating residential gateway")
    ap.add_argument("--cookies-from-browser", default=None, metavar="BROWSER", help="let yt-dlp use your browser login (chrome, firefox, safari, ...) for sites that require it, such as Vimeo")
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
    ids += [(s, None) for s in args.items]
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
