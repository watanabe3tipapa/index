#!/usr/bin/env python3
"""Generate docs/index.html from public repos with GitHub Pages enabled.

Usage:
    GITHUB_TOKEN=xxx python3 .github/scripts/generate_index.py
    (token is optional; unauthenticated API is limited to ~60 req/hr)
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import urllib.error
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


def http_status(url, timeout=15):
    """Return HTTP status code for url; -1 for connection/timeout errors."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (index-generator)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


def annotate_status(items):
    """Attach 'status' to each item by checking its pages URL concurrently."""
    def probe(item):
        return item["name"], http_status(item["pages_url"])
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(probe, it) for it in items]
        status = {}
        for fut in as_completed(futures):
            name, code = fut.result()
            status[name] = code
    for it in items:
        it["status"] = status.get(it["name"], -1)


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

    annotate_status(items)

    ok_items = [it for it in items if it["status"] not in (404, -1)]
    broken_items = [it for it in items if it["status"] in (404, -1)]
    # Now:404 は最下部へ（更新順に整列）
    broken_items.sort(key=lambda r: r["updated"], reverse=True)

    cards = "\n".join(render_card(r, i) for i, r in enumerate(ok_items))
    broken_cards = "\n".join(render_broken_card(r) for r in broken_items)

    html = HTML_TEMPLATE
    html = html.replace("{{COUNT}}", str(len(items)))
    html = html.replace("{{OK_COUNT}}", str(len(ok_items)))
    html = html.replace("{{BROKEN_COUNT}}", str(len(broken_items)))
    html = html.replace("{{CARDS}}", cards)
    html = html.replace("{{BROKEN_CARDS}}", broken_cards)
    html = html.replace("{{GENERATED_AT}}", __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    out = os.path.join(REPO_ROOT, "docs", "index.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"Generated {len(items)} repos ({len(ok_items)} ok / {len(broken_items)} 404) -> {out}")


CARD_COLORS = ["#fff", "#ffe14d", "#9ef01a", "#7ec8e3", "#ffadad"]


def render_broken_card(r):
    desc = r["description"] or "（説明なし）"
    status = r.get("status", -1)
    label = "404" if status == 404 else "ERR"
    return f'''
      <a class="card broken" href="{r["repo_url"]}" rel="noopener" target="_blank">
        <span class="tag broken-tag">NOW:{label}</span>
        <h3>{r["name"]}</h3>
        <p class="desc">{desc}</p>
        <p class="date">更新 {r["updated"]}</p>
      </a>'''


def render_card(r, index):
    desc = r["description"] or "（説明なし）"
    bg = CARD_COLORS[index % len(CARD_COLORS)]
    return f'''
      <a class="card" style="background:{bg}" href="{r["pages_url"]}" rel="noopener">
        <span class="tag">UPDATE-STAMP</span>
        <h3>{r["name"]}</h3>
        <p class="desc">{desc}</p>
        <p class="meta">
          <span class="repo">{r["name"]}</span>
        </p>
        <p class="date">更新 {r["updated"]}</p>
      </a>'''


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>watanabe3tipapa の公開サイト・サービス一覧</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { font-size: 18px; }
  body { font-family: "Arial Black", Arial, "Hiragino Kaku Gothic ProN", "Hiragino Sans", sans-serif;
         line-height: 1.5; color: #000; background: #f6f6f4; padding: 2.5rem 1rem; min-height: 100vh; }
  .wrap { max-width: 1020px; margin: 0 auto; }
  header { margin-bottom: 2.5rem; }
  .badge { display: inline-block; background: #000; color: #fff; font-weight: 900;
           padding: .3rem .8rem; border: 3px solid #000; box-shadow: 4px 4px 0 #ff2d75; margin-bottom: 1.2rem; }
  header h1 { font-size: 2rem; font-weight: 900; border: 4px solid #000; background: #ffe14d;
              display: inline-block; padding: .6rem 1.2rem; box-shadow: 8px 8px 0 #000;
              text-transform: uppercase; letter-spacing: .5px; }
  header p { margin-top: 1.2rem; font-size: 1rem; font-weight: 700; }
  header p b { background: #9ef01a; padding: .1rem .4rem; border: 2px solid #000; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.6rem; }
  .card { display: flex; flex-direction: column; position: relative; padding: 1.4rem;
          border: 4px solid #000; box-shadow: 8px 8px 0 #000; border-radius: 0;
          text-decoration: none; color: #000;
          transition: transform .1s ease, box-shadow .1s ease; }
  .card:hover { transform: translate(-4px, -4px); box-shadow: 0 0 0 4px #000; }
  .card:active { transform: translate(2px, 6px); box-shadow: 2px 2px 0 #000; }
  .card .tag { position: absolute; top: -0.9rem; right: 1rem; background: #000; color: #fff;
               font-size: .8rem; font-weight: 900; padding: .15rem .6rem; border: 2px solid #fff;
               transform: rotate(3deg); }
  .card h3 { font-size: 1.5rem; font-weight: 900; margin: .6rem 0 .4rem; word-break: break-all; }
  .card .desc { font-size: 1.05rem; font-weight: 700; min-height: 3em; flex: 1; }
  .card .meta { border-top: 3px dashed #000; padding-top: .8rem; margin-top: .5rem; }
  .card .repo { font-size: .75rem; font-weight: 900; }
  .card .date { align-self: flex-end; margin-top: .5rem; font-size: .85rem; font-weight: 900;
                background: #fff; border: 2px solid #000; padding: .1rem .4rem; }
  .section { margin-top: 3rem; border-top: 4px solid #000; padding-top: 1.5rem; }
  .section .title { display: inline-block; background: #000; color: #fff; font-weight: 900;
                    font-size: 1.3rem; padding: .4rem 1rem; border: 3px solid #000;
                    box-shadow: 6px 6px 0 #ff2d75; margin-bottom: 1.2rem; }
  .section .title small { font-size: .9rem; }
  .card.broken { border-color: #ff2d75; background: #fff0f3; box-shadow: 8px 8px 0 #ff2d75; }
  .card.broken:hover { transform: none; box-shadow: 8px 8px 0 #ff2d75; }
  .card.broken h3 { color: #ff2d75; }
  .broken-tag { background: #ff2d75; }
  footer { margin-top: 3rem; text-align: center; font-size: .9rem; font-weight: 900;
           border-top: 4px solid #000; padding-top: 1rem; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="badge">MY STUFF ON THE WEB</span>
    <h1>公開サイト・サービス一覧</h1>
    <p>watanabe3tipapa の公開リポジトリを <b>{{COUNT}}</b> 件ピックアップ。</p>
    <p><small>自動生成: {{GENERATED_AT}}</small></p>
  </header>
  <div class="grid">
{{CARDS}}
  </div>
  <div class="section" id="now-404">
    <span class="title">Now:404 <small>({{BROKEN_COUNT}})</small></span>
    <div class="grid">
{{BROKEN_CARDS}}
    </div>
  </div>
  <footer>Powered by GitHub Actions &amp; GitHub Pages</footer>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    main()