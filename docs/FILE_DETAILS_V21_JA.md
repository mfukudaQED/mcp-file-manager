# MCP File Manager UI v21: ファイル情報の折りたたみ

## 変更内容

ファイルを開いたときのタイトル・絶対パス・サイズ・読み込み範囲・読み取り専用状態を表示するヘッダー（例：`README.md`）を、**初期状態で非表示**にした。

- ファイルビューのアクションバーに、単色の情報アイコン `ⓘ`（`file-details-toggle`）を追加。
- クリックするとヘッダー `file-details` が開閉する。ツールチップは `Show file details` / `Hide file details` に切り替わる。
- `aria-expanded` と `aria-controls` を更新し、キーボード操作も通常のボタンで対応。
- ヘッダーのファイル名・絶対パス・メタデータを更新する既存JavaScript処理は保持。閉じたままファイルを切り替えても、展開時は現在のファイルの情報を表示できる。
- 表示状態はUIインスタンス内で維持する。ファイルを開き直すたびに強制的に変更しない。
- Status/diagnosticsの折りたたみ、SVGアイコンのホバーツールチップ、Copy Path/Tabby/WinSCP、編集・Git Historyは変更しない。
- 旧リソース（v16〜v20）のHTMLは変更しない。新規リソースURIは `ui://mcp-file-manager/v21/app.html`。

## 検証と適用

- TypeScript型チェック、Nodeフロントエンドテスト、Vite単一HTMLビルド、Python統合テストを実施済み。
- GitHub push、サービス再起動、Slurm・Intel oneAPI・既存systemd設定の変更は実施しない。
- UI v21のファイル情報の展開・折りたたみはユーザーがChatGPT上で動作を確認済み（2026-10-19）。
