# AI Rules for Mesopycnic

## Tech Stack Overview

- **Backend Language**: Python 3.8+ (zero external `pip` dependencies)
- **Web Server**: Python standard library `http.server` + `socketserver.ThreadingHTTPServer`
- **Database**: Python standard library `sqlite3` (no ORMs, no SQLAlchemy, no Alembic)
- **Frontend**: Vanilla HTML5, CSS3, and ES6 JavaScript (no frameworks, no build step)
- **API Protocol**: OpenAI-compatible Chat Completions over HTTP/SSE
- **Tool Integration**: Model Context Protocol (MCP) via stdio JSON-RPC 2.0 subprocesses
- **HTTP Client**: Python standard library `urllib.request` (no `requests`, no `httpx`, no `aiohttp`)
- **Process Management**: Python standard library `subprocess` (no `psutil`, no `supervisor`)
- **JSON Handling**: Python standard library `json` (no `pydantic`, no `marshmallow`)
- **Concurrency**: Python standard library `threading` (no `asyncio`, no `celery`, no `redis`)

## Library & Implementation Rules

### Backend Rules

1. **No External Python Packages**: Never add dependencies to `requirements.txt`, `setup.py`, `pyproject.toml`, or any `pip install` command. If a feature requires a third-party library, implement it using the Python standard library or ask the user for explicit permission.
2. **HTTP Server Only**: Use `http.server.BaseHTTPRequestHandler` or `socketserver.ThreadingHTTPServer`. Do not introduce Flask, FastAPI, Django, Tornado, or Bottle.
3. **SQLite3 Directly**: Execute raw SQL via `sqlite3` module. Do not use SQLAlchemy, Peewee, Django ORM, or any query builder.
4. **HTTP Requests via `urllib`**: Make all outbound API calls with `urllib.request`. Do not use `requests`, `httpx`, `urllib3`, or `aiohttp`.
5. **Subprocess for MCP**: Spawn MCP tool servers exclusively via `subprocess.Popen` with stdio pipes. Do not use WebSocket, gRPC, or HTTP transports for MCP.
6. **JSON Everywhere**: Use `json.dumps` / `json.loads`. Do not use `pydantic`, `dataclasses-json`, `msgspec`, or similar serialization libraries.
7. **Threading for Concurrency**: Use `threading.Thread` for background tasks. Do not use `asyncio`, `async`/`await`, or event loops.
8. **SSL via `ssl` module**: If you need custom TLS behavior, use `ssl.create_default_context()`. Do not add `certifi` or `pyopenssl`.

### Frontend Rules

1. **Vanilla JavaScript Only**: Write plain ES6 JavaScript. Do not add React, Vue, Angular, Svelte, jQuery, Lodash, or Alpine.js.
2. **No Build Step**: The frontend is served as static files (`static/index.html`, `static/style.css`, `static/app.js`). Do not introduce Webpack, Vite, Rollup, Parcel, Babel, or TypeScript.
3. **CSS from Scratch**: Write custom CSS using CSS variables (`:root`) and Flexbox/Grid. Do not add Tailwind CSS, Bootstrap, Bulma, Material UI, or any CSS framework.
4. **Allowed CDN Libraries**: The only permitted external frontend libraries are:
   - `highlight.js` for syntax highlighting
   - `marked.js` for Markdown rendering
   - Google Fonts (Inter, Fira Code)
   - Lucide icons (via inline SVG or CDN if needed, but prefer emojis for simplicity)
5. **DOM Manipulation**: Use `document.querySelector`, `document.createElement`, and standard DOM APIs. Do not use virtual DOM abstractions or templating engines.
6. **Event Handling**: Use `addEventListener` and vanilla event delegation. No event bus libraries.

### API & Data Rules

1. **OpenAI-Compatible Endpoints**: All chat completion proxying must conform to the OpenAI API shape (`/v1/chat/completions`, `messages`, `choices`, `delta`, `stream: true`).
2. **SSE for Streaming**: Server-Sent Events are the only allowed streaming transport. Use `text/event-stream` with `event:` prefixes and `data:` JSON payloads.
3. **SQLite Schema**: The database schema is fixed. `conversations` and `messages` tables use string UUIDs and ISO timestamps. Do not change column names or add ORM layers.
4. **MCP Tool Naming**: Prefix tool names with `server_name__tool_name` when exposing them to the LLM via OpenAI function calling.

### General Rules

1. **Keep It Lightweight**: The entire backend must start in under a second and consume less than 20MB RAM. If a change violates this, it is forbidden.
2. **Mobile / Termux Compatible**: All code must run on Android via Termux. Avoid OS-specific APIs, compiled C extensions, or features that require root.
3. **No Placeholders**: Every feature must be fully implemented with working code. No `TODO`, `FIXME`, `pass`, or `raise NotImplementedError`.
4. **Test Coverage**: Add or update `test_*.py` unit tests for any backend logic change. Use `unittest` from the standard library.
5. **Single File Per Concern**: Keep `server.py` (HTTP routing), `db.py` (persistence), `mcp_client.py` (tool processes), and `openai_service.py` (LLM proxy) cleanly separated. Do not bloat `server.py` with business logic that belongs elsewhere.