#!/usr/bin/env python3
"""Generate docs/index.html from public repos with GitHub Pages enabled.

Usage:
    GITHUB_TOKEN=xxx python3 .github/scripts/generate_index.py
    (token is optional; unauthenticated API is limited to ~60 req/hr)
"""
import json
import os
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "https://api.github.com"
OWNER = "watanabe3tipapa"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

with open(os.path.join(REPO_ROOT, ".github", "index-config.json")) as f:
    CONFIG = json.load(f)
OWNER = CONFIG.get("owner", OWNER)
HOME_OVERRIDES = CONFIG.get("homeOverrides", {})

with open(os.path.join(REPO_ROOT, ".github", "index-exclude.txt")) as f:
    EXCLUDE = {
        line.strip()
        for line in f
        if line.strip() and not line.strip().startswith("#")
    }


def api(path):
    url = BASE_URL + path
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "index-generator",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def fetch_all_repos():
    page = 1
    repos = []
    while True:
        batch = api(f"/users/{OWNER}/repos?per_page=100&page={page}&sort=updated")
        if not batch:
            break
        repos.extend(batch)
        page += 1
        if len(batch) < 100:
            break
    return repos


def pages_url(repo):
    if repo["name"] in HOME_OVERRIDES:
        return HOME_OVERRIDES[repo["name"]]
    if repo["name"] == f"{OWNER}.github.io":
        return CONFIG.get("baseUrl", f"https://{OWNER}.github.io")
    return f"{CONFIG.get('baseUrl', 'https://' + OWNER + '.github.io')}/{repo['name']}/"


def main():
    repos = fetch_all_repos()
    items = []
    for repo in repos:
        if not repo.get("has_pages"):
            continue
        if repo["name"] in EXCLUDE:
            continue
        items.append({
            "name": repo["name"],
            "description": repo.get("description") or "",
            "repo_url": repo["html_url"],
            "pages_url": pages_url(repo),
            "updated": repo.get("updated_at", "")[:10],
            "homepage": repo.get("homepage") or "",
        })

    items.sort(key=lambda r: r["updated"], reverse=True)

    cards = "\n".join(render_card(r) for r in items)
    html = HTML_TEMPLATE.replace("{{CARDS}}", cards).replace(
        "{{COUNT}}", str(len(items))
    ).replace("{{GENERATED_AT}}", __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    out = os.path.join(REPO_ROOT, "docs", "index.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"Generated {len(items)} repos -> {out}")


def render_card(r):
    desc = r["description"] or "（説明なし）"
    return f'''
      <a class="card" href="{r["pages_url"]}" rel="noopener">
        <h3>{r["name"]}</h3>
        <p class="desc">{desc}</p>
        <p class="meta">
          <span class="updated">更新: {r["updated"]}</span>
          <span class="repo">github.com/{OWNER}/{r["name"]}</span>
        </p>
      </a>'''


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>watanabe3tipapa の公開サイト・サービス一覧</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Kaku Gothic ProN", sans-serif;
         line-height: 1.6; color: #1f2328; background: #f6f8fa; padding: 2rem 1rem; }
  .wrap { max-width: 920px; margin: 0 auto; }
  header { margin-bottom: 2rem; }
  header h1 { font-size: 1.5rem; border-bottom: 2px solid #0969da; padding-bottom: .5rem; }
  header p { color: #57606a; margin-top: .5rem; font-size: .9rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }
  .card { display: block; background: #fff; border: 1px solid #d0d7de; border-radius: 8px;
          padding: 1rem; text-decoration: none; color: inherit;
          transition: border-color .15s, box-shadow .15s; }
  .card:hover { border-color: #0969da; box-shadow: 0 1px 6px rgba(9,105,218,.2); }
  .card h3 { font-size: 1rem; color: #0969da; }
  .card .desc { font-size: .85rem; color: #57606a; margin: .4rem 0; min-height: 2.6em; }
  .card .meta { font-size: .75rem; color: #8b949e; border-top: 1px solid #eaeef2; padding-top: .5rem; }
  .card .updated { margin-right: .5rem; }
  footer { margin-top: 2rem; text-align: center; color: #8b949e; font-size: .8rem; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>watanabe3tipapa の公開サイト・サービス一覧</h1>
    <p>{{COUNT}} 件（GitHub Actions で自動生成 / 最終更新: {{GENERATED_AT}}）</p>
  </header>
  <div class="grid">
{{CARDS}}
  </div>
  <footer>Powered by GitHub Actions &amp; GitHub Pages</footer>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    main()