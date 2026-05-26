#!/usr/bin/env python3
"""Check whether the live Vercel bundle embeds VITE_API_KEY."""

from __future__ import annotations

import re
import sys
from urllib.request import urlopen

SITE = "https://automatic-karaoke.vercel.app"
KEY = "test-karaoke-phase7-key"


def main() -> int:
    html = urlopen(SITE, timeout=30).read().decode("utf-8", errors="replace")
    scripts = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    if not scripts:
        print("No /assets/*.js found in index.html")
        return 1
    print(f"site: {SITE}")
    found_key = False
    for path in scripts:
        js = urlopen(SITE + path, timeout=60).read().decode("utf-8", errors="replace")
        if KEY in js:
            found_key = True
            print(f"  {path}: contains API key string YES")
        else:
            print(f"  {path}: contains API key string NO")
    if found_key:
        print("\nVercel build likely has VITE_API_KEY baked in.")
    else:
        print(
            "\nVercel build does NOT contain the key — add VITE_API_KEY in Vercel env "
            "and redeploy (Production)."
        )
    return 0 if found_key else 1


if __name__ == "__main__":
    raise SystemExit(main())
