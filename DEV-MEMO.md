# DEV-MEMO

本リポジトリ（`watanabe3tipapa/index`）の開発メモ。

---

## 要件（PLAN.md から）と決定事項

自分のリポジトリ関連で「サイト・サービスを公開しているもの」の一覧を GitHub Pages で紹介するサイトを作る。

| 項目 | 決定 |
| ---- | ---- |
| 1. 自動巡回 or 手動管理 | **B: GitHub Actions で自動巡回** |
| 2. 掲載方法 | **B: 全公開リポジトリ自動一覧**（説明はリポジトリ description を使用） |
| 3. 既存 index.md | **廃止**（生成 HTML に置き換える） |

- 公開先: プロジェクトサイト方式 → `https://watanabe3tipapa.github.io/index/`
- 公開元: `docs/` フォルダ（main ブランチ）
- Pages 有効かつ公開リポジトリのみを自動一覧化

---

## アイデア・設計判断

- **`.nojekyll` を置いて Jekyll を無効化**：生成済みの素の静的 HTML をそのまま配信する。
  これで `docs/index.html` と `docs/index.md` の優先順位衝突を根本的に回避（index.md は削除する）。
- **Pages 有効リポジトリのみ自動フィルタ**：`has_pages == true` のものを掲載。
- **除外リストでキュレーション**：`has_pages` だけだとワークショップ用リポジトリまで大量に出るため、
  `.github/index-exclude.txt` に 1 行 1 リポジトリで非掲載指定できるようにする。
- **ユーザーサイト（`watanabe3tipapa.github.io`）の扱い**：Pages URL 算出を分岐し、カスタムドメイン等は
  `.github/index-config.json` のオーバーライドで上書き可能にする。
- **残課題**：
  - 掲載初期状態は「全部表示」だが、ワークショップ系が多いので除外リストで絞り込むか要判断。
  - Jekyll テーマ（`_config.yml`）は不使用になるため、そのままでも無害（`.nojekyll` で無視）。

---

## ファイル構成

```
.github/
  workflows/update-repos.yml      # 定期/手動トリガの自動巡回ワークフロー
  scripts/generate_index.py       # API取得→docs/index.html 生成スクリプト
  index-config.json               # owner / baseUrl / homeOverrides 設定
  index-exclude.txt               # 非掲載リポジトリ（1行1件、# はコメント）
.nojekyll                         # Jekyll 無効化（素の静的HTMLを配信）
docs/index.html                   # 生成物（スクリプトが上書き）
docs/index.md                     # 廃止（削除）
```

---

## 作業ログ

### 2026-08-05
- [x] PLAN.md の確認、要件整理（上表）。
- [x] GitHub REST API で公開リポジトリ一覧・`has_pages` 状況を確認（読み取り専用）。
- [x] `generate_index.py` 作成。
- [x] `update-repos.yml` 作成。
- [x] `.nojekyll` 追加、`docs/index.md` 削除。
- [x] 除外リスト（`index-exclude.txt`） / 設定ファイル（`index-config.json`）用意。
- [x] ローカル生成で `docs/index.html` を検証。

### 検証結果
- `python3 .github/scripts/generate_index.py` 実行 → **71 件**生成に成功。
- `index` リポジトリ自身は除外リスト通り **非掲載** を確認（`grep -c ">index<"` = 0）。
- `watanabe3tipapa.github.io` は `homeOverrides` により `http://watanabe3ti.com` へリンクされるのを確認。
- 出力: `docs/index.html`（677 行、カードグリッドレイアウト）。

### 残課題
- **GitHub Actions の実動作確認**：未pushのため未検証。`git push` 後に Actions タブで `Update repository index` の実行（`workflow_dispatch` 手動実行）と Pages 更新を要確認。
- 掲載初期状態は **71 件すべて表示**。ワークショップ系が多いため、`index-exclude.txt` で絞り込むべきか要判断。