from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import requests
from bs4 import BeautifulSoup
import random, os

app = Flask(__name__)

def get_free_proxy():
    """Scrape HTTPS proxies from free-proxy-list.net"""
    try:
        r = requests.get("https://free-proxy-list.net/", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.find("table", id="proxylisttable").find_all("tr")
        proxies = []
        for row in rows[1:]:
            cols = row.find_all("td")
            if cols and cols[6].text.strip().lower() == "yes":  # only HTTPS proxies
                proxies.append(f"{cols[0].text}:{cols[1].text}")
        if proxies:
            proxy = random.choice(proxies)
            print(f"[Proxy Selected] {proxy}")
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

            # Try to extract readable text
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
