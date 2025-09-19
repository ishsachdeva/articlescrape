from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from freeproxy import FreeProxy

import os, random

app = Flask(__name__)

def get_free_proxy():
    try:
        proxy = FreeProxy(country_id=['US','IN'], timeout=1, rand=True).get()
        print(f"Using proxy: {proxy}")
        return proxy
    except Exception as e:
        print(f"[Proxy Error] {e}")
        return None

@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    proxy = get_free_proxy()
    try:
        with sync_playwright() as p:
            launch_args = {"headless": True}
            if proxy:
                launch_args["proxy"] = {"server": f"http://{proxy}"}

            browser = p.chromium.launch(**launch_args)
            page = browser.new_page()
            page.goto(url, timeout=60000)
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
