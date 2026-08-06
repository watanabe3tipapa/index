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

### push 完了（2026-08-05）
- コミット `66d5880`「Add GitHub Actions auto index generation for GitHub Pages」を `main` に push 成功。
- ダミー学習用 `run.yml` を削除（毎 push 動作の無駄を排除）。
- 未コミット残: `PLAN.md`（計画文書のため本リポジトリへは含めず）。
- **次の確認**：GitHub Actions タブで `Update repository index` が手動トリガ / cron で回り、`docs/index.html` が公開されることを確認。

### GitHub Pages 公開（2026-08-05）
- Pages は既に有効だったが、公開元が `/`（ルート）だったため **`main` / `/docs`** に変更。
- `build_type` が `workflow`（Actions 前提）だったため、**`legacy`（ブランチからデプロイ）に変更**。
- 空コミットの push でビルドを発火 → **`https://watanabe3tipapa.github.io/index/` が HTTP 200 で公開**。
- 実機確認: title「watanabe3tipapa の公開サイト・サービス一覧」/ カード **71 件** / リンク正常。
- **残TODO**：Actions の `Update repository index` が `legacy` 環境下で `docs/index.html` を更新→ push に成功することの実動作確認（毎日 cron で回る）。

### LP デザイン刷新（neo-brutalism）（2026-08-05）
- ユーザー要望: 「LP の CSS を追加、neo Brutalism 調に変更、使用フォントのサイズを大きめに」。
- `generate_index.py` のテンプレート / `render_card` を改修してから `docs/index.html` を再生成（71件維持）。
- **neo-brutalism 実装**：
  - カード: `border: 4px solid #000` ＋ `box-shadow: 8px 8px 0 #000`（ハードシャドウ）、角丸なし。
  - ホバーで `translate(-4px,-4px)` / `:active` で押し込む動き。
  - 5色（黄・緑・水色・ピンク・白）でカードを順番に塗分け（`CARD_COLORS`）。
  - 回転付き `UPDATE-STAMP` タグ、黒地バッジ、黄色大見出しブロック、破線セパレータ。
- **フォント拡大**：`html { font-size: 18px }` 基準。h1 `2rem`、カード h3 `1.5rem`、desc `1.05rem`。
- コミット `59e7e4d`「Restyle index LP in neo-brutalism with larger fonts」push 済み。
- 検証: カード71件 / `box-shadow: 8px 8px 0 #000` 反映 / HTML 構文OK（32,943 bytes）。

### LP カード URL 表記の調整（2026-08-05）
- ユーザー要望の経緯:
  1. URL フォント縮小（`.95rem` → `.85rem`、コミット `6e40dfd`）。
  2. さらに縮小（`.75rem`、コミット `ae28b20`）。この際、Actions cron のタイムスタンプ更新（`d6e1eee`）と衝突 → rebase で解消。
  3. 「URL 非表示」要望 → いったん URL 要素ごと除去（コミット `7ad0b4a`）＋ DEV-MEMO 追録（`87b2dcf`）。
  4. **履歴巻き戻し**: ユーザー指示で 2 つ前の状態（`ae28b20`）へ `git reset --hard` + `force-with-lease` push（`7ad0b4a` / `87b2dcf` を破棄）。
  5. **最終仕様（2026-08-05）**: 「`github.com/watanabe3tipapa/` の接頭辞だけ非表示、リポジトリ名は表示」。
     `render_card` を `github.com/{OWNER}/{name}` → `{name}` のみに変更。コミット `891856e`「Show only repo name in card URL label」push 済み。
- 検証: 生成後に `github.com/watanabe3tipapa` を含む出力 0 件 / リポジトリ名のみ表示（`frameworks-now` 等）。
- 現在のカード構成: 見出し / 説明 / リポジトリ名（`.repo`）/ 更新日。