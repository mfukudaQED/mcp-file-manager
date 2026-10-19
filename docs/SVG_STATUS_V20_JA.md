# MCP File Manager UI v20 — SVGアイコン・折りたたみ式Status

## 変更概要

- ユーザー選択の**案B**に従ってコピー操作は用途別の単色SVG＋短いラベルにした。
  - **Path**: file-copy（ファイル複製）
  - **Tabby**: square-terminal（ターミナル）
  - **WinSCP**: folders（フォルダ）
- Explorerの開閉、ファイルを開く、Folder、Reload、Log tail、Previous/Next、検索、Source/Preview、Edit、Save、Cancel、Diff、Git Historyなどの通常アクションボタンはSVGの**アイコンのみ**にした。
- ツールチップ（`title`）と支援技術向け説明（`aria-label`）は保持。表示は既存UIに合わせて16〜17px、currentColor、1.75pxストローク、8px角丸。
- 動的に生成されるGit履歴操作、ファイルツリーの開閉、タブのCloseもSVG化（ファイル名とGitの説明文は引き続き表示）。
- ライト・ダークモードの双方で単色アイコンが反映される。外部CDNや画像ファイルは不要で、SVGの`symbol`をHTMLに内包する。
- **Status / diagnostics / performance metrics / connection benchmark**を`status-panel`にまとめ、**デフォルト非表示**にした。画面右上のアクティビティSVGから開閉する（初期`aria-expanded=false`）。
- エラー時は開閉アイコンにエラー色を付ける。閉じた状態でもエラーの存在を示す。
- コピー成功時、該当ボタンのSVGを約1.5秒チェックに切り替える。クリップボード拒否時の手動コピー欄はStatusが閉じていても表示される。

## 対応する既存機能

- コピー内容・URL生成（Path、Tabby、WinSCP）を変更しない。
- v16/v17/v18/v19を独立したUIリソースとして保持。v20は`ui://mcp-file-manager/v20/app.html`。
- Download / Uploadは非表示のままで、関連バックエンドは変更しない。
- 閲覧・編集・Git History・差分比較を維持する。
- Slurm、Intel oneAPI、systemd設定に変更なし。

## 検証と未実施事項

フロントエンドTypeScriptチェック、JSテスト、Vite単一HTMLビルド、MCP登録・互換性のPythonテストを実施。古いUI HTMLのハッシュの不変性を確認。

これはUI v20実装時の検証記録。現行UIはv21で、SVGアイコン・Statusの初期非表示・ツールチップを継承している。公開リポジトリへのコミット・GitHub pushは別途実施する。

## アイコンのホバー説明（v20追加）

アイコンボタンへマウスを重ねると、ブラウザ標準の title 表示に依存しない小さなツールチップが現れる。Tabby/WinSCP/Pathのコピー操作、Explorer、Open、Edit、Save、Git History、ファイルツリーの展開、タブClose等に対応。

- キーボードのフォーカスでも表示。支援技術向け aria-label を表示名に使用。
- 位置は固定座標で計算し、スクロール領域で切り取られないようにする。画面端では位置を自動調整する。
- マウスが離れる・クリックする・スクロールする・Escを押す・ウィンドウサイズを変更すると閉じる。
- 無効なボタンも意味を確認できるよう、マウスの位置から対象アイコンを検出する。
- 画面外部から画像・CSSなどを取得しない。v16〜v19は変更しない。

ブラウザ上での実機ホバー操作は、サービス反映後に別途確認する。
