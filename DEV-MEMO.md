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
  workflows/update-repos.yml      # 定期/手動トリガーの自動巡回ワークフロー
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
- **GitHub Actions の実動作確認**：未 push のため未検証。`git push` 後に Actions タブで `Update repository index` の実行（`workflow_dispatch` 手動実行）と Pages 更新を要確認。
- 掲載初期状態は **71 件すべて表示**。ワークショップ系が多いため、`index-exclude.txt` で絞り込むべきか要判断。

### push 完了（2026-08-05）
- コミット `66d5880`「Add GitHub Actions auto index generation for GitHub Pages」を `main` に push 成功。
- ダミー学習用 `run.yml` を削除（毎 push 動作の無駄を排除）。
- 未コミット残: `PLAN.md`（計画文書のため本リポジトリへは含めず）。
- **次の確認**：GitHub Actions タブで `Update repository index` が手動トリガー / cron で回り、`docs/index.html` が公開されることを確認。

### GitHub Pages 公開（2026-08-05）
- Pages は既に有効だったが、公開元が `/`（ルート）だったため **`main` / `/docs`** に変更。
- `build_type` が `workflow`（Actions 前提）だったため、**`legacy`（ブランチからデプロイ）に変更**。
- 空コミットの push でビルドを発火 → **`https://watanabe3tipapa.github.io/index/` が HTTP 200 で公開**。
- 実機確認: title「watanabe3tipapa の公開サイト・サービス一覧」/ カード **71 件** / リンク正常。
- **残TODO**：Actions の `Update repository index` が `legacy` 環境下で `docs/index.html` を更新→ push に成功することの実動作確認（毎日 cron で回る）。

### LP デザイン刷新（neo-brutalism）（2026-08-05）
- ユーザー要望: 「LP の CSS を追加、neo-brutalism 調に変更、使用フォントのサイズを大きめに」。
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

### 日次スケジュール変更 & 手動更新（2026-08-07）
- ユーザー要望: 「設定時刻を **01:00 UTC** に変更（JST 10:00）」＋「手動で更新も行う」。
- `.github/workflows/update-repos.yml` の `cron: '0 8 * * *'` → **`cron: '0 1 * * *'`** に変更。
- コミット `5e2796f`「Set daily schedule to 01:00 UTC」push 済み（push 時、cron 生成コミット `760d25a` と rebase で吸収）。
- 手動更新: `gh workflow run update-repos.yml`（workflow_dispatch、run ID 31155668110）→ **success**。
  手動実行が `docs/index.html` を再生成し、コミット `3a087ae`「Update repository index [ci]」として push。
- 確認: `origin/main` と同期、公開ページ `https://watanabe3tipapa.github.io/index/` は HTTP 200。
- **補足（実行時刻）**: 設定は毎日 01:00 UTC（10:00 JST）。GitHub の schedule 遅延により実実行は概ね
  **03:30 UTC（12:30 JST）頃**になる（2026-08-06 実績 10:28 UTC）。

### Now:404 カテゴリー追加（2026-08-07）
- ユーザー要望: 「それぞれの GitHub Pages で 404 となっているものを、表の最下部で **Now:404** という
  カテゴリーにまとめて表示。手直しする際に便利」。
- `generate_index.py` を拡張:
  - `http_status()`: 各 Pages URL を GET して HTTP ステータスを取得（`urllib`、タイムアウト15s）。
  - `annotate_status()`: `ThreadPoolExecutor(max_workers=10)` で**並列チェック**（71→72件でも高速）。
  - 分類: `status` が **404 or -1**（接続エラー）→ `broken_items`、それ以外 → `ok_items`。
  - 404 カードは **`repo_url`（GitHub リポジトリ）へリンク**（修正作業に直結）。通常カードは `pages_url` のまま。
- HTML テンプレート: 最下部に `#now-404` セクション追加。
  - タイトル「Now:404 (件数)」、赤系デザイン（`#ff2d75` 枠/影）、`NOW:404` / `NOW:ERR` スタンプ。
  - ヘッダー件数は「全72件」表示のまま、通常カードは 54 枚に。
- 生成結果: **72 件（54 ok / 18 404）**。
  - Now:404 に分類されたリポジトリ（18件）: markdown-editor / ollama-sakana-ai / ollama-model-runner /
    ollama-lexical-editor-pe / joke-macos9-pe / joke-windows3-pe / joke-windows3-ce / ollama-eo-pe /
    notion-ollama-webui / ai-ratchet-pe / notion-ollama-pe / markitdown-ce / mintlify-docs / zakki6 /
    ReStartPC-ACTION / next.js / react-markdown / docs
- コミット `7b59925`「Add Now:404 section listing repos with failing Pages」push 済み。
- 手動更新（workflow_dispatch、run ID `31156596517`）→ **success**、Pages 反映確認済み。
- **注意（誤判定の可能性）**: 100件目以降に存在した `docs` / `next.js` / `react-markdown` / `ReStartPC-ACTION`
  は専用サブドメイン等で URL 形式が異なる可能性。カスタムドメインやリダイレクトの場合は除外リスト
  （`index-exclude.txt`）や判定ロジックで調整可能。
### LP 再編集: Public / Private の2セクション化（2026-11-12）
- ユーザー要望: 「GitHub - INDEX」「Public リポジトリのリンク（現行）」
  「Private リポジトリから派生する LP などへのリンク」の構成に再編集。
