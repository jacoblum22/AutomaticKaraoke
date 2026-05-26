#!/usr/bin/env python3
"""Inspect what automatic-karaoke.vercel.app is actually serving."""

from __future__ import annotations

import re
import sys
from urllib.request import Request, urlopen

SITE = "https://automatic-karaoke.vercel.app"
KEY = "test-karaoke-phase7-key"


def main() -> int:
    req = Request(SITE, headers={"Cache-Control": "no-cache"})
    with urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
        headers = dict(resp.headers)

    print(f"url: {SITE}")
    for h in (
        "age",
        "cache-control",
        "x-vercel-cache",
        "x-vercel-id",
        "server",
        "last-modified",
    ):
        if h in headers:
            print(f"  {h}: {headers[h]}")

    scripts = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    print(f"js bundles: {scripts}")
    if not scripts:
        print("ERROR: no /assets/*.js in index.html")
        return 1

    for path in scripts:
        with urlopen(SITE + path, timeout=60) as r:
            js = r.read().decode("utf-8", errors="replace")
        has_key = KEY in js
        has_footer = "Client API key" in js
        print(f"  {path}")
        print(f"    size={len(js)} has_api_key={has_key} has_new_footer={has_footer}")

    if KEY in html:
        print("  (key found in index.html itself)")

    if KEY not in js and path == scripts[0]:
        print(
            "\nDiagnosis: bundle does not include VITE_API_KEY. "
            "Redeploy Production after setting VITE_API_KEY, or push to main."
        )
        return 1

    if scripts == ["/assets/index-DR7xYdnr.js"]:
        print(
            "\nNote: index-DR7xYdnr.js is an older build (often without the API key). "
            "A rebuild with VITE_API_KEY uses a new hash (e.g. index-BeVnPnVB.js)."
        )

    print("\nOK: live bundle includes API key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
