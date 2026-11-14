#!/usr/bin/env python3
"""Generate docs/index.html from public repos with GitHub Pages enabled.

Usage:
    GITHUB_TOKEN=xxx python3 .github/scripts/generate_index.py
    (token is optional; unauthenticated API is limited to ~60 req/hr)

The script retries transient GitHub API failures, validates the generated
HTML, and writes the file atomically so a failed run never publishes a
truncated page.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "https://api.github.com"
OWNER = "watanabe3tipapa"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

API_TIMEOUT = 20
API_RETRIES = 3
STATUS_TIMEOUT = 15
STATUS_WORKERS = 10

# 「本日のおすすめ」の日付判定は JST 基準（UTC だと JST 9:00 で日付が変わるため）。
JST = timezone(timedelta(hours=9))

# GitHub URL の "hub" を "diagram" に置き換えた構成図サービス。
GITDIAGRAM_BASE = "https://gitdiagram.com"

with open(os.path.join(REPO_ROOT, ".github", "index-config.json")) as f:
    CONFIG = json.load(f)
OWNER = CONFIG.get("owner", OWNER)
SITE_REPO = CONFIG.get("siteRepo", "index")
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


def _retry_delay(err, attempt):
    """Return seconds to wait before retrying an API error."""
    headers = getattr(err, "headers", None)
    if headers is not None:
        retry_after = headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return min(int(retry_after), 60)
        reset = headers.get("X-RateLimit-Reset")
        if reset and reset.isdigit():
            delay = int(reset) - int(time.time()) + 1
            if delay > 0:
                return min(delay, 60)
    return min(2 ** attempt, 30)


def api(path):
    url = BASE_URL + path
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "index-generator",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    last_error = None
    for attempt in range(1, API_RETRIES + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            last_error = e
            # 403/429 はレート制限、5xx は一時障害としてリトライする。
            if e.code not in (403, 429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_error = e
        if attempt < API_RETRIES:
            wait = _retry_delay(last_error, attempt)
            print(f"GitHub API error ({last_error}); retry {attempt}/{API_RETRIES} in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)

    raise RuntimeError(f"GitHub API request failed: {url}: {last_error}")


def fetch_all_repos():
    page = 1
    repos = []
    while page <= 50:
        batch = api(f"/users/{OWNER}/repos?per_page=100&page={page}&sort=updated")
        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected API response for page {page}: {type(batch).__name__}")
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    else:
        raise RuntimeError("Repository pagination exceeded 50 pages; refusing to continue")
    return repos


def pages_url(repo):
    if repo["name"] in HOME_OVERRIDES:
        return HOME_OVERRIDES[repo["name"]]
    if repo["name"] == f"{OWNER}.github.io":
        return CONFIG.get("baseUrl", f"https://{OWNER}.github.io")
    return f"{CONFIG.get('baseUrl', 'https://' + OWNER + '.github.io')}/{repo['name']}/"


def http_status(url, timeout=STATUS_TIMEOUT):
    """Return HTTP status code for url; -1 for connection/timeout errors."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (index-generator)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


def annotate_status(items, url_field):
    """Attach 'status' to each item by checking its URL concurrently."""
    def probe(index, item):
        try:
            return index, http_status(item[url_field])
        except Exception as e:  # 個別サイトの異常で全体を止めない
            print(f"Status check failed for {item.get(url_field)}: {e}", file=sys.stderr)
            return index, -1

    with ThreadPoolExecutor(max_workers=STATUS_WORKERS) as ex:
        futures = [ex.submit(probe, i, it) for i, it in enumerate(items)]
        status = {}
        for fut in as_completed(futures):
            index, code = fut.result()
            status[index] = code
    for index, item in enumerate(items):
        item["status"] = status.get(index, -1)


def load_private_items():
    """Normalize, filter and de-duplicate private-derived links."""
    items = []
    seen = set()
    min_updated = CONFIG.get("privateMinUpdated", "")
    for raw in PRIVATE_LINKS:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url", "")).strip()
        name = str(raw.get("name", "")).strip()
        if not name or not url.startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        updated = str(raw.get("updated", ""))[:10]
        if min_updated and updated < min_updated:
            continue
        seen.add(url)
        items.append({
            "name": name,
            "description": str(raw.get("description", "")),
            "url": url,
            "updated": updated,
        })
    items.sort(key=lambda r: r["updated"], reverse=True)
    return items


def with_description(items):
    """Pick candidates need a description to be presentable."""
    return [it for it in items if str(it.get("description", "")).strip()]


