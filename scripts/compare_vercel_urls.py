#!/usr/bin/env python3
"""Compare JS bundles across Vercel URLs."""

from __future__ import annotations

import re
import sys
from urllib.request import urlopen

KEY = "test-karaoke-phase7-key"

URLS = [
    "https://automatic-karaoke.vercel.app",
    "https://automatic-karaoke-jacoblum22.vercel.app",
    "https://automatic-karaoke-git-main-jacoblum22.vercel.app",
]


def inspect(site: str) -> None:
    try:
        html = urlopen(site, timeout=20).read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"{site}\n  ERROR: {exc}\n")
        return
    scripts = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    if not scripts:
        print(f"{site}\n  no /assets/*.js\n")
        return
    path = scripts[0]
    js = urlopen(site + path, timeout=60).read().decode("utf-8", errors="replace")
    print(f"{site}")
    print(f"  bundle: {path}")
    print(f"  has_key: {KEY in js}")
    print(f"  has_footer: {'Client API key' in js}\n")


def main() -> int:
    for url in URLS:
        inspect(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
