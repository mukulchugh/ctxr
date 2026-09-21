"""ctxr MCP server: lets any MCP client (Claude Code, Codex, Cursor, ...) turn videos into context and query it.

Run over stdio:  ctxr-mcp   (or: uvx --from 'ctxr[mcp]' ctxr-mcp)
Output folder:   --out per call, else $CTXR_OUT, else ~/ctxr
"""
import argparse, json, logging, os, re, subprocess, sys
from pathlib import Path

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver import Context, Image
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from . import cli

log = logging.getLogger("ctxr.mcp")
READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True)

INSTRUCTIONS = """ctxr turns videos (YouTube, Vimeo, Loom, Wistia, X, TikTok, direct links, local files) into context an agent can read: per video, a transcript, frames where the
screen changed, and a walkthrough that puts each frame next to what was being said.

Typical flow: ctxr_find (search YouTube or list a channel/playlist) -> ctxr_process (urls, local files, a playlist, or
every video on a page) -> ctxr_index to see what exists -> ctxr_search / ctxr_walkthrough / ctxr_frame to read it. For more than a handful of videos pass background=true and
poll ctxr_status; YouTube rate-limits, so a page of 70 videos takes about an hour. The learn_from_videos prompt is a
ready-made study plan over a processed folder; skill_from_videos turns one into an installable SKILL.md."""

mcp = MCPServer("ctxr", instructions=INSTRUCTIONS, version=cli.__version__)


class Video(BaseModel):
    id: str
    title: str
    date: str
    duration_s: int
    frames: int
    transcript_source: str
    folder: str
    url: str


class Section(BaseModel):
    t: float
    timestamp: str
    frame: str
    text: str


class Hit(BaseModel):
    video: str
    title: str
    t: float
    timestamp: str
    text: str
    frame: str
    watch: str
    score: float = 0


class Found(BaseModel):
    url: str
    title: str | None
    duration_s: int | None
    channel: str | None
    views: int | None


class ProcessResult(BaseModel):
    out: str
    requested: int
    done: int
    failed: list[str]
    background: bool
    log: str | None = None
    note: str


class Status(BaseModel):
    out: str
    running: bool
    done: int
    failed: list[str]
    last_lines: list[str]


def _out(out: str | None) -> Path:
    p = Path(out or os.environ.get("CTXR_OUT") or "~/ctxr").expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _manifests(out: Path):
    for mf in sorted(out.glob("*/manifest.json")):
        yield mf.parent, json.loads(mf.read_text())


def _video(out: Path, video: str) -> tuple[Path, dict]:
    hits = [(d, m) for d, m in _manifests(out) if m["id"] == video or video.lower() in (m.get("title") or "").lower() or video == d.name]
    if len(hits) != 1:
        raise ValueError(f"{'no' if not hits else len(hits)} videos match {video!r} in {out}; use the id from ctxr_index")
    return hits[0]


def _date(m: dict) -> str:
    d = m.get("upload_date") or ""
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d


def _section(f: dict) -> Section:
    return Section(t=f["t"], timestamp=cli.fmt_ts(f["t"]), frame=f["file"], text=" ".join(s["text"] for s in f["segments"]).strip())


