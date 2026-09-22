#!/usr/bin/env python3
"""Export the complete ballistics payload embedded in wardogs.tools.

This preserves every field published to the calculator—not only fields shown
in the table.  It intentionally uses only the Python standard library.

Examples:
    python3 tools/export_wardogs_ballistics.py > wardogs_ballistics_raw.json
    python3 tools/export_wardogs_ballistics.py -o wardogs_ballistics_raw.json
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

URL = "https://wardogs.tools/zh-hans/ballistics"
PUSH_PREFIX = "self.__next_f.push([1,"


def _balanced_object(text: str, start: int) -> str:
    """Return the JSON object at *start*, respecting JSON string escapes."""
    if text[start] != "{":
        raise ValueError("payload does not start with a JSON object")
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError("unterminated payload object")


def extract_payload(page: str) -> dict:
    """Decode the React Server Component payload shipped in the HTML page."""
    decoder = json.JSONDecoder()
    for match in re.finditer(re.escape(PUSH_PREFIX), page):
        # The bracket begins an ordinary JSON array: [1, "decoded RSC text"].
        try:
            event, _ = decoder.raw_decode(page[match.start() + len("self.__next_f.push(") :])
        except json.JSONDecodeError:
            continue
        if not isinstance(event, list) or len(event) != 2 or not isinstance(event[1], str):
            continue
        rsc = event[1]
        marker = '"payload":'
        payload_at = rsc.find(marker)
        if payload_at < 0:
            continue
        object_at = rsc.find("{", payload_at + len(marker))
        if object_at >= 0:
            return json.loads(_balanced_object(rsc, object_at))
    raise ValueError("could not find the calculator payload in the page")


def download_payload() -> dict:
    request = Request(URL, headers={"User-Agent": "WARDOGS-ballistics-export/1.0"})
    with urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8")
    return extract_payload(html.unescape(page))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, help="write JSON to this path")
    args = parser.parse_args()
    result = json.dumps(download_payload(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
