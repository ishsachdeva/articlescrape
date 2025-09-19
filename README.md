# Article Fetcher (Flask + cloudscraper)

A tiny Flask service that fetches an article URL, passes basic Cloudflare checks using `cloudscraper`, extracts the main text with BeautifulSoup, and returns JSON:

```json
{ "URL": "<input-url>", "article": "<clean text>", "success": true/false }
```

## Endpoints

- `GET /health` → `{ "ok": true }`
- `POST /fetch` (JSON body: `{ "url": "<https://…>" }`)

## Quick local run

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export PORT=8080                    # Windows (Powershell): $Env:PORT=8080
python app.py
```

Then:

```bash
curl -X POST http://localhost:8080/fetch \
  -H "Content-Type: application/json" \
  -d '{ "url": "https://example.com" }'
```

## Deploy to Render (Free Tier)

1. Push this folder to a **public GitHub repo**.
2. In Render: New → **Web Service**
3. Connect your repo, select branch `main`.
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `gunicorn app:app`
6. Instance Type: **Free**

Render will give you a URL like:

```
https://your-service.onrender.com
```

Test:

```bash
curl -X POST https://your-service.onrender.com/fetch \
  -H "Content-Type: application/json" \
  -d '{ "url": "https://example.com" }'
```

## Environment Variables

- `MAX_CHARS` (default `8000`) — max characters in `article` (to keep LLM tokens under control).

## Notes & Tips

- This service **attempts** to handle common Cloudflare pages via `cloudscraper`. Some sites may still require a full headless browser (Playwright/Puppeteer). If that happens, you can upgrade the service to use Playwright.
- Always respect site Terms of Service and robots.txt.