def pick_of_the_day(ok_items, config):
    """Choose today's pick deterministically from the JST date.

    The result is stable for the same date and candidate set, so every visitor
    sees the same recommendation and re-running the generator does not reshuffle
    it. `INDEX_TODAY=YYYY-MM-DD` overrides the date for tests.
    """
    cfg = config.get("dailyPick") or {}
    if not cfg.get("enabled", True):
        return None

    day = os.environ.get("INDEX_TODAY") or datetime.now(JST).strftime("%Y-%m-%d")
    salt = str(cfg.get("seedSalt", "index"))
    seed = int(hashlib.sha256(f"{day}:{salt}".encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)

    by_name = {it["name"]: it for it in ok_items}

    # 手動キュレーションがある場合はその中から日替わりで選ぶ。
    curated = []
    for entry in cfg.get("curated") or []:
        if isinstance(entry, dict):
            name = str(entry.get("name", "")).strip()
            note = str(entry.get("note", ""))
        else:
            name = str(entry).strip()
            note = ""
        item = by_name.get(name)
        if item is None:
            print(f"dailyPick: skipping unknown or unavailable repo: {name}", file=sys.stderr)
            continue
        curated.append({"item": item, "note": note})
    if curated:
        chosen = curated[rng.randrange(len(curated))]
        return {"item": chosen["item"], "note": chosen["note"], "day": day, "curated": True}

    pool = sorted(with_description(ok_items), key=lambda it: it["name"])
    if not pool:
        return None

    try:
        today = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        raise RuntimeError(f"Invalid INDEX_TODAY value: {day!r} (expected YYYY-MM-DD)")
    cutoff = (today - timedelta(days=int(cfg.get("recentDays", 14)))).strftime("%Y-%m-%d")
    fresh = [it for it in pool if it.get("updated", "") >= cutoff]
    # 7割は最近更新されたもの、3割は全件から選び、埋もれたリポジトリも拾う。
    if fresh and rng.random() < 0.7:
        pool = fresh

    return {"item": rng.choice(pool), "note": "", "day": day, "curated": False}


def pick_reason(pick):
    """Short human-readable reason for the pick, derived from its update date."""
    if pick.get("note"):
        return pick["note"]
    item = pick["item"]
    day = pick["day"]
    updated = item.get("updated", "")
    if updated == day:
        return "本日 push"
    try:
        delta = (datetime.strptime(day, "%Y-%m-%d")
                 - datetime.strptime(updated, "%Y-%m-%d")).days
    except ValueError:
        return "静かな名作"
    if 0 <= delta <= 7:
        return "今週の更新"
    return "静かな名作"


def gitdiagram_url(repo_url):
    """Map a public GitHub repository URL to its GitDiagram page."""
    parsed = urlparse(repo_url or "")
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.hostname not in ("github.com", "www.github.com"):
        return None
    path = parsed.path.rstrip("/")
    if len([part for part in path.split("/") if part]) < 2:
        return None
    return GITDIAGRAM_BASE + path


def render_pick(pick, show_diagram=True):
    if pick is None:
        return ""
    item = pick["item"]
    name = esc(item["name"])
    pages_url = esc(item["pages_url"])
    desc = esc(item.get("description") or "（説明なし）")
    stamp = "CURATED" if pick["curated"] else "AUTO PICK"
    diagram_url = gitdiagram_url(item.get("repo_url")) if show_diagram else None
    diagram = ""
    if diagram_url:
        diagram = f'''
              <a class="pick-action pick-diagram" data-diagram="{name}" href="{esc(diagram_url)}"
                 target="_blank" rel="noopener noreferrer"
                 aria-label="{name} の構成図を GitDiagram で開く（新しいタブ）"
                 title="GitDiagram で構成図を開く（新しいタブ・初回は生成に時間がかかります）">構成図 ↗</a>'''
    return f'''
        <div class="pick" data-pick="{name}">
          <a class="pick-main" href="{pages_url}" rel="noopener">
            <span class="pick-head"><span class="pick-stamp">{stamp}</span><time>{esc(pick["day"])}</time></span>
            <h3>{name}</h3>
            <span class="pick-desc">{desc}</span>
          </a>
          <div class="pick-foot">
            <span class="pick-reason">{esc(pick_reason(pick))}</span>
            <span class="pick-actions">
              <a class="pick-action pick-open" href="{pages_url}" rel="noopener">OPEN →</a>{diagram}
            </span>
          </div>
        </div>'''


def render_site_diagram(show_diagram=True):
    if not show_diagram:
        return ""
    url = f"{GITDIAGRAM_BASE}/{OWNER}/{SITE_REPO}"
    return f'''
      <p class="sidecar-site"><a data-site-diagram="1" href="{esc(url)}"
        target="_blank" rel="noopener noreferrer"
        title="GitDiagram でこのサイトの構成図を開く（新しいタブ）">このサイトの構成図 ↗</a></p>'''


def render_ticker(ok_items, ng_count):
    entries = [f'{it["name"]} {it["updated"][5:]} 更新' for it in ok_items[:6]]
    if ng_count:
        entries.insert(0, f"NG {ng_count}件")
    if not entries:
        entries = ["更新情報はありません"]
    # 2回繰り返して継ぎ目なくループさせる（CSS の translateX(-50%) と対）。
    run = "".join(f'<span class="tick">{esc(e)}</span>' for e in entries)
    return f'''
        <div class="ticker" tabindex="0" aria-label="更新情報ティッカー（フォーカスで一時停止）">
          <div class="ticker-track">{run}{run}</div>
        </div>'''


def render_sidecar(pick, ok_items, private_count, ng_count, generated_at, show_diagram=True):
    ticker = render_ticker(ok_items, ng_count)
    site_diagram = render_site_diagram(show_diagram)
    return f'''
  <details class="sidecar" open>
    <summary>
      <span class="led" aria-hidden="true"></span>
      <span class="sidecar-title">SIDECAR</span>
      <span class="sidecar-toggle" aria-hidden="true"></span>
    </summary>
    <div class="sidecar-body">
      <p class="sidecar-note">公開中の Pages を毎日自動巡回しています。更新日は最終 push 日時です。</p>{render_pick(pick, show_diagram)}{ticker}
      <dl class="sidecar-stats">
        <div><dt>PUBLIC</dt><dd>{len(ok_items)}</dd></div>
        <div><dt>PRIVATE</dt><dd>{private_count}</dd></div>
        <div><dt>NG</dt><dd>{ng_count}</dd></div>
      </dl>
      <p class="sidecar-time">生成 {esc(generated_at)}</p>{site_diagram}
    </div>
  </details>
  <script>
  (function () {{
    var sc = document.querySelector('.sidecar');
    if (!sc) return;
    var summary = sc.querySelector('summary');
    var userToggled = false;
    if (summary) summary.addEventListener('click', function () {{ userToggled = true; }});
    try {{
      var saved = localStorage.getItem('index-sidecar-open');
      if (saved === null) sc.open = window.matchMedia('(min-width: 1121px)').matches;
      else sc.open = saved === '1';
      sc.addEventListener('toggle', function () {{
        // 画面幅による初期開閉は保存せず、ユーザー操作だけを記憶する。
        if (!userToggled) return;
        localStorage.setItem('index-sidecar-open', sc.open ? '1' : '0');
      }});
    }} catch (e) {{}}
  }})();
  </script>'''


def validate_sidecar(html_out, pick, show_diagram=True):
    if html_out.count('class="sidecar"') != 1:
        raise RuntimeError("Generated HTML must contain exactly one sidecar")
    if pick is not None and f'data-pick="{esc(pick["item"]["name"])}"' not in html_out:
        raise RuntimeError("Daily pick is missing from generated HTML")
    if show_diagram:
        if 'data-site-diagram="1"' not in html_out:
            raise RuntimeError("Site GitDiagram link is missing from generated HTML")
        if 'target="_blank" rel="noopener noreferrer"' not in html_out:
            raise RuntimeError("GitDiagram link must open in a new tab")
        if pick is not None:
            diagram_url = gitdiagram_url(pick["item"].get("repo_url"))
            if diagram_url:
                name = esc(pick["item"]["name"])
                if f'data-diagram="{name}"' not in html_out:
                    raise RuntimeError("Daily pick GitDiagram link is missing from generated HTML")
                if f'href="{esc(diagram_url)}"' not in html_out:
                    raise RuntimeError("Daily pick GitDiagram URL is incorrect")


def validate_output(html_out, expected_cards):
    """Fail fast instead of publishing an incomplete/empty page."""
    if "{{" in html_out or "}}" in html_out:
        raise RuntimeError("Unresolved template placeholder remains in generated HTML")
    if "<title>GitHub - INDEX</title>" not in html_out:
        raise RuntimeError("Generated HTML is missing the expected title")
    actual_cards = html_out.count('class="card')
    if actual_cards != expected_cards:
        raise RuntimeError(f"Card count mismatch: rendered {actual_cards}, expected {expected_cards}")
    if expected_cards == 0:
        raise RuntimeError("Refusing to write an index with zero cards")


def write_atomic(path, content):
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


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
            # description 編集などで updated_at が動いても並びが変わらないよう、
            # 実際の更新日は最終 push 日時を使う。
            "updated": (repo.get("pushed_at") or repo.get("updated_at") or "")[:10],
            "homepage": repo.get("homepage") or "",
        })

    if not items:
        raise RuntimeError("No public repositories with GitHub Pages found; refusing to overwrite index.html")

    items.sort(key=lambda r: r["updated"], reverse=True)
    annotate_status(items, "pages_url")

    private_items = load_private_items()
    annotate_status(private_items, "url")

    ok_items = [it for it in items if it["status"] not in (404, -1)]
    broken_items = [it for it in items if it["status"] in (404, -1)]
    # Now:404 は最下部へ（更新順に整列）
    broken_items.sort(key=lambda r: r["updated"], reverse=True)

    cards = "\n".join(render_card(r, i) for i, r in enumerate(ok_items))
    broken_cards = "\n".join(render_broken_card(r) for r in broken_items)
    private_cards = "\n".join(render_private_card(r, i) for i, r in enumerate(private_items))

    pick = pick_of_the_day(ok_items, CONFIG)
    show_diagram = bool((CONFIG.get("dailyPick") or {}).get("diagram", True))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    private_broken = sum(1 for it in private_items if it["status"] in (404, -1))
    ng_count = len(broken_items) + private_broken
    sidecar = render_sidecar(pick, ok_items, len(private_items), ng_count, generated_at,
                             show_diagram)

    html_out = HTML_TEMPLATE
    html_out = html_out.replace("{{COUNT}}", str(len(items)))
    html_out = html_out.replace("{{OK_COUNT}}", str(len(ok_items)))
    html_out = html_out.replace("{{BROKEN_COUNT}}", str(len(broken_items)))
    html_out = html_out.replace("{{PRIVATE_COUNT}}", str(len(private_items)))
    html_out = html_out.replace("{{CARDS}}", cards)
    html_out = html_out.replace("{{BROKEN_CARDS}}", broken_cards)
    html_out = html_out.replace("{{PRIVATE_CARDS}}", private_cards)
    html_out = html_out.replace("{{GENERATED_AT}}", generated_at)
    html_out = html_out.replace("{{SIDECAR}}", sidecar)

    validate_output(html_out, len(ok_items) + len(broken_items) + len(private_items))
    validate_sidecar(html_out, pick, show_diagram)

    out = os.path.join(REPO_ROOT, "docs", "index.html")
    write_atomic(out, html_out)
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
  .card .desc { font-size: 1.05rem; font-weight: 700; min-height: 3em; flex: 1;
                overflow-wrap: anywhere; }
  .card .meta { border-top: 3px dashed #000; padding-top: .8rem; margin-top: .5rem; }
  .card .repo { font-size: .75rem; font-weight: 900; overflow-wrap: anywhere; }
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

  /* SIDECAR: ワイド画面では右に追従、狭い画面では上部の折りたたみパネル */
  .shell { display: grid; grid-template-columns: minmax(0, 1020px) 300px;
           grid-template-areas: "main side";
           gap: 2rem; max-width: 1360px; margin: 0 auto; align-items: start; }
  .wrap { grid-area: main; max-width: 1020px; margin: 0; min-width: 0; }
  .sidecar { grid-area: side; position: sticky; top: 1.5rem; width: 300px; background: #fff;
             border: 4px solid #000; box-shadow: 8px 8px 0 #000; }
  .sidecar > summary { display: flex; align-items: center; gap: .6rem; cursor: pointer;
                       list-style: none; background: #000; color: #fff; padding: .7rem .9rem;
                       font-size: .9rem; font-weight: 900; letter-spacing: .12em; }
  .sidecar > summary::-webkit-details-marker { display: none; }
  .sidecar > summary:focus-visible { outline: 4px solid #ff2d75; outline-offset: 2px; }
  .led { width: .7rem; height: .7rem; flex: none; background: #9ef01a; border: 2px solid #fff;
         animation: led-pulse 2s ease-in-out infinite; }
  .sidecar-title { flex: 1; }
  .sidecar-toggle::before { content: "−"; font-size: 1.1rem; }
  .sidecar:not([open]) .sidecar-toggle::before { content: "+"; }
  .sidecar-body { padding: 1rem; }
  .sidecar-note { font-size: .78rem; font-weight: 700; }
  .pick { display: flex; flex-direction: column; gap: .45rem; margin: 1rem 0;
          padding: .9rem; border: 3px solid #000; background: #ffe14d; box-shadow: 5px 5px 0 #000;
          color: #000; transition: transform .1s ease, box-shadow .1s ease; }
  .pick:hover { transform: translate(-3px, -3px); box-shadow: 8px 8px 0 #000; }
  .pick:active { transform: translate(1px, 3px); box-shadow: 2px 2px 0 #000; }
  .pick-main { display: flex; flex-direction: column; gap: .45rem;
               color: #000; text-decoration: none; }
  .pick-main:focus-visible { outline: 3px solid #ff2d75; outline-offset: 3px; }
  .pick-head { display: flex; justify-content: space-between; align-items: center;
               gap: .5rem; font-size: .68rem; font-weight: 900; }
  .pick-stamp { background: #000; color: #fff; padding: .15rem .45rem; }
  .pick h3 { font-size: 1.25rem; font-weight: 900; line-height: 1.25; word-break: break-all; }
  .pick-desc { font-size: .85rem; font-weight: 700; overflow-wrap: anywhere; }
  .pick-foot { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
               gap: .5rem; border-top: 3px dashed #000; padding-top: .5rem;
               font-size: .72rem; font-weight: 900; }
  .pick-reason { flex: 1 1 auto; }
  .pick-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .35rem; }
  .pick-action { display: inline-block; padding: .22rem .45rem; border: 2px solid #000;
                 font-size: .68rem; font-weight: 900; line-height: 1.3; text-decoration: none;
                 white-space: nowrap; transition: transform .1s ease, box-shadow .1s ease; }
  .pick-open { background: #000; color: #fff; }
  .pick-diagram { background: #9ef01a; color: #000; }
  .pick-action:hover { transform: translate(-1px, -1px); box-shadow: 2px 2px 0 #000; }
  .pick-action:focus-visible { outline: 3px solid #ff2d75; outline-offset: 2px; }
  .ticker { overflow: hidden; border: 3px solid #000; background: #000; color: #fff;
            font-size: .78rem; font-weight: 900; }
  .ticker-track { display: flex; width: max-content; animation: ticker-scroll 26s linear infinite; }
  .ticker:hover .ticker-track, .ticker:focus .ticker-track,
  .ticker:focus-within .ticker-track { animation-play-state: paused; }
  .ticker:focus-visible { outline: 4px solid #ff2d75; outline-offset: 2px; }
  .tick { padding: .4rem .8rem; border-right: 2px solid #fff; white-space: nowrap; }
  .sidecar-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; margin-top: 1rem; }
  .sidecar-stats div { border: 3px solid #000; padding: .5rem .25rem; text-align: center; background: #9ef01a; }
  .sidecar-stats div:nth-child(2) { background: #e9d5ff; }
  .sidecar-stats div:nth-child(3) { background: #ffadad; }
  .sidecar-stats dt { font-size: .62rem; font-weight: 900; letter-spacing: .08em; }
  .sidecar-stats dd { font-size: 1.25rem; font-weight: 900; line-height: 1.2; }
  .sidecar-time { margin-top: .8rem; text-align: right; font-size: .68rem; font-weight: 900; }
  .sidecar-site { margin-top: .8rem; }
  .sidecar-site a { display: block; padding: .5rem .4rem; border: 3px solid #000; background: #7ec8e3;
                    box-shadow: 4px 4px 0 #000; color: #000; font-size: .75rem; font-weight: 900;
                    text-align: center; text-decoration: none;
                    transition: transform .1s ease, box-shadow .1s ease; }
  .sidecar-site a:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0 #000; }
  .sidecar-site a:focus-visible { outline: 3px solid #ff2d75; outline-offset: 2px; }
  @keyframes led-pulse { 50% { background: #ff2d75; } }
  @keyframes ticker-scroll { to { transform: translateX(-50%); } }
  @media (max-width: 1120px) {
    .shell { display: block; max-width: 1020px; }
    .wrap { max-width: none; }
    .sidecar { position: static; width: auto; margin-bottom: 2rem; }
  }
  @media (prefers-reduced-motion: reduce) {
    .led { animation: none; }
    .ticker-track { animation: none; flex-wrap: wrap; width: auto; }
    .pick, .pick-action, .sidecar-site a { transition: none; }
  }
</style>
</head>
<body>
<div class="shell">
{{SIDECAR}}
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
</div>
</body>
</html>
"""


if __name__ == "__main__":
    main()