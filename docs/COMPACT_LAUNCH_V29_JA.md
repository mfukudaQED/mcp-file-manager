# MCP File Manager UI v29 — コンパクト起動カードとChatGPT内全画面表示

更新日: 2026-11-12 JST

状態: **sham・ohtakaに実装・配信確認済み。PCで全画面起動PASS、iPhoneで単一ファイル起動PASS**

バージョン: Pythonパッケージ 0.4.0候補、UI v29

## 目的

ChatGPTのチャット中に大きなファイルビュアーを常時表示せず、ファイルごとの名前・接続ホスト名・ファイル形式・「開く」ボタンを備えたコンパクトなカードを初期表示する。ユーザーが直接ボタンを押したとき、ChatGPT内部の全画面表示をMCP Appsホストに要求する。Safari/Chrome等の外部ブラウザには移動しない。

### 表示例

- **SrVO3_cRPA.pdf** · ohtaka · PDF　［開く］
- **theory.md** · sham · Markdown　［開く］
- **DOS.png** · ohtaka · 画像　［開く］

ファイル名は絶対パスのbasename、形式はファイル拡張子から取得する。名前は `textContent` を通じて設定し、任意の文字列をHTMLとして解釈しない。ホスト名はHPC-MCPサーバー側で `resolve_host_defaults()` により導出し、HTML属性のエスケープをして埋め込む。Tabby/WinSCP接続名の上書きには依存しない。

## MCP Apps表示モード

- 新URI `ui://mcp-file-manager/v29/app.html` を使う。MCP Appsリソースの `openai/ui.preferredDisplayMode` は `inline`。対応モードは `inline` / `fullscreen`。
- アプリが初期化されるときは `<section id="launch-card">` だけを表示し、旧ビュアーを含む `<div id="viewer-shell">` は隠す。
- `app.getHostContext()?.availableDisplayModes` を確認し、ボタンのクリックイベント内で `app.requestDisplayMode({mode:"fullscreen"})` を呼ぶ。
- ホストが返す実際のモードを確認し、`fullscreen` の場合だけビュアーを表示してファイルを読み込む。拒否時はカードにエラーを表示する。
- `app.onhostcontextchanged` によって元の`inline`に戻ったらビューを隠し、ファイル名カードを再表示する。
- `file_viewer_open(path)` が渡したパスは読み込み前でもカードへ表示される。`file_manager_panel()` のようにパスが未指定なら「HPC File Browser」を表示する。
- 従来のv28は `ui://mcp-file-manager/v28/app.html` に元のHTMLとfullscreen推奨メタデータを残す。その他の古いUIのURIと内容も変更しない。

## ホスト依存の制限

ChatGPTが描画するネイティブの「HPC MCP (ohtaka)で開く」ボタンのラベルはMCPアプリから上書きできる保証がない。v29のファイル名表示は **MCPアプリのinlineカード自身** で実現する。iPhone版ChatGPTがinlineカードを描画する前にネイティブボタンだけを表示する場合、ファイル名カードはそのボタンを押した後に表示される可能性がある。

全画面化はホスト側で拒否され得る。アプリはホストの `availableDisplayModes` を確認し、対応しない場合にはユーザーへ通知して無理にサイズを拡大しない。

## 非変更範囲・安全性

- PDF.js、PNG/JPEG/GIF/WebP、Markdown、数式、UTF-8ファイル・コード表示、編集・Git Historyの処理はv28と同じ。
- Upload/Downloadの許可、HPC-MCP設定、Slurm、oneAPI、GitHub、ユーザー所有サービスには変更なし。
- 新規のHTTPSサービス・SSHトンネル・外部リンク・外部ブラウザは不要。
- メタデータやUIの更新は新URIと新HTMLだけに限定し、既存v28を不変に保つ。

## テスト

- TypeScript: `npm run check`
- ランチャー: `npm run test:launch`（日本語ファイル名、PNG/PDF/Markdown/テキスト、ホスト識別、DOMと表示イベント配線）
- 既存回帰: `npm run test:math`、`npm run test:image`、`npm run test:pdf`
- Python: `tests/test_phase23_compact_launch.py` を含む既存pytestスイート
- ビルド: `npm run build` で生成した `frontend/dist/index.html` が `ui/app_v29.html` とバイト一致
- sham・ohtakaのv29 HTMLのSHA-256一致、v28 HTMLのSHA-256不変、バックアップの検証

**実機確認:** PC版ではv29のコンパクトカードと全画面表示がユーザー確認でPASS。iPhone版では`file_viewer_open`を1件のみ実行した場合の正常起動をユーザー確認でPASS。iOSネイティブボタンの文言はホスト依存であり、iOSでの全画面遷移・復帰は独立確認が未完了。
