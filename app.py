from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os, sys, traceback

app = Flask(__name__)

@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    try:
        print("[INFO] Starting Playwright...", file=sys.stderr, flush=True)
        with sync_playwright() as p:
            print("[INFO] Launching Chromium...", file=sys.stderr, flush=True)
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                    "--no-zygote",
                    "--disable-software-rasterizer",
                ],
            )
            print("[INFO] Chromium launched!", file=sys.stderr, flush=True)

            page = browser.new_page()
            print(f"[INFO] Navigating to {url}", file=sys.stderr, flush=True)
            page.goto(url, timeout=90000, wait_until="domcontentloaded")

            print("[INFO] Extracting text...", file=sys.stderr, flush=True)
            text = page.inner_text("body")
            browser.close()

        return jsonify({
            "URL": url,
            "article": text[:8000] + ("... [truncated]" if len(text) > 8000 else ""),
            "success": True
        })
    except Exception as e:
        err = traceback.format_exc()
        print(f"[ERROR] {err}", file=sys.stderr, flush=True)
        return jsonify({
            "URL": url,
            "article": f"[ERROR] Navigation/Extraction exception: {str(e)}",
            "success": False
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
