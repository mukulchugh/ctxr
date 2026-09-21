# The ctxr MCP server: design notes

How ctxr is exposed to agents over the Model Context Protocol, and why it is shaped this way. Written against MCP spec 2026-07-28 and the Python SDK v2 (`mcp` 2.2.0).

## What an agent needs from a video tool

Two different jobs: turning videos into context (slow, minutes to an hour, network-bound) and reading that context (fast, local, repeated many times). A good MCP surface keeps them separate so the agent can start a long run, keep working, and then query results in small pieces instead of swallowing a 400 KB Markdown file.

## The surface

| Primitive | Name | Why |
|---|---|---|
| tool | `ctxr_process` | Ingest urls from any yt-dlp site, YouTube ids, local files, a playlist, or every video on a page. Inline for a few videos with per-video progress notifications; `background: true` returns immediately for big batches; `proxy` routes requests through an HTTP/SOCKS proxy. |
| tool | `ctxr_status` | Poll a background run: running flag (pid alive), videos done, failures, last log lines. Works in every MCP client today. |
| tool | `ctxr_index` | What is processed, as structured rows (id, title, date, duration, frames, transcript source, folder). |
| tool | `ctxr_search` | Where is X said, across all videos. Returns sentence, timestamp, the frame on screen, and a YouTube link at that second. |
| tool | `ctxr_walkthrough` | One video, section by section, with `start`/`end` so a 12-minute video can be read in windows. |
| tool | `ctxr_frame` | The screen at second t, returned as image content so the model can look at the UI. |
| prompt | `learn_from_videos` | The study plan, parameterized by product and folder. |

Every read tool is annotated `read_only_hint` and `idempotent_hint`, so hosts can auto-approve them; `ctxr_process` is marked `open_world_hint` because it downloads from YouTube. Results are typed Pydantic models, so clients get an output schema and `structuredContent`, not prose to parse.

## Decisions

- **Tools, not resources, for the content.** Resource templates with filesystem paths trip the SDK's path-traversal protections and most hosts do not let the model browse resources on its own. Tools with an `out` argument are explicit and work everywhere. A resource view can be added later without changing the tools.
- **Background + status polling instead of the Tasks extension.** MCP Tasks (`io.modelcontextprotocol/tasks`) is the official answer for long-running calls: a durable task id, `tasks/get` polling, cancellation. It is an extension that both client and server must opt into, and client support is still uneven. A background process plus a `ctxr_status` tool gives the same call-now, fetch-later behaviour on every client today. When Tasks support is common, `ctxr_process` can return a task handle instead; the status tool stays useful for humans.
- **Progress notifications for inline runs.** `ctx.report_progress(i, n, message)` after each video keeps the host from timing out and shows the agent what is happening.
- **stdio by default.** Hosts launch `ctxr-mcp` as a subprocess; nothing to deploy. The SDK's `run(transport="streamable-http")` is one argument away if a shared server is ever wanted. Nothing is printed to stdout because stdout is the wire; logs go to stderr.
- **One output folder per corpus.** `out` per call, else `$CTXR_OUT`, else `~/ctxr`. The folder is the state; there is no database. Rerunning is safe because finished videos are skipped.
- **Substring search.** A scan over a few hundred transcripts is instant. Ranking (BM25 or embeddings) can be added when a corpus is large enough to need it.

## Multi-harness

The same server runs in every MCP client. The command is identical; only the config file differs.

Claude Code (`.mcp.json` in a project, or the plugin's `.mcp.json`):
```json
{ "mcpServers": { "ctxr": { "type": "stdio", "command": "uvx", "args": ["--from", "ctxr[mcp,whisper] @ git+https://github.com/mukulchugh/ctxr", "ctxr-mcp"] } } }
```

Codex (`~/.codex/config.toml`):
```toml
[mcp_servers.ctxr]
command = "uvx"
args = ["--from", "ctxr[mcp,whisper] @ git+https://github.com/mukulchugh/ctxr", "ctxr-mcp"]
```

Cursor (`~/.cursor/mcp.json`):
```json
{ "mcpServers": { "ctxr": { "type": "stdio", "command": "uvx", "args": ["--from", "ctxr[mcp,whisper] @ git+https://github.com/mukulchugh/ctxr", "ctxr-mcp"] } } }
```

The skill (`skills/ctxr/SKILL.md`) follows the open Agent Skills format, so it installs into Claude Code, Codex, Cursor and others with `npx skills add mukulchugh/ctxr`, and into Claude Code through the plugin marketplace in this repo.

## Sources

- MCP specification, latest revision: https://modelcontextprotocol.io/specification/latest
- MCP Tasks extension: https://modelcontextprotocol.io/extensions/tasks/overview
- Python SDK v2 docs: https://py.sdk.modelcontextprotocol.io/ (tools, context and progress, images, running)
- Python SDK repository: https://github.com/modelcontextprotocol/python-sdk
- Agent Skills specification: https://agentskills.io/specification
- skills CLI: https://github.com/vercel-labs/skills