def _resolve(items, page, playlist):
    ids = []
    if page:
        ids += [(v, page) for v in cli.ids_from_page(page)]
    if playlist:
        ids += [(v, playlist) for v in cli.ids_from_playlist(playlist)]
    ids += [(s, None) for s in items or []]
    seen = set()
    return [x for x in ids if not (x[0] in seen or seen.add(x[0]))]


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True, open_world_hint=True))
async def ctxr_process(
    ctx: Context,
    items: list[str] | None = None,
    page: str | None = None,
    playlist: str | None = None,
    out: str | None = None,
    limit: int | None = None,
    whisper_all: bool = False,
    vocab: str | None = None,
    whisper_model: str = "small",
    proxy: str | None = None,
    background: bool = False,
) -> ProcessResult:
    """Turn videos into context. items takes YouTube ids or urls, urls from any site yt-dlp supports (Vimeo, Loom,
    Wistia, X, TikTok, Google Drive, Dropbox, direct mp4/m3u8 links) and local video file paths; playlist takes a
    playlist or channel url; page takes a web page (every video embedded on it is processed). Already-processed videos are skipped. Inline mode reports
    progress per video and returns when done; background=true returns at once and ctxr_status reports progress
    (use it for more than ~5 videos). vocab is a comma-separated list of names (brands, products, people) that local
    transcription must spell correctly; the channel and title are added automatically. whisper_model: small (default),
    medium or large-v3 for harder audio. proxy routes yt-dlp and caption requests through an HTTP/SOCKS proxy."""
    o = _out(out)
    ids = _resolve(items, page, playlist)[:limit]
    if not ids:
        raise ValueError("nothing to process: pass items, page or playlist")
    if background:
        cmd = [sys.executable, "-m", "ctxr.cli", "--out", str(o)] + (["--page", page] if page else []) + \
              (["--playlist", playlist] if playlist else []) + (items or []) + (["--limit", str(limit)] if limit else []) + \
              (["--whisper-all"] if whisper_all else []) + (["--proxy", proxy] if proxy else []) + \
              (["--vocab", vocab] if vocab else []) + (["--whisper-model", whisper_model] if whisper_model != "small" else [])
        logf = o / "ctxr.log"
        proc = subprocess.Popen(cmd, stdout=open(logf, "ab"), stderr=subprocess.STDOUT, start_new_session=True)
        (o / "ctxr.pid").write_text(str(proc.pid))
        return ProcessResult(out=str(o), requested=len(ids), done=0, failed=[], background=True, log=str(logf),
                             note=f"started pid {proc.pid}; poll ctxr_status(out) until running is false")
    args = argparse.Namespace(scene=0.05, min_gap=10, every=None, force=False, keep_video=False, whisper_all=whisper_all, proxy=proxy,
                              vocab=vocab, whisper_model=whisper_model)
    failed = []
    for i, (vid, src) in enumerate(ids, 1):
        await ctx.report_progress(i - 1, len(ids), f"{vid} ({i}/{len(ids)})")
        try:
            await anyio.to_thread.run_sync(cli.process, vid, o, args, src)
        except cli.BotCheck as e:  # every further download would fail too; stop and report
            failed += [f"{v}: {e}" for v, _ in ids[i - 1:]]
            break
        except Exception as e:  # keep going; the agent sees which ids failed
            log.warning("%s failed: %s", vid, e)
            failed.append(f"{vid}: {type(e).__name__}: {e}")
    await anyio.to_thread.run_sync(cli.write_index, o, [(f.split(':')[0], f) for f in failed])
    await ctx.report_progress(len(ids), len(ids), "done")
    return ProcessResult(out=str(o), requested=len(ids), done=len(ids) - len(failed), failed=failed, background=False,
                         note="read INDEX.md or call ctxr_index next")


@mcp.tool(annotations=READ_ONLY)
def ctxr_status(out: str | None = None) -> Status:
    """Progress of a background ctxr_process run in this output folder: is it still running, how many videos are
    done, which failed, and the last log lines."""
    o = _out(out)
    pid = o / "ctxr.pid"
    running = False
    if pid.exists():
        try:
            os.kill(int(pid.read_text()), 0); running = True
        except (OSError, ValueError):
            pass
    lines = (o / "ctxr.log").read_text(errors="replace").splitlines() if (o / "ctxr.log").exists() else []
    failed = [l.strip() for l in lines if l.lstrip().startswith("FAILED")]
    return Status(out=str(o), running=running, done=sum(1 for _ in _manifests(o)), failed=failed, last_lines=lines[-5:])


@mcp.tool(annotations=READ_ONLY)
def ctxr_index(out: str | None = None) -> list[Video]:
    """List every processed video in the output folder, oldest first."""
    o = _out(out)
    vids = [Video(id=m["id"], title=m.get("title") or m["id"], date=_date(m), duration_s=int(m.get("duration") or 0),
                  frames=len(m["frames"]), transcript_source=m["transcript_source"], folder=str(d),
                  url=m["url"]) for d, m in _manifests(o)]
    return sorted(vids, key=lambda v: (v.date, v.title))


@mcp.tool(annotations=READ_ONLY)
def ctxr_walkthrough(video: str, out: str | None = None, start: float = 0, end: float | None = None) -> list[Section]:
    """The walkthrough of one video (by id, folder name, or a unique title fragment): one section per distinct
    screen with its timestamp, frame filename, and the narration spoken while it was on screen. Use start/end
    seconds to read a window of a long video; call ctxr_frame to see a section's image."""
    d, m = _video(_out(out), video)
    return [_section(f) for f in m["frames"] if f["t"] >= start and (end is None or f["t"] < end)]


