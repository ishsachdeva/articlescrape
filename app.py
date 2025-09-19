#!/usr/bin/env python3
"""
Final app.py — Playwright scraper with stealth + headers + fallbacks.

- Uses playwright (sync) to launch Chromium and render the page.
- Applies playwright-stealth if available (safe import).
- Uses realistic headers, viewport, and waits for networkidle + small timeout.
- Prefers <article> (or common article selectors) and falls back to body text.
- Defensive: doesn't crash if stealth package is missing; returns structured JSON.
- Respects PORT environment variable (for Railway / other hosts).
- Truncates output to MAX_CHARS (env var, default 8000).
"""

import os
import time
import traceback
from flask import Flask, request, jsonify

# Playwright sync API
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# stealth import may expose different names depending on version; handle safely
try:
    # newer versions expose stealth() that works with sync pages
    from playwright_stealth import stealth  # type: ignore
    STEALTH_AVAILABLE = True
except Exception:
    stealth = None  # type: ignore
    STEALTH_AVAILABLE = False

app = Flask(__name__)

MAX_CHARS = int(os.getenv("MAX_CHARS", "8000"))
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_VIEWPORT = {"width": 1366, "height": 768}
CHALLENGE_PHRASES = [
    "Verifying you are human",
    "Just a moment",
    "Enable JavaScript and cookies to continue",
    "Checking your browser before accessing",
    "Checking if the site connection is secure",
    "Access Denied",
    "Please check back soon"
]


def looks_like_challenge(html: str) -> bool:
    if not html:
        return False
    low = html.lower()
    for p in CHALLENGE_PHRASES:
        if p.lower() in low:
            return True
    return False


def extract_main_text(page) -> str:
    """Try common article selectors first, fallback to body text."""
    selectors = [
        "article",
        "main",
        "[role=main]",
        "div[itemprop='articleBody']",
        ".article-body",
        ".post-content",
        ".entry-content",
        ".content",
    ]
    for sel in selectors:
        try:
            if page.query_selector(sel):
                txt = page.inner_text(sel).strip()
                if len(txt) > 50:
                    return txt
        except Exception:
            # ignore and try next
            pass
    # fallback
    try:
        body = page.inner_text("body")
        return body or ""
    except Exception:
        return ""


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "stealth_available": STEALTH_AVAILABLE})


@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get("url") or request.args.get("u") or request.args.get("URL")
    if not url:
        return jsonify({"URL": None, "article": "[ERROR] Missing URL", "success": False}), 400

    # Optional parameters
    max_wait = int(os.getenv("MAX_WAIT_MS", "60000"))  # navigation timeout in ms
    extra_wait_ms = int(os.getenv("EXTRA_WAIT_MS", "3000"))  # wait after networkidle

    # Keep a short debug log for server logs
    print(f"[INFO] Starting extraction for URL: {url}")
    if STEALTH_AVAILABLE:
        print("[INFO] playwright-stealth is available")
    else:
        print("[INFO] playwright-stealth NOT available — proceeding without it")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            # create a context with human-like values
            context = browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport=DEFAULT_VIEWPORT,
                locale="en-US",
                java_script_enabled=True,
                bypass_csp=True,
            )

            # extra HTTP headers to appear human-like
            context.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Cache-Control": "no-cache",
            })

            page = context.new_page()

            # If stealth is available, apply it (best-effort)
            try:
                if STEALTH_AVAILABLE and stealth is not None:
                    # stealth may be sync-compatible; call it with the page
                    # Some versions expect async stealth; most expose a sync stealth for sync pages.
                    stealth(page)
                    print("[INFO] Applied stealth() to page")
            except Exception as se:
                # don't fail if stealth call errors — log and continue
                print("[WARN] stealth() raised an exception; continuing without it")
                print(traceback.format_exc())

            # Try navigation with retries (helps transient blocks)
            last_html_snippet = ""
            article_text = ""
            success = False
            last_error = None

            for attempt in range(1, 4):
                try:
                    print(f"[INFO] Navigation attempt {attempt} -> {url}")
                    page.goto(url, timeout=max_wait, wait_until="networkidle")
                    # small extra wait to let JS render dynamic content
                    time.sleep(extra_wait_ms / 1000.0)

                    # capture a short html snippet for debugging when blocked
                    try:
                        last_html_snippet = page.content()[:3000]
                    except Exception:
                        last_html_snippet = ""

                    # detect challenge pages quickly
                    if looks_like_challenge(last_html_snippet):
                        last_error = "[INFO] Detected challenge/interstitial page"
                        print(last_error)
                        # try a longer wait then re-check
                        try:
                            page.wait_for_load_state("networkidle", timeout=10000)
                        except PlaywrightTimeoutError:
                            pass
                        time.sleep(1.5)
                        try:
                            last_html_snippet = page.content()[:3000]
                            if looks_like_challenge(last_html_snippet):
                                # still challenge -> retry outer loop
                                print("[INFO] Challenge still present after wait, retrying")
                                continue
                        except Exception:
                            pass

                    # attempt to extract main readable text
                    try:
                        article_text = extract_main_text(page)
                    except Exception as e:
                        print("[WARN] extract_main_text error", e)
                        article_text = ""

                    if article_text and len(article_text.strip()) > 50:
                        success = True
                        break
                    else:
                        last_error = "[INFO] Extracted text too short, retrying"
                        print(last_error)
                        # try again (maybe dynamic content loads slightly later)
                        continue

                except PlaywrightTimeoutError as te:
                    last_error = f"[ERROR] Timeout during navigation: {te}"
                    print(last_error)
                    continue
                except Exception as e:
                    last_error = f"[ERROR] Navigation/Extraction exception: {e}"
                    print(last_error)
                    print(traceback.format_exc())
                    continue

            # close context & browser
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

            if not success:
                # return helpful debug info so you can see the interstitial HTML snippet
                msg = f"[ERROR] Could not extract content. LastError: {last_error}"
                snippet = last_html_snippet.replace("\n", " ")[:1500]
                return jsonify({
                    "URL": url,
                    "article": f"{msg} | HTML_SNIPPET: {snippet}",
                    "success": False
                }), 200

            # normalize whitespace and truncate
            text = " ".join(article_text.split()).strip()
            if not text:
                return jsonify({"URL": url, "article": "[ERROR] No content extracted", "success": False}), 200

            if len(text) > MAX_CHARS:
                text = text[:MAX_CHARS] + " ... [truncated]"

            return jsonify({"URL": url, "article": text, "success": True}), 200

    except Exception as outer_e:
        # catch-all: return a clear error payload (avoid crashing the container)
        print("[ERROR] Outer exception:", outer_e)
        print(traceback.format_exc())
        return jsonify({"URL": url, "article": f"[ERROR] Exception: {str(outer_e)}", "success": False}), 500


if __name__ == "__main__":
    # Port for Railway or other PaaS (they set PORT)
    port = int(os.environ.get("PORT", 8080))
    # Run Flask (gunicorn is preferred in Dockerfile; this is a safe fallback)
    app.run(host="0.0.0.0", port=port)
