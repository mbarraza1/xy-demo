"""Screenshot the running Reflex page and report any console errors."""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

URL = "http://localhost:3000/"


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "results/page_full.png"
    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--enable-gpu", "--use-angle=metal", "--enable-unsafe-swiftshader"],
        )
        page = browser.new_context(viewport={"width": 1320, "height": 1000},
                                   device_scale_factor=1).new_page()
        page.on("console", lambda m: errors.append(f"{m.type}: {m.text}")
                if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(URL, wait_until="networkidle", timeout=180_000)
        page.wait_for_timeout(6000)

        canvases = page.evaluate("""
          () => [...document.querySelectorAll('canvas')]
                 .map(c => ({w: c.width, h: c.height,
                             vis: c.getBoundingClientRect().width > 0}))
        """)
        print(f"canvases: {len(canvases)}")
        for c in canvases:
            print("  ", c)

        page.screenshot(path=out, full_page=True)
        print(f"wrote {out}")
        if errors:
            print("\n--- console ---")
            for e in errors[:25]:
                print("  ", e[:220])
        browser.close()


if __name__ == "__main__":
    main()
