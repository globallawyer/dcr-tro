#!/usr/bin/env python3
"""Build crawler and AI discovery files for trolawyer.site."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

DOMAIN = "https://trolawyer.site"


def public_html_files(root: Path) -> list[Path]:
    pages = [path for path in root.glob("*.html") if not path.name.startswith("_")]
    pages.extend(path for path in (root / "news").glob("*.html") if not path.name.startswith("_"))
    return sorted(pages, key=lambda path: (path.parent.name == "news", path.as_posix()))


def page_url(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    return f"{DOMAIN}/" if relative == "index.html" else f"{DOMAIN}/{relative}"


def build_discovery_files(root: Path) -> None:
    pages = public_html_files(root)
    now = datetime.now(timezone.utc).date().isoformat()
    sitemap_entries = []
    urls = []
    for path in pages:
        url = page_url(root, path)
        urls.append(url)
        lastmod = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()
        priority = "1.0" if path.name == "index.html" and path.parent == root else "0.8"
        frequency = "daily" if path.parent.name == "news" or path.name == "index.html" else "monthly"
        sitemap_entries.append(
            "  <url>\n"
            f"    <loc>{escape(url)}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{frequency}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )

    (root / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(sitemap_entries)
        + "\n</urlset>\n",
        encoding="utf-8",
    )
    (root / "sitemap.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
    (root / "baidu_urls.txt").write_text("\n".join(urls[:50]) + "\n", encoding="utf-8")
    print(f"[discovery] generated {len(urls)} URLs on {now}")


if __name__ == "__main__":
    build_discovery_files(Path(__file__).resolve().parent.parent)

