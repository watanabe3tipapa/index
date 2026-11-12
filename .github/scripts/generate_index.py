#!/usr/bin/env python3
"""Generate docs/index.html from public repos with GitHub Pages enabled.

Usage:
    GITHUB_TOKEN=xxx python3 .github/scripts/generate_index.py
    (token is optional; unauthenticated API is limited to ~60 req/hr)
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

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

# Private リポジトリ由来の LP は API から取得できないため、手動管理の JSON を読み込む。
try:
    with open(os.path.join(REPO_ROOT, ".github", "private-links.json")) as f:
        PRIVATE_LINKS = json.load(f)
except FileNotFoundError:
    PRIVATE_LINKS = []


def esc(value):
    return html.escape(str(value or ""), quote=True)


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


def annotate_private_status(items):
    """Attach 'status' to private-derived links by checking each URL."""
    def probe(item):
        return item["url"], http_status(item["url"])
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(probe, it) for it in items]
        status = {}
        for fut in as_completed(futures):
            url, code = fut.result()
            status[url] = code
    for it in items:
        it["status"] = status.get(it["url"], -1)


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

    private_items = [dict(it) for it in PRIVATE_LINKS]
    min_updated = CONFIG.get("privateMinUpdated", "")
    if min_updated:
        private_items = [it for it in private_items if str(it.get("updated", "")) >= min_updated]
    private_items.sort(key=lambda r: r.get("updated", ""), reverse=True)
    annotate_private_status(private_items)

    ok_items = [it for it in items if it["status"] not in (404, -1)]
    broken_items = [it for it in items if it["status"] in (404, -1)]
    # Now:404 は最下部へ（更新順に整列）
    broken_items.sort(key=lambda r: r["updated"], reverse=True)

    cards = "\n".join(render_card(r, i) for i, r in enumerate(ok_items))
    broken_cards = "\n".join(render_broken_card(r) for r in broken_items)
    private_cards = "\n".join(render_private_card(r, i) for i, r in enumerate(private_items))

    html_out = HTML_TEMPLATE
    html_out = html_out.replace("{{COUNT}}", str(len(items)))
    html_out = html_out.replace("{{OK_COUNT}}", str(len(ok_items)))
    html_out = html_out.replace("{{BROKEN_COUNT}}", str(len(broken_items)))
    html_out = html_out.replace("{{PRIVATE_COUNT}}", str(len(private_items)))
    html_out = html_out.replace("{{CARDS}}", cards)
    html_out = html_out.replace("{{BROKEN_CARDS}}", broken_cards)
    html_out = html_out.replace("{{PRIVATE_CARDS}}", private_cards)
    html_out = html_out.replace("{{GENERATED_AT}}", __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    out = os.path.join(REPO_ROOT, "docs", "index.html")
    with open(out, "w") as f:
        f.write(html_out)
    print(f"Generated {len(items)} repos ({len(ok_items)} ok / {len(broken_items)} 404) "
          f"+ {len(private_items)} private-derived links -> {out}")


CARD_COLORS = ["#fff", "#ffe14d", "#9ef01a", "#7ec8e3", "#ffadad"]
PRIVATE_COLORS = ["#e9d5ff", "#ddd6fe", "#c7d2fe", "#fae8ff", "#fff"]


def render_broken_card(r):
    desc = esc(r["description"] or "（説明なし）")
    status = r.get("status", -1)
    label = "404" if status == 404 else "ERR"
    return f'''
      <a class="card broken" href="{esc(r["repo_url"])}" rel="noopener" target="_blank">
        <span class="tag broken-tag">NOW:{label}</span>
        <h3>{esc(r["name"])}</h3>
        <p class="desc">{desc}</p>
        <p class="date">更新 {esc(r["updated"])}</p>
      </a>'''


def render_card(r, index):
    desc = esc(r["description"] or "（説明なし）")
    bg = CARD_COLORS[index % len(CARD_COLORS)]
    return f'''
      <a class="card" style="background:{bg}" href="{esc(r["pages_url"])}" rel="noopener">
        <span class="tag">UPDATE-STAMP</span>
        <h3>{esc(r["name"])}</h3>
        <p class="desc">{desc}</p>
        <p class="meta">
          <span class="repo">{esc(r["name"])}</span>
        </p>
        <p class="date">更新 {esc(r["updated"])}</p>
      </a>'''


def render_private_card(r, index):
    desc = esc(r.get("description") or "（説明なし）")
    url = r.get("url", "")
    host = urlparse(url).hostname or url
    status = r.get("status", -1)
    broken = status in (404, -1)
    label = "404" if status == 404 else "ERR"
    bg = PRIVATE_COLORS[index % len(PRIVATE_COLORS)]
    card_class = "card private broken" if broken else "card private"
    tag = f'NOW:{label}' if broken else "FROM PRIVATE"
    tag_class = "tag private-tag broken-tag" if broken else "tag private-tag"
    return f'''
      <a class="{card_class}" style="background:{bg}" href="{esc(url)}" rel="noopener" target="_blank">
        <span class="{tag_class}">{tag}</span>
        <h3>{esc(r.get("name"))}</h3>
        <p class="desc">{desc}</p>
        <p class="meta">
          <span class="repo">{esc(host)}</span>
        </p>
        <p class="date">更新 {esc(r.get("updated"))}</p>
      </a>'''


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitHub - INDEX</title>
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
  .section.first { margin-top: 0; border-top: none; padding-top: 0; }
  .section .title { display: inline-block; background: #000; color: #fff; font-weight: 900;
                    font-size: 1.3rem; padding: .4rem 1rem; border: 3px solid #000;
                    box-shadow: 6px 6px 0 #ff2d75; margin-bottom: 1.2rem; }
  .section .title small { font-size: .9rem; }
  .section .title.private-title { box-shadow: 6px 6px 0 #7c3aed; }
  .card.private { border-color: #7c3aed; box-shadow: 8px 8px 0 #7c3aed; }
  .card.private:hover { box-shadow: 0 0 0 4px #7c3aed; }
  .private-tag { background: #7c3aed; }
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
    <h1>GitHub - INDEX</h1>
    <p>公開リポジトリ <b>{{COUNT}}</b> 件 と、Private リポジトリから派生した LP <b>{{PRIVATE_COUNT}}</b> 件。</p>
    <p><small>自動生成: {{GENERATED_AT}}</small></p>
  </header>
  <div class="section first" id="public-repos">
    <span class="title">Public リポジトリ <small>({{OK_COUNT}})</small></span>
    <div class="grid">
{{CARDS}}
    </div>
  </div>
  <div class="section" id="private-derived">
    <span class="title private-title">Private リポジトリから派生する LP など <small>({{PRIVATE_COUNT}})</small></span>
    <div class="grid">
{{PRIVATE_CARDS}}
    </div>
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