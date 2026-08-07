# index

GitHub Pages で公開している「自分のサイト・サービス一覧」のランディングページ（LP）です。

## 公開 URL

- GitHub Pages: https://watanabe3tipapa.github.io/index/
  メインサイト: http://watanabe3ti.com

## 概要

- **neo-brutalism 調**の LP で、公開中のサイト・サービスをカード一覧で紹介します。
- 掲載対象は **GitHub Pages が有効な公開リポジトリ** のみ。
- 一覧は **GitHub Actions が毎日自動巡回**して自動生成します（手動実行も可）。
- 最下部に **Now:404** セクションがあり、**Pages が 404 になっているリポジトリ**をまとめて表示
  （修正時に確認しやすいよう、リポジトリへ直リンク）。

## 技術スタック

- 生成: `.github/scripts/generate_index.py`
  - GitHub REST API でリポジトリ一覧を取得 → `docs/index.html` を生成
  - 各 Pages URL を **HTTP チェック**し、404/エラーを Now:404 に分類（並列判定）
- 自動化: `.github/workflows/update-repos.yml`（毎日 01:00 UTC の `schedule` + `workflow_dispatch`）
  - ※ GitHub の schedule 遅延により実実行は概ね 03:30 UTC（12:30 JST）頃
- 配信: GitHub Pages（`main` ブランチ `/docs` フォルダ / `.nojekyll` で素の静的 HTML を配信）

## カスタマイズ

| ファイル | 用途 |
| --- | --- |
| `.github/index-exclude.txt` | 一覧に**表示しない**リポジトリ（1 行 1 件、`#` はコメント） |
| `.github/index-config.json` | owner / baseUrl / カスタムドメイン等のオーバーライド設定 |
| `.github/scripts/generate_index.py` | 生成ロジック・デザイン（CSS）テンプレート・404 判定 |

### カードについて

- 各カードは「リポジトリ名（`pages_url` へリンク）／説明／更新日」を表示。
- Now:404 カードは GitHub リポジトリへ直リンクし、`NOW:404` / `NOW:ERR` のスタンプを表示。
- 掲載から外したい、または 404 判定を外したいリポジトリは `index-exclude.txt` で非掲載にできます。

```bash
# ローカルで再生成（オプション。トークンなしは API レート制限 60回/時）
GITHUB_TOKEN=xxx python3 .github/scripts/generate_index.py
```

## 外部リンク

- [Main Site](http://watanabe3ti.com)
- [BLOG](https://watanabe3ti.txt-nifty.com/)
- [BLOG(annex)](https://wiki.watanabe3ti.com)
- [Toolsmith](https://toolsmith.watanabe3ti.com)

---