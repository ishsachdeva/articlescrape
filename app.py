from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os

# ✅ Import stealth function correctly
from playwright_stealth import stealth

app = Flask(__name__)

@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/117.0 Safari/537.36"
            )

            # ✅ Apply stealth correctly
            stealth(page)

            page.goto(url, timeout=60000, wait_until="networkidle")
            text = page.inner_text("body")
            browser.close()

        return jsonify({
            "URL": url,
            "article": text[:8000] + ("... [truncated]" if len(text) > 8000 else ""),
            "success": True
        })
    except Exception as e:
        return jsonify({
            "URL": url,
            "article": f"[ERROR] {str(e)}",
            "success": False
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
