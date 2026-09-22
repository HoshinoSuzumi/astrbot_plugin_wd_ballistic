#!/usr/bin/env python3
"""Download image URLs referenced by the WARDOGS ballistics JSON.

Writes ``assets/wardogs/`` and a deterministic manifest mapping each original
URL to its project-relative file.  Requests include the page origin/referer so
the CDN sees the same context as the calculator page.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "wardogs_ballistics_raw.json"
ASSET_DIR = ROOT / "assets" / "wardogs"
MANIFEST = ROOT / "data" / "wardogs_ballistics_assets.json"
HEADERS = {
    "Origin": "https://wardogs.tools",
    "Referer": "https://wardogs.tools/zh-hans/ballistics",
    "User-Agent": "Mozilla/5.0 (compatible; WARDOGS-data-export/1.0)",
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
}


def image_urls(value: object, output: set[str]) -> None:
    if isinstance(value, dict):
        for child in value.values():
            image_urls(child, output)
    elif isinstance(value, list):
        for child in value:
            image_urls(child, output)
    elif isinstance(value, str) and "/images/" in value and value.startswith("https://"):
        output.add(value)


def destination(url: str) -> Path:
    parsed = urlparse(url)
    stem = Path(parsed.path).name
    digest = hashlib.sha256(url.encode()).hexdigest()[:10]
    return ASSET_DIR / f"{Path(stem).stem}-{digest}{Path(stem).suffix or '.webp'}"


def main() -> None:
    urls: set[str] = set()
    image_urls(json.loads(DATA.read_text(encoding="utf-8")), urls)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, object]] = {}
    for url in sorted(urls):
        target = destination(url)
        try:
            if not target.exists():
                request = Request(url, headers=HEADERS)
                with urlopen(request, timeout=30) as response:
                    content_type = response.headers.get_content_type()
                    if not content_type.startswith("image/"):
                        raise ValueError(f"unexpected content type: {content_type}")
                    target.write_bytes(response.read())
            manifest[url] = {"path": target.relative_to(ROOT).as_posix(), "bytes": target.stat().st_size, "status": "downloaded"}
        except (HTTPError, URLError, ValueError) as exc:
            # Do not fabricate an asset for a URL that is already broken on
            # the upstream CDN.  Keep it visible in the manifest for a later
            # data refresh or a manually supplied replacement.
            target.unlink(missing_ok=True)
            manifest[url] = {"path": None, "bytes": 0, "status": "unavailable", "error": str(exc)}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    unavailable=sum(1 for item in manifest.values() if item["status"] != "downloaded")
    print(f"downloaded/verified {len(manifest)-unavailable} image assets; {unavailable} unavailable upstream")


if __name__ == "__main__":
    main()
