#!/usr/bin/env python3
"""Publish docs/jevlab/BLOG-SEQUEL.md to the DSC blog (markdown -> the blog's HTML).

Run:  set -a && . ~/.ssh/dsc-blog-idalia.pass && set +a
      python3 tools/jevlab/publish_julia_sequel.py HEADER.webp [--dry-run]
"""

from __future__ import annotations

import html
import io
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, "/root/projects/decisionsciencecorp.com/tools")
from dsc_blog_api import BlogApiError, BlogClient  # noqa: E402

SLUG = "julia-1-mood-tagger-with-a-marketing-department"
TITLE = "Julia-1 is a mood tagger with a marketing department"
EXCERPT = (
    "Julia-1 was sold as the tiny model that beats the giants. On the shared scoreboard it lost badly. "
    "On its own model card's benchmarks, run at full size, it won exactly one — and the card's biggest "
    "number can't be reproduced."
)
MD = ROOT / "docs" / "jevlab" / "BLOG-SEQUEL.md"
CHARTS = ROOT / "docs" / "jevlab" / "illustrations" / "julia"
CAPTIONS = {
    "julia-card-vs-full-set.png": "What the model card says vs. what the full test set says.",
    "julia-round-one.png": "Round one. Dashed lines are what random guessing scores.",
    "julia-round-two.png": "Round two, on Julia’s own benchmarks. Dashed outlines are the card’s numbers.",
    "julia-emotion-gap.png": "The real win, at its real size.",
    "julia-card-check-flow.png": "Where the recipe was public, the number held up.",
    "julia-emotion-by-mood.png": "Emotion, one mood at a time.",
    "julia-which-model-flow.png": "Which decision model for which job.",
}


def inline(text: str) -> str:
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def to_html(md: str, image_urls: dict[str, str]) -> str:
    out: list[str] = []
    blocks = re.split(r"\n\s*\n", md.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        first = lines[0]
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)$", first.strip())
        if m and len(lines) == 1:
            name = Path(m.group(2)).name
            out.append(
                '<figure class="blog-figure">\n'
                f'<img src="{image_urls[name]}" alt="{html.escape(m.group(1))}" loading="lazy" decoding="async">\n'
                f"<figcaption>{html.escape(CAPTIONS[name], quote=False)}</figcaption>\n</figure>"
            )
        elif first.startswith("## "):
            out.append(f"<h2>{inline(first[3:])}</h2>")
            if len(lines) > 1:
                out.append(f"<p>{inline(' '.join(lines[1:]))}</p>")
        elif first.startswith("|"):
            head = cells(lines[0])
            rows = [cells(l) for l in lines[2:] if l.startswith("|")]
            t = ["<table>", "<thead>", "<tr>" + "".join(f"<th>{inline(h)}</th>" for h in head) + "</tr>", "</thead>",
                 "<tbody>"]
            t += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows]
            t += ["</tbody>", "</table>"]
            out.append("\n".join(t))
            rest = [l for l in lines[len(rows) + 2:]]
            if rest:
                out.append(f"<p>{inline(' '.join(rest))}</p>")
        elif first.startswith("- "):
            out.append("<ul>\n" + "\n".join(f"<li>{inline(l[2:])}</li>" for l in lines) + "\n</ul>")
        else:
            out.append(f"<p>{inline(' '.join(l.strip() for l in lines))}</p>")
    out.append('<p>Want a decision model picked, tested, or built for your shop — '
               '<a href="#blog-contact">hit us here</a>.</p>')
    return "\n\n".join(out) + "\n"


def webp_bytes(path: Path) -> bytes:
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, "WEBP", quality=90, method=6)
    return buf.getvalue()


def main() -> int:
    header = Path(sys.argv[1])
    dry = "--dry-run" in sys.argv
    md = MD.read_text()
    names = re.findall(r"illustrations/julia/([\w-]+\.png)", md)
    urls = {n: f"/uploads/blog/inline/{SLUG}-{Path(n).stem.removeprefix('julia-')}.webp" for n in names}
    body = to_html(md, urls)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / f"{SLUG}.html").write_text(body)
    if dry:
        print(body)
        return 0
    c = BlogClient()
    for n in names:
        key = f"{SLUG}-{Path(n).stem.removeprefix('julia-')}"
        c.upload_image_bytes(key, webp_bytes(CHARTS / n), role="inline")
        print("inline", key)
    payload = {"slug": SLUG, "title": TITLE, "excerpt": EXCERPT, "content": body, "author": "Mark Hopkins"}
    try:
        c.get_post(SLUG)
        c.update_post(SLUG, title=TITLE, excerpt=EXCERPT, content=body)
        print("updated post")
    except BlogApiError:
        c.create_post(payload)
        print("created post")
    c.upload_image_bytes(SLUG, header.read_bytes(), role="featured")
    c.update_post(SLUG, featured_image=f"uploads/blog/{SLUG}.webp")
    print("featured set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
