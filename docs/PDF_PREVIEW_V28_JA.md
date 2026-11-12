# MCP File Manager UI v28 — PDFプレビュー実装・検証

日付: 2026-11-12（JST）

状態: **両ホストにソース配置済み・未デプロイ・未コミット・未push**

パッケージ候補: `0.4.0` / UI `v28`

## 1. 利用方法

File Managerのパス入力またはExplorerから許可済みの `.pdf` ファイルを開く。新UIはPDF専用の読み取り専用ペインを表示する。

- **Previous / Next**: 前・次のページへ移動
- **ページ番号 + Go**: 指定ページに移動
- **− / + / Fit**: 拡大縮小・幅に合わせる表示
- **Text**: 現在のページから抽出できた文字列を表示・コピー
- **Reload**: ファイルを再取得し、変更後の内容を開き直す
- PDFタブ: タブの切り替え後もページ番号とズーム設定を保持

PDFページはブラウザ内にバンドルしたPDF.jsを使用してCanvasに描画する。画像はCanvasを通じて表示し、PDF内のJavaScript、リンク、添付ファイルを起動する機能は設けない。

## 2. MCP APIとセキュリティ

- `src/mcp_file_viewer/pdf_preview.py`: 既存の `ReadOnlyFileAccess._open` を使い、許可ルート・秘密ファイル・通常ファイルの制約を維持。拡張子 `.pdf`（大文字小文字不問）と先頭の `%PDF-` マジックを確認。
- `file_manager_pdf_info(path)`: MIME `application/pdf`、ファイルサイズ、24 KiBのチャンクサイズ、`pdfstat:`形式のメタデータ・リビジョンを返す。
- `file_manager_pdf_chunk(path, offset, revision)`: 一度に最大24 KiB、Base64で送信。変更されたファイル、無効なオフセット、改ざんされたリビジョンを拒否。
- 両APIの公開範囲は `ui.visibility=["app"]`。Upload/Download機能の許可は変更しない。
- 上限は既存の `max_file_bytes`（標準 **2 MiB**）とPDF専用ハード上限 **8 MiB** の小さい方。大きなPDFは安全にエラーを返す。
- リビジョンはinode・サイズ・mtime・ctime等のメタデータに基づくSHA-256であり、文書全体の内容SHA-256ではない。
- PDFは既存MCPセッションからのみ取得。HTTPサーバー、CDN、別のSSHトンネル、ローカル一時保存は不要。

## 3. フロントエンド

- `frontend/src/pdf-preview.ts`: PDF.js 5.4.394を使用。PDF.js本体とworkerコードを同じ単一HTMLに同梱する。ネットワークWorkerの取得を避け、PDF.js内部のfake-worker構成を採用。
- 取得時に全チャンクのリビジョン、位置、バイト数を検証。最大4並列、合計8 MiB以下のクライアントバッファに限定。
- Canvas描画は **最大400万画素**かつ各辺 **4096px以下**に制限。1ページのみ描画し、ページ変更時に再描画する。
- PDF.js設定で動的評価を無効化し、XFAを無効化。内容描画はCanvasのみで、注釈スクリプトや外部リンクは描画しない。
- テキスト抽出は現在ページのみ、最大300,000文字。PDF内の一部フォントや画像スキャンの文字は抽出できない場合がある。
- 暗号化・パスワード付きPDF、破損PDF、巨大PDFはエラーとなることがある。パスワード入力UIは未実装。

## 4. 既存UIとの互換性

- 現行URI: `ui://mcp-file-manager/v28/app.html`
- 旧v27画像UIは `ui://mcp-file-manager/v27/app.html` として元のHTMLを保持
- 旧v26・v25・v24…なども元のリソースを維持
- PNG/JPEG/GIF/WebP、Markdown・数式表示、1000行自動読み込み、Load more、編集、Git History等の既存機能の処理を変更しない

## 5. 検証状況

- sham: `python_venv -m pytest -q` **78件PASS**（PDF向け5件追加）
- sham: `npm run check`、`npm run test:pdf`、`npm run build` PASS
- Node上でPDF.jsによる**2ページのテストPDF解析・ページ単位の文字抽出・PDFページのCanvas実描画（非空白画素）**を確認
- v28の単一HTMLはshamで生成し、ohtakaではv27からの差分を検証して再構成。両環境で **2,970,645 bytes**、SHA-256 `171bcbf50e134495f6362639b5c00b02de7a941bfe4b5041508c1982895c4361` で完全一致
- ohtakaは許可されたPython 3.6環境のみのため、pytestの実行は未実施
- **ChatGPT MCP Apps iframe内のPDF Canvas実描画は未検証**。サービス反映後に少なくとも1ページPDF・複数ページPDFを開いて確認が必要

## 6. リリースゲート

本実装はユーザーの許可なしにサービス再起動・HPC-MCP設定変更・Git commit/tag/pushをしない。Python 3.12のohtaka仮想環境が存在してもMCP許可リストを回避しない。

変更前バックアップは両環境の `.pdf_preview_v28_backup_20261112/MANIFEST.json` に保存済み。旧UI・研究成果物は変更しない。
