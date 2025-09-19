from flask import Flask, request, jsonify
import os
import cloudscraper
from bs4 import BeautifulSoup

app = Flask(__name__)

# Environment-configurable max length for returned text
MAX_CHARS = int(os.getenv("MAX_CHARS", "8000"))

# Create a single scraper instance (Cloudflare-aware)
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

def extract_main_text(html: str) -> str:
    """Extract the most relevant article text with graceful fallbacks."""
    soup = BeautifulSoup(html, "html.parser")

    # 1) Try <article>
    article = soup.find("article")
    if article and article.get_text(strip=True):
        return article.get_text(" ", strip=True)

    # 2) Try common main-content containers
    for selector in ["main", "[role=main]", ".article-body", ".post-content", ".content", ".entry-content"]:
        found = soup.select_one(selector)
        if found and found.get_text(strip=True):
            return found.get_text(" ", strip=True)

    # 3) Fallback to whole body text
    body = soup.body
    return body.get_text(" ", strip=True) if body else soup.get_text(" ", strip=True)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route("/fetch", methods=["POST"])
def fetch():
    data = request.get_json(silent=True) or {}
    url = data.get("url") or data.get("URL")
    if not url:
        return jsonify({"URL": None, "article": "[ERROR] Missing URL", "success": False}), 400

    try:
        resp = scraper.get(url, timeout=25)
        status = resp.status_code

        # If blocked or failure, return error but keep URL
        if status != 200:
            return jsonify({"URL": url, "article": f"[ERROR] HTTP {status}", "success": False}), 200

        html = resp.text
        # Quick check for Cloudflare challenge content
        if "cf-chl" in html or "Just a moment" in html or "Enable JavaScript and cookies to continue" in html:
            return jsonify({"URL": url, "article": "[ERROR] Cloudflare challenge detected", "success": False}), 200

        text = extract_main_text(html)
        # Normalize whitespace
        text = " ".join(text.split())

        if not text:
            return jsonify({"URL": url, "article": "[ERROR] No content extracted", "success": False}), 200

        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + " ... [truncated]"

        return jsonify({"URL": url, "article": text, "success": True}), 200

    except Exception as e:
        return jsonify({"URL": url, "article": f"[ERROR] Exception: {str(e)}", "success": False}), 200

if __name__ == "__main__":
    # Local run: python app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