- `generate_index.py` を拡張:
  - ページタイトル / h1 を **`GitHub - INDEX`** に変更。
  - 「Public リポジトリ」「Private リポジトリから派生する LP など」「Now:404」の3セクション構成。
  - Private 由来カードは紫系（`#7c3aed`）＋ `FROM PRIVATE` スタンプ。404/ERR 時は既存の赤系表示に切替。
  - 説明文・属性値を `html.escape` でエスケープ。
- Private 由来リンクは API から取得不可（Actions の `GITHUB_TOKEN` は自リポジトリのみ）のため、
  認証済み `gh repo list watanabe3tipapa --visibility private` から `.github/private-links.json` を生成して同梱。
  - 収録条件: `homepageUrl` が公開 http(s) URL、`127.0.0.1` / `localhost` / CodeSandbox / mybinder は除外。
  - **2022年更新のものは非掲載**（ユーザー指示）。恒久ルールとして
    `index-config.json` に `"privateMinUpdated": "2023-01-01"` を追加し、スクリプト側でも除外。
- 初回生成結果: **Public 93 件（83 ok / 10 404）＋ Private 由来 33 件**。
  - Private 33 件のうち 10 件は匿名アクセスで 404/ERR（Private リポジトリの Pages アクセス制御等）。
- README に2セクション構成・`private-links.json`・`privateMinUpdated` を追記。

### CI 堅牢化（2026-11-12）
- 目的: 定期実行が API レート制限・一時障害・同時実行・push 競合・不完全な生成物で失敗／破損しないようにする。
- `generate_index.py`:
  - GitHub API 呼び出しに **20 秒タイムアウト**と**最大3回のリトライ**（403/429/5xx/接続エラー、`Retry-After`・`X-RateLimit-Reset` を考慮したバックオフ）を追加。
  - ページネーション上限（50ページ）と API レスポンス型チェックを追加。
  - ステータスチェックをインデックス管理に変更し、個別サイトの例外で全体が落ちないよう修正。
  - Private リンクの正規化・URL 重複排除・不正エントリのスキップを追加。
  - 生成後に **プレースホルダ残存 / タイトル / カード件数 / 0件** を検証。異常時は書き込まない。
  - `docs/index.html` を **一時ファイル + `os.replace`** でアトミック更新。
- `update-repos.yml`:
  - `concurrency: update-repository-index`（`cancel-in-progress: false`）で定期／手動実行を直列化。
  - `timeout-minutes: 20`、`setup-python@v7`（3.12 固定）、`PYTHONUNBUFFERED` / `GIT_TERMINAL_PROMPT=0` を設定。
  - Actions を `checkout@v7` / `setup-python@v7` / `upload-artifact@v7` に更新（Node 20 非推奨警告の解消）。
  - push 失敗時に `git pull --rebase --autostash` して最大3回再試行。
  - 実行結果とカード件数を Job Summary に出力。失敗時は生成物を artifact として 3 日保存。
- ローカル検証: 再生成成功（Public 93 件 / 83 ok・10 404、Private 33 件）、バリデータの異常系テスト OK、Workflow YAML 構文 OK。

### リポジトリ全体のタイポチェック（2026-11-12）
- 手動で全テキストファイル（README / DEV-MEMO / ワークフロー / スクリプト / JSON / 生成 HTML）を確認。
- 修正:
  - README: 「GitHub Pagesで」「neo-brutalism調」の区切り、「README 内の…」の自己言及表現を整理。
  - DEV-MEMO: 「neo Brutalism 調」→「neo-brutalism 調」、`未push` / `手動トリガ` / `派生するLP` の表記統一。
  - `private-links.json`: 説明文の末尾スペース除去、`=~` → `—`、`。|` → `。`。
  - `generate_index.py`: 検証メッセージ `Unreplaced` → `Unresolved`。
  - 上流データ: `ollama-sakana-ai` の description `Rachet` → `Ratchet`（README の表記に合わせて修正）。
- 再生成後もカード件数は Public 93（83 ok / 10 404）＋ Private 33 で変化なし。

### 上流 description の整備（2026-11-12）
- GitHub の公開リポジトリ description を全件スキャンし、前後スペース・連続スペース・全角スペースを正規化（9件）。
  - 対象: gist-editor-ce / ReStartPC-ACTION / site-uploader-pe / seek-an / pdf-sandbox /
    daily-news-digest / gtfs-jp-sandbox / next / cfos-sandbox
- `gh repo edit --description` は `updated_at` を更新して並び順に影響するため、
  Public カードの「更新日」と並び順を **`pushed_at`（最終 push 日時）** 基準に変更。
  - `updated_at != pushed_at` は全93件中8件のみ（今回の description 編集7件＋issues-astro-cms）。
- 再生成後: Public 93（83 ok / 10 404）＋ Private 33、表示上の空白異常 0 件。

### 手動再生成・検証（2026-11-14）
- `GITHUB_TOKEN` を付けてローカル再生成し、`docs/index.html` を検証。
  - 結果: Public 93（83 ok / 10 404）＋ Private 33 = **126 カード**（前回と同数）。
  - 検証: プレースホルダ 0 / リンク重複 0 / `pushed_at` 降順 / Now:404 は 20 件すべて実 404（接続エラー 0）。
- ローカル生成物は、同日 07:15 UTC の CI 生成物と**タイムスタンプ行以外は完全一致**。
  そのため `docs/index.html` は CI 版（5bea9c2）をそのまま採用し、差分のコミットは行っていない。
- 前回確認時（2026-11-12）からの実質的な変更は、11/12 以降に push された 6 リポジトリの更新日と並び順のみ。
  - 対象: editorial-collector / watanabe3tipapa / frameworks-now / standard-libraries-now / goose-sandbox / 3d-books。
  - 追加・消失リポジトリなし。
