from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import trafilatura

app = Flask(__name__)

def extract_article(url: str) -> str:
    # --- Step 1: Try trafilatura (fast + no browser) ---
    try:
        downloaded = trafilatura.fetch_url(url)
        extracted = trafilatura.extract(downloaded)
        if extracted and len(extracted.strip()) > 200:  # only accept if enough content
            return extracted
    except Exception:
        pass  # fallback to Playwright

    # --- Step 2: Playwright fallback ---
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page()
            page.set_extra_http_headers({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/117.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
                "DNT": "1",
            })
            page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Try to wait for main content
            for selector in ["article", "main", "div[itemprop='articleBody']", "div[class*='content']"]:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    break
                except Exception:
                    continue

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        # Remove noisy tags
        for tag in soup([
            "script", "style", "noscript", "header", "footer",
            "nav", "form", "button", "input", "aside"
        ]):
            tag.decompose()

        # Extract article-like section if possible
        article_tag = soup.find("article") or soup.find("main") or soup.find("div", itemprop="articleBody")
        if article_tag:
            text = article_tag.get_text("\n", strip=True)
        else:
            text = soup.get_text("\n", strip=True)

        # --- Step 3: Safety labelling ---
        title = soup.title.string if soup.title else ""
        if "access denied" in title.lower():
            return "[Blocked by Access Control]"
        if any(w in title.lower() for w in ["sign in", "subscribe", "login"]):
            return "[Paywall or Login Required]"
        if not text.strip():
            return "[No extractable content]"

        # Truncate if extreme length
        return text[:20000] + "... [truncated]" if len(text) > 20000 else text

    except Exception as e:
        return f"[ERROR] {str(e)}"


@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing ?url= parameter"}), 400

    article = extract_article(url)
    return jsonify({
        "URL": url,
        "article": article,
        "success": not article.startswith("[ERROR]")
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
