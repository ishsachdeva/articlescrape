from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

app = Flask(__name__)

def extract_article(url: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                    "--disable-software-rasterizer",
                ],
            )
            page = browser.new_page()

            # Pretend to be a real browser
            page.set_extra_http_headers({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/114.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            })

            page.goto(url, timeout=60000, wait_until="domcontentloaded")

            html = page.content()
            browser.close()

            soup = BeautifulSoup(html, "html.parser")
            article = soup.get_text(separator="\n", strip=True)

            return article if article else "[ERROR] Empty content"
    except Exception as e:
        return f"[ERROR] {str(e)}"

@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing ?url= parameter"}), 400

    article = extract_article(url)
    return jsonify({"URL": url, "article": article, "success": not article.startswith("[ERROR]")})

if __name__ == "__main__":
    # Local run
    app.run(host="0.0.0.0", port=8080, debug=True)
