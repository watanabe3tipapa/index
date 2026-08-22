# index

GitHub Pagesで公開している「自分のサイト・サービス一覧」のランディングページ（LP）です。

## 公開 URL

- GitHub Pages: https://watanabe3tipapa.github.io/index/
- メインサイト: http://watanabe3ti.com

## 概要

- neo-brutalism調のカード一覧で、公開中のサイト・サービスを紹介する静的ページです。
- 掲載対象は GitHub Pages が有効な公開リポジトリのみを想定しています。
- 一覧は自動生成され、最下部に Pages が 404 やエラーになっているリポジトリをまとめた「Now:404」セクションを表示します。

## 主な内容・特徴

- 各カードにリポジトリ名（Pages URL へリンク）、説明、更新日を表示。
- Now:404 セクションでは、Pages が 404/エラーになっているリポジトリへ直リンクし、`NOW:404` / `NOW:ERR` スタンプを付与。
- 掲載対象のフィルタリング・オーバーライド用の設定ファイルを用意。

## 技術スタック（実装上の事実）

- 生成スクリプト: `.github/scripts/generate_index.py`
  - GitHub REST API でリポジトリ一覧を取得し、`docs/index.html` を生成します。
  - 各 Pages URL に対して HTTP チェックを行い、404/エラーを Now:404 に分類（並列判定）。
- 自動化: `.github/workflows/update-repos.yml`
  - 毎日 01:00 UTC の schedule と `workflow_dispatch` が設定されています。
  - README 内の注記では、GitHub の schedule 遅延により実実行は概ね 03:30 UTC（12:30 JST）頃になるとされています。
- 配信: GitHub Pages（`main` ブランチの `/docs` フォルダ、`.nojekyll` を使って素の静的 HTML を配信）

## カスタマイズ（リポジトリ内の設定）

- `.github/index-exclude.txt` — 一覧に表示しないリポジトリの一覧（1 行 1 件、`#` はコメント）。
- `.github/index-config.json` — owner / baseUrl / カスタムドメイン等のオーバーライド設定。
- `.github/scripts/generate_index.py` — 生成ロジック・テンプレート・404 判定の実装を含みます。

カード表示や 404 判定の扱いは上記ファイルで制御できます。掲載から外したい、または 404 判定を外したいリポジトリは `index-exclude.txt` で非掲載にできます。

### ローカルでの再生成（README に記載の事実）

```bash
# トークンありでローカル再生成（トークンなしは API レート制限 60回/時）
GITHUB_TOKEN=xxx python3 .github/scripts/generate_index.py
```

## リポジトリ構成（ルートにある主なファイル・フォルダ）

- .github
- .nojekyll
- DEV-MEMO.md
- README.md
- _config.yml
- assets
- docs

## 外部リンク

- Main Site: http://watanabe3ti.com
- BLOG: https://watanabe3ti.txt-nifty.com/
- BLOG(annex): https://wiki.watanabe3ti.com
- Toolsmith: https://toolsmith.watanabe3ti.com

## 開発・保守状態

- 一覧は GitHub Actions による自動巡回で毎日更新されます（手動実行も可能）。
- README 内の記載に基づき、スケジュール実行は遅延の影響で実際の実行時刻が変動する旨が明記されています。

## ライセンス

- リポジトリ内に明示的なライセンス表記は確認できません。

---

（この README はリポジトリ内に元々あった情報に基づき、構成と導線を整理して再構成したものです。）
