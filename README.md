# tobelabs.com

Static site for **to be labs** — home, research-notes index, and individual notes.
Tight & light: Markdown + Jinja2 → static HTML. No node, no framework.

## Layout

```
build.py              # the generator (markdown + jinja2 -> dist/)
requirements.txt      # markdown, jinja2, pyyaml
content/posts/*.md    # one file per note (YAML frontmatter + body)
templates/            # base / home / notes / note
static/style.css      # Warm-70s palette, Galt/Garland-inspired
docs/BRIEF.md         # project brief
dist/                 # build output (gitignored) — this is what deploys
```

Design mockups live in `reference/` (gitignored, local only).

## Build

Uses the OODA per-machine venv convention (`venv-<hostname>` → `~/.virtualenvs/`):

```bash
mkvenv                 # first time: create venv-$(hostname)
ve .                   # activate
pip install -r requirements.txt
python build.py                        # writes dist/
python -m http.server -d dist 8000     # preview at :8000
```

Output is three levels of clean URLs:

- `/`                       — home (three-blocks hero)
- `/notes/`                 — notes index, newest first
- `/notes/<slug>/`          — each note

## Add a note

Drop a markdown file in `content/posts/`. Frontmatter:

```yaml
---
title: "..."
date: "June 2026"          # display string
date_sort: "2026-06-01"    # sort key, newest first
summary: "one-line teaser for the index"
tags: [timing, small models]
author: "tobelabs research"   # optional, defaults to this
---
body markdown...
```

Conventions used by the design:
- The **first paragraph** renders as the large serif lead.
- `## Headings` get the orange caps + green square treatment.
- Wrap the closing claim in a `>` blockquote to get the green box.
- Tables, fenced code, inline `code`, **bold**, *italic* all styled.

Reading time is computed automatically unless you set `readtime:`.

## Deploy — Cloudflare Pages

The build is plain static files in `dist/`. Connect this GitHub repo to
Cloudflare Pages and set:

- **Build command:** `pip install -r requirements.txt && python build.py`
- **Build output directory:** `dist`
- **Python version:** pinned to 3.12 via `.python-version` (or set
  `PYTHON_VERSION=3.12` in the Pages env vars)

Or deploy a local build directly:

```bash
python build.py
npx wrangler pages deploy dist --project-name tobelabs
```
