---
name: ctxr
description: Turn videos (YouTube, Vimeo, Loom, Wistia, X, TikTok, direct links, local files, a playlist, or a page of embeds) into agent-readable context with ctxr, then read it: per-video transcript, unique scene-change frames, and a walkthrough that puts each frame next to the narration. Use when asked to learn from, document, summarize, or extract product knowledge from videos, demos, tutorials or talks.
---

# ctxr

Requires `ffmpeg` on PATH and `uv`. Two ways to use it; prefer the MCP tools when the ctxr MCP server is connected, the CLI otherwise.

## With the MCP server connected

1. `ctxr_find` with a search phrase or a channel/playlist url lists candidate videos (nothing downloaded); pick the urls you want.
2. `ctxr_process` with `items` (video urls from any supported site, YouTube ids, or local file paths), `playlist`, or `page` (every video embedded on that page). Pass `background: true` for more than about 5 videos, then poll `ctxr_status` until `running` is false. Expect about one video per minute; ctxr paces itself to stay under YouTube's rate limits.
3. `ctxr_index` lists what is processed. `ctxr_search` is ranked full-text search over every transcript. `ctxr_walkthrough` reads one video section by section (use `start`/`end` seconds for a window of a long one). `ctxr_frame` shows the screen at a given second.
4. When videos have no captions and are transcribed locally, pass `vocab` with the product, brand and people names that must be spelled right (for example "Quivly, Claude, Salesforce"); the channel and title are added automatically.
5. The `learn_from_videos` prompt is a full study plan over a processed folder; `skill_from_videos` turns one into an installable SKILL.md.

## With the CLI

```
uvx --from "ctxr[whisper] @ git+https://github.com/mukulchugh/ctxr" ctxr --page <url> --out <dir>        # every video embedded on a page
uvx --from "ctxr[whisper] @ git+https://github.com/mukulchugh/ctxr" ctxr --playlist <url> --out <dir>
uvx --from "ctxr[whisper] @ git+https://github.com/mukulchugh/ctxr" ctxr <url-or-id-or-local-file> ... --out <dir>   # any yt-dlp site, direct link, or local file
```

`--find "query or channel url"` lists candidates without downloading. Try `--limit 3` first on a big page. `--vocab "Name, Name"` fixes misspelled brand names in local transcripts. `--proxy URL` routes yt-dlp and caption requests through a proxy if one IP is not enough. Finished folders are skipped on rerun, so an interrupted batch resumes. Then read `<dir>/README.md` (how to study the output) and `<dir>/INDEX.md` (the list). Each video folder has `README.md` (the walkthrough), `manifest.json` (frames with aligned transcript segments), `transcript.{json,srt,txt}` and `frames/`.

## Reading the output well

Frames are the ground truth for UI labels and layout; narration explains intent. Transcripts are automatic (YouTube captions or local Whisper) and can mishear product names, so when text and screen disagree, trust the screen. A section with no narration is a quick screen change or a pause; the frame usually shows the result of the previous action. Cite the video title and timestamp for anything specific.