@mcp.tool(annotations=READ_ONLY)
def ctxr_frame(video: str, t: float, out: str | None = None) -> Image:
    """The frame on screen at second t of a video (the last captured frame at or before t), as an image."""
    d, m = _video(_out(out), video)
    frames = [f for f in m["frames"] if f["t"] <= t] or m["frames"][:1]
    return Image(path=d / "frames" / frames[-1]["file"])


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
def ctxr_find(query: str, limit: int = 10) -> list[Found]:
    """Find videos to process without downloading anything: a search phrase runs a YouTube search; a channel or
    playlist url lists its videos. Returns url, title, duration, channel and view count; pass the urls to
    ctxr_process."""
    return [Found(url=f["url"], title=f["title"], duration_s=f["duration"], channel=f["channel"], views=f["views"]) for f in cli.find_videos(query, limit)]


@mcp.tool(annotations=READ_ONLY)
def ctxr_search(query: str, out: str | None = None, limit: int = 20) -> list[Hit]:
    """Find where something is said across all processed videos. Full-text search with ranking (all terms first,
    then any term); each hit gives the video, timestamp, sentence, the frame on screen, a link to that second of
    the source, and a relevance score."""
    return [Hit(video=h["video"], title=h["title"], t=h["t"], timestamp=cli.fmt_ts(h["t"]), text=h["text"], frame=h["frame"],
                watch=cli.watch_url(h["url"], h["t"]) or h["url"], score=h["score"]) for h in cli.search(_out(out), query, limit)]


@mcp.prompt()
def learn_from_videos(product: str, out: str | None = None) -> str:
    """A study plan: learn a product end to end from a folder of ctxr-processed demo videos."""
    o = _out(out)
    return f"""I want you to learn {product} from its demo videos so you can explain any feature, answer questions about how it works, and describe how {product} demonstrates it.

The videos are processed with ctxr into {o}. Call ctxr_index to list them, then study each one in date order, oldest first.

For each video: call ctxr_walkthrough to read it section by section (each section is a distinct screen with a timestamp and the narration spoken while it was on screen), and ctxr_frame on sections that describe UI, so you see the real menus, labels and layouts. Treat the frames as ground truth for what the product looks like and the narration as the explanation of why; transcripts are automatic and can mishear product terms, so when text and screen disagree, trust the screen. A section with empty text is a quick screen change or a pause; still look at the frame.

Keep notes per video: what the feature is, the problem it solves, the exact steps shown with UI labels as they appear in the frames, the end result, and any limits mentioned. Cite the video title and timestamp for anything specific. Use ctxr_search to find where a term is discussed across videos.

When done, produce: (1) a feature map grouped by product area with links to the demos that cover each feature, (2) a glossary of the terms {product} uses in its own wording, (3) factual observations on how {product} runs a demo (length, structure, how they show before and after). Do not invent details that are not in the frames or transcripts; if something is unclear, say so and point to the timestamp."""


@mcp.prompt()
def skill_from_videos(topic: str, out: str | None = None) -> str:
    """Turn a folder of processed tutorial or demo videos into an installable agent skill (a SKILL.md)."""
    o = _out(out)
    return f"""Turn the videos processed with ctxr in {o} into one agent skill about {topic}, as a SKILL.md file another agent can install and follow.

Call ctxr_index to list the videos, then study each with ctxr_walkthrough (section by section) and ctxr_frame on the sections that show something on screen. Frames are ground truth for what is shown; narration explains why. Use ctxr_search to find where a term or step is covered across videos.

Write the skill in the Agent Skills format: YAML frontmatter with `name` (kebab-case) and `description` (one sentence saying what the skill does and when to use it), then Markdown with these sections: When to use; Prerequisites; Steps (numbered, each step concrete enough to act on, with the exact UI labels, commands or code shown, and a citation like "Video title, 01:40"); Pitfalls and limits the presenters mention or that the frames reveal; Verification (how the agent knows it worked); References (one line per source video with its url). Drop sponsor segments, filler and self-promotion. Keep only what the videos actually show or say; if something is unclear, say so with the timestamp rather than guessing. Plain language."""


def main():
    logging.basicConfig(level=os.environ.get("CTXR_LOG", "INFO"), stream=sys.stderr, format="%(name)s %(levelname)s %(message)s")
    mcp.run()  # stdio; streamable-http is one argument away if a hosted server is ever wanted


if __name__ == "__main__":
    main()
