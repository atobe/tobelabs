#!/usr/bin/env python3
"""Tight static site generator for to be labs.

Markdown notes + Jinja2 templates -> static HTML in dist/.
No node, no framework. Deploys as-is to Cloudflare Pages.

    pip install -r requirements.txt
    python build.py            # writes dist/
    python -m http.server -d dist 8000   # preview
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
POSTS_DIR = ROOT / "content" / "posts"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"

SITE = {
    "name": "tobelabs",
    "tagline": "Independent research on minds, machines, and what it means to be.",
    "email": "hello@tobelabs.com",
    "eyebrow": "independent ai research — est. 2026",
}

# colour cycle for the numbered squares on the notes index
BLOCK_COLORS = ["orange", "green", "mustard"]

MD_EXTENSIONS = ["tables", "fenced_code", "attr_list", "smarty"]


def parse_frontmatter(text: str):
    """Split a leading `---` YAML block from the markdown body."""
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body.lstrip("\n")
    return {}, text


def reading_time(md_body: str) -> int:
    words = len(re.findall(r"\w+", md_body))
    return max(1, round(words / 200))


def load_posts() -> list[dict]:
    posts = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        meta["slug"] = meta.get("slug", path.stem)
        meta["html"] = markdown.markdown(body, extensions=MD_EXTENSIONS)
        meta["readtime"] = meta.get("readtime") or f"{reading_time(body)} min"
        meta.setdefault("author", "tobelabs research")
        meta.setdefault("tags", [])
        if "date_sort" not in meta:
            raise ValueError(f"{path.name} is missing `date_sort` in frontmatter")
        posts.append(meta)
    posts.sort(key=lambda p: str(p["date_sort"]), reverse=True)
    for i, p in enumerate(posts):
        p["index"] = f"{i + 1:02d}"
        p["color"] = BLOCK_COLORS[i % len(BLOCK_COLORS)]
    return posts


def render(env: Environment, template: str, out_rel: str, **ctx) -> None:
    html = env.get_template(template).render(site=SITE, **ctx)
    out = DIST / out_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    posts = load_posts()

    render(env, "home.html", "index.html", active="home", posts=posts)
    render(env, "notes.html", "notes/index.html", active="notes", posts=posts)
    for p in posts:
        render(env, "note.html", f"notes/{p['slug']}/index.html", active="notes", post=p)

    shutil.copytree(STATIC, DIST / "static")
    print(f"built {len(posts)} notes + home + index -> {DIST.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
