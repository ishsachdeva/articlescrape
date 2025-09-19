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

            # Remove unwanted elements
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form", "button", "input", "aside"]):
                tag.decompose()

            # Remove repeating noise
            blacklist_keywords = [
                "Popular Searches", "Popular News", "Sign In", "Free Sign Up",
                "Risk Disclosure", "Fusion Media", "Terms And Conditions",
                "Privacy Policy", "ProPicks", "Get 45% Off",
                "Install Our App", "Ad.", "remove ads"
            ]

            text_parts = []
            for line in soup.get_text(separator="\n", strip=True).splitlines():
                if not any(bad in line for bad in blacklist_keywords):
                    text_parts.append(line)

            cleaned = "\n".join(text_parts)

            if len(cleaned) > 20000:
                cleaned = cleaned[:20000] + "... [truncated]"

            return cleaned if cleaned else "[ERROR] Empty content"

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
