import os
import time
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

app = Flask(__name__)

# Max characters to return for LLM token safety
MAX_CHARS = int(os.getenv("MAX_CHARS", "8000"))

# Common phrases that indicate Cloudflare/JS challenge page
CHALLENGE_PHRASES = [
    "Verifying you are human",
    "Just a moment",
    "Enable JavaScript and cookies to continue",
    "Checking your browser before accessing",
    "Checking if the site connection is secure"
]

# Browser-level defaults (feel free to tweak)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_VIEWPORT = {"width": 1366, "height": 768}
DEFAULT_LOCALE = "en-US"

def looks_like_challenge(html: str) -> bool:
    if not html:
        return False
    for p in CHALLENGE_PHRASES:
        if p.lower() in html.lower():
            return True
    return False

def extract_main_text_from_page(page) -> str:
    """Try common selectors first, then fallback to body text."""
    selectors = [
        "article",
        "main",
        "[role=main]",
        ".article-body",
        ".post-content",
        ".content",
        ".entry-content",
        "div[itemprop='articleBody']"
    ]
    for sel in selectors:
        try:
            if page.query_selector(sel):
                txt = page.inner_text(sel)
                if txt and len(txt.strip()) > 50:
                    return txt
        except Exception:
            # ignore selector errors and try next
            pass

    # fallback to body text
    try:
        body_text = page.inner_text("body")
        return body_text or ""
    except Exception:
        return ""

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get("url") or request.args.get("u") or request.args.get("URL")
    if not url:
        return jsonify({"URL": None, "article": "[ERROR] Missing URL", "success": False}), 400

    # Optional proxy (e.g. "http://username:pass@host:port")
    proxy_url = os.getenv("PROXY", "").strip() or None

    # Launch Playwright and try to fetch
    try:
        with sync_playwright() as p:
            launch_kwargs = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-dev-shm-usage"],
            }
            if proxy_url:
                launch_kwargs["proxy"] = {"server": proxy_url}

            browser = p.chromium.launch(**launch_kwargs)

            # create an incognito context with realistic settings
            context = browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                locale=DEFAULT_LOCALE,
                viewport=DEFAULT_VIEWPORT,
                java_script_enabled=True,
                bypass_csp=True,
            )

            # extra headers for HTTP requests
            context.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })

            page = context.new_page()

            # Try multiple attempts if first navigation gets a challenge or times out
            attempt_html = ""
            success = False
            last_error = None

            for attempt in range(1, 4):
                try:
                    # navigate and wait until network is mostly idle
                    page.goto(url, timeout=60000, wait_until="networkidle")
                    # small extra wait for any JS-based challenge to complete
                    time.sleep(2 + attempt)  # 3s, 4s, 5s on successive attempts

                    # If an <article> or main content appears quickly, good sign
                    try:
                        content = extract_main_text_from_page(page)
                    except Exception:
                        content = page.inner_text("body") if page.evaluate("() => !!document.body") else ""

                    attempt_html = page.content()
                    # detect if this is a challenge page
                    if looks_like_challenge(attempt_html):
                        # if challenge detected, try waiting longer and retry
                        last_error = "[INFO] Challenge detected, retrying"
                        # try waiting up to 10 more seconds for the challenge to resolve
                        try:
                            page.wait_for_load_state("networkidle", timeout=10000)
                        except PlaywrightTimeoutError:
                            pass
                        # after wait, re-check content
                        try:
                            content = extract_main_text_from_page(page)
                        except Exception:
                            content = page.inner_text("body") if page.evaluate("() => !!document.body") else ""
                        attempt_html = page.content()
                        if looks_like_challenge(attempt_html):
                            # still challenge — go to next attempt (maybe proxy needed)
                            last_error = "[INFO] Challenge still present after wait"
                            continue
                        else:
                            # challenge resolved
                            article_text = content or ""
                            success = True
                            break
                    else:
                        # not a challenge page — we have a usable page
                        article_text = content or ""
                        success = True
                        break

                except PlaywrightTimeoutError as te:
                    last_error = f"[ERROR] Timeout: {str(te)}"
                    # try again
                    continue
                except Exception as e:
                    last_error = f"[ERROR] Navigation/Extraction exception: {str(e)}"
                    continue

            # close browser context
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

            if not success:
                # Return the HTML snippet check info to aid debugging (short)
                info_sample = (attempt_html or "")[:2000]
                message = f"[ERROR] Could not bypass challenge. Last: {last_error}"
                return jsonify({"URL": url, "article": message + " | HTML_SNIPPET: " + info_sample, "success": False}), 200

            # Normalize and truncate output
            text = " ".join((article_text or "").split()).strip()
            if not text:
                return jsonify({"URL": url, "article": "[ERROR] No content extracted", "success": False}), 200

            if len(text) > MAX_CHARS:
                text = text[:MAX_CHARS] + " ... [truncated]"

            return jsonify({"URL": url, "article": text, "success": True}), 200

    except Exception as e:
        return jsonify({"URL": url, "article": f"[ERROR] Exception: {str(e)}", "success": False}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
