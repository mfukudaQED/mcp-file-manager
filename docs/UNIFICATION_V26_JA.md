# MCP File Manager UI v26 統合仕様・配布前監査

日付: 2026-11-12（JST）

状態: **UI v26当時の設計・検証記録**（最新版はUI v29・パッケージv0.4.0）

Git基準: `63ed240` (`v0.3.0`)

次期パッケージ候補: `v0.4.0`（パッケージ定義は更新済み。コミット・タグ未作成）

## 目的と原則

shamとohtakaのFile Managerを単一のGitHubリポジトリ `mfukudaQED/mcp-file-manager` で管理し、UI v26の**配布バイナリを完全同一**にする。TabbyプロファイルとWinSCPサイトだけを、HPC-MCPのサービス設定を変更せずホストごとに決定する。従来の編集、Git History、折りたたみUI、Markdown/MathML、初回1000行自動読み込み、明示的なLoad moreなどは維持する。

## ディレクトリ

- sham: `<user-owned-workdir>/mcp-file-manager`
- ohtaka: `<user-owned-workdir>/projects/mcp-file-manager`
- バックアップ: 各リポジトリの `.integration_preserve_20261112/MANIFEST.json`。変更前の未コミット・未追跡ファイルの元SHA-256とコピーを含む。ohtakaの既存 `.math_v25_backups_20261110/` は手を触れない。

## 実装

- `src/mcp_file_viewer/ui/app_v26.html`: 両ホストで同一バイトのオフライン単一HTMLバンドル。
- `frontend/index.html`: v26を生成する共通テンプレート。従来の `sham`/`ohtaka` 固定値を `__MCPFM_V26_TABBY_PROFILE__` と `__MCPFM_V26_WINSCP_SITE__` に分離。
- `src/mcp_file_viewer/host_defaults.py`: ホスト名を短縮し、`sham`、`ohtaka.example.org` などから既定プロファイルを解決。環境変数 `MCP_FILE_MANAGER_TABBY_PROFILE` と `MCP_FILE_MANAGER_WINSCP_SITE` で個別に上書き可能。サービス側設定の変更は不要。
- `src/mcp_file_viewer/extension.py`: v26リソースを返す際だけ、HTML属性エスケープ済みのプロファイル名とサイト名を挿入。入力長は1–128文字で制限し、制御文字を拒否。従来のツール・パス許可ポリシーは変更しない。
- `ui://mcp-file-manager/v26/app.html` が**当時の**リソースURI。現在はUI v29。新URIによって旧ChatGPT UIキャッシュとの衝突を避ける。

## 後方互換性の扱い

- v16–v23: 既存配布バンドルを変更しない。
- v24: sham版は `app_v24.html`（数式対応、元SHA `bbafb0e63a33e1cff371152da12a2643b30e63f8b3c59a39075942fc6274447a`）、ohtaka版は `app_v24_ohtaka.html`（元SHA `723af3eb851154df5b9f52f62d2cca0f8e9a2ce339308429c2fd155fe3b310d7`）。旧URIには実行中ホストの元HTMLを返す。
- v25: ohtakaの数式対応版 `app_v25.html` を元SHA `2eb8ba099a3454d2df09a7020f84c5d9c44f0793914be22067edddfa76f52d1c` のまま保持。shamでも互換リソースとして登録。
- v26: リソース本体は共通。配信時に2属性値だけを注入するので、返されるHTML全体のSHAはホスト別に異なりうるが、*配布されたテンプレートのSHA*は同一。

## 固定SHA-256と検証

| ファイル | SHA-256 |
|---|---|
| `app_v26.html` | `1ab4138a7ba927cde208d56de4466b82d600f8f314330264d460c77cddf86854` |
| `frontend/index.html` | `037639e15557c1c9cf252fb640b5ab6b6114dce47610b4062819062f51f96dc9` |
| `extension.py` | `32e3bf43bc31468980c039fdafe2c8f314942bfd39a068f5944a34305e488e1b` |
| `host_defaults.py` | `cc1f5f8237fbae002b8b9419ba46d3c5888270b592db176cbce4f0728cdff318` |

shamで `python_venv -m pytest -q` は **67 passed**。`npm run check` と `npm run test:math` もPASS。`npm run build` で生成された `frontend/dist/index.html` と `app_v26.html` はバイト一致。ohtakaでは同一SHAの静的整合性を確認済み。ただしMCP許可コマンドのPython 3.6にはpytestがなく、ohtakaでのテスト実行とChatGPT埋め込みブラウザ実表示は未検証。

## リリース作業（未実施）

1. バックアップと `git status` を監査し、個別環境の設定ファイルと `.integration_preserve_20261112/`、`.math_v25_backups_20261110/` はコミットしない。
2. 統合後の共通ファイルを選択してstageする。`git add -A` は利用しない。
3. ohtakaでPython 3.10以降の**承認済み実行環境**を利用可能にした後、回帰テストを実行する。
4. `pyproject.toml` の版は両ホストで `0.4.0` に更新済み。ohtakaの実行テストと配布前承認後にのみ、Git commit、tag、pushをユーザーが別途指示する。
5. その後、通常の手順でHPC-MCPユーザーサービスを再起動し、ChatGPTコネクタを再読込してUI実機確認する。

**今回実施しなかった操作:** サービス再起動、GitHubへのpush、Slurm操作、HPC-MCPの許可設定・systemd・cron・Intel oneAPIなどのHPC環境変更。
