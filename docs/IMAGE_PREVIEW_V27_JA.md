# MCP File Manager UI v27 — 画像プレビュー設計・検証

日付: 2026-11-12（JST）

状態: **開発ソース実装済み・未デプロイ・未コミット・未push**

## 1. 目的

MCP File Managerの既存のパス入力、ファイルツリー、タブ、Reloadから、PNG・JPEG（.jpg/.jpeg）・GIF・WebP画像を読み取り専用で表示する。SVG、PDF、TIFFおよびその他の形式はこのフェーズの対象外。Markdown内の外部画像は引き続き自動表示しない。

## 2. 実装

- UI URI: `ui://mcp-file-manager/v27/app.html`
- 旧v26: `ui://mcp-file-manager/v26/app.html` を別リソースとして維持し、従来の単一HTMLを変更しない。
- `src/mcp_file_viewer/image_preview.py`: 既存 `FilePolicy` と `ReadOnlyFileAccess._open` を再利用。許可ルート外・秘密情報・特殊ファイルを拒否。シンボリックリンクは既存の許可ルート判定とファイルディスクリプタ検査に従う。拡張子とマジックバイトを照合し、PNG/GIFの宣言寸法が極端に大きい場合も拒否。
- `file_manager_image_info(path)`: MIME、ファイルサイズ、チャンクサイズとメタデータ・リビジョン `imgstat:<SHA256>` を返す。画像データ自体は含まない。
- `file_manager_image_chunk(path, offset, revision)`: 検証した最大24 KiBのBase64データを返す。オフセットはチャンク境界に限定。各要求時に同じファイルのinode・サイズ・mtime・ctimeを検証する。
- 両APIは `ui.visibility=["app"]` でFile Managerアプリ専用に登録。Upload/Download機能は有効化しない。
- `frontend/src/image-preview.ts`: 最大4並列でチャンクを読み出し、Base64とリビジョン・バイト長・継続位置を検証し、`data:image/...;base64,` URLを組み立てる。
- `frontend/src/main.ts`: 画像のOpen/Reload、画像タブの切替、ファイル名・サイズ表示、フィット/原寸表示切替。画像の編集、Git History、本文検索、Load moreは無効。
- `frontend/index.html`: 独立した `image-pane` を設置。Markdown用DOMPurifyの画像禁止は維持。
- タブを閉じるまで画像データはアプリ内のメモリに保持。外部HTTPアクセス、画像の一時ファイル生成、HPC上での画像のデコード・リサイズは行わない。

## 3. 制約と安全性

- 画像は既存の `max_file_bytes` を超えて取得しない。規定値は2 MiB、UI画像専用上限は4 MiB。
- 24 KiBバイナリ/チャンク、1応答約33 KiBのBase64を含む画像専用の上限40,000文字。既存のテキスト用12,000文字上限は変更しない。
- `imgstat:` はメタデータ識別子のSHA-256であり、**ファイル全体のSHA-256ではない**。ロード中の通常の変更はメタデータ照合により検出される。
- PNG/GIFでは画素数8,000万を超える宣言寸法を拒否。JPEG/WebPの全寸法解析は未実装。非常に大きい・不正な圧縮画像のデコード安全性はブラウザ側にも依存する。
- SVGのスクリプト埋め込みなどを避けるためSVGは対象に含めない。
- MCP Apps仕様の既定CSPは `img-src 'self' data:` を含むが、ChatGPTの実機iframe表示・デコード可否はサービス反映後に検証する。

## 4. 検証

- sham: Python 73件の回帰テストPASS（画像テスト6件追加）。`npm run check`、`npm run test:image`、数式テストはPASS。
- sham: Vite buildで画像対応v27を単一HTMLとして生成。
- ohtaka: Node/npmがないためsham生成v27をv26ベースの検証済み差分から再構成。SHA-256とファイルサイズの一致を検証。
- sham/ohtakaの旧未コミット変更は `.image_preview_v27_backup_20261112/MANIFEST.json` に保存。既存 `.integration_preserve_20261112` 等も保持。
- ohtakaのPython 3.12 venvはMCP許可コマンド外。ohtakaのpytestと実機iframeプレビューは未実施。

## 5. リリース時の注意

本実装はv0.4.0候補に追加した**UI v27**。古い `UI v26` や `v0.3.0` が実行中のMCPサービスは再起動・コネクタ更新するまで新機能を提供しない。サービス再起動、GitHub commit/tag/push、HPC-MCP許可設定の変更はこの開発作業では行わない。
