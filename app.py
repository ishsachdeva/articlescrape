from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

@app.route("/scrape", methods=["GET"])
def scrape():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")

            text = page.inner_text("body")[:5000]  # limit to 5000 chars
            browser.close()

        return jsonify({"URL": url, "article": text, "success": True})
    except Exception as e:
        return jsonify({"URL": url, "article": f"[ERROR] {str(e)}", "success": False})

@app.route("/")
def home():
    return "Playwright scraper is running!"
