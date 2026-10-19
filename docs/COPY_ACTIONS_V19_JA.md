# MCP File Manager UI v19: Copy path / Tabby / WinSCP

## 概要

UI v18 の Open in Tabby は ChatGPT ホスト経由で外部 URL を起動できなかった。UI v19 では URL を直接起動せず、コピーする方式に変更する。

上部ツールバーに小さなボタンを配置した。ツールチップとアクセシブル名で機能を識別できる。

| ボタン | 入力 | コピーされる内容 |
|---|---|---|
| Path（file-copy SVG） | Path | 選択中の絶対Linuxパスをそのまま |
| Tabby（square-terminal SVG） | Tabby | 登録済みプロファイル用 tabby://profile?profileName=... |
| WinSCP（folders SVG） | WinSCP | 保存済みサイト名 / ホスト名を用いた winscp-sftp://... |

## 例

Path = /home/user/work/project/README.md、Tabby = sham、WinSCP = sham の場合:

- **Path:** /home/user/work/project/README.md
- **Tabby:** tabby://profile?profileName=sham
- **WinSCP:** winscp-sftp://sham/home/user/work/project/

WinSCP はファイル指定のURLを開くとダウンロードになるため、**現在開いているファイルの親ディレクトリ**を使用し、URL末尾に必ずスラッシュを付ける。

WinSCP のサイト名は Tabby のプロファイル名とは独立して変更できる。初期値はどちらも sham だが、必ず各アプリに設定済みの名称（またはWinSCPから接続可能なホスト名）に合わせること。WinSCP URL は保存済みサイトの設定（認証、ホストキー等）を利用することを想定しており、認証情報を埋め込まない。

## コピーができない場合

MCP Apps iframe に対する clipboard-write 権限の要求を v19 リソースのメタデータに追加した。ただし、ホストの権限ポリシーによって navigator.clipboard.writeText が失敗する可能性がある。

その場合はコピーする文字列を選択状態のテキストエリアに表示するので、Windows では **Ctrl+C**、macOSでは **⌘+C** で手動コピーする。自動コピーに成功していない場合、UI は「copied」と表示しない。選択表示が不要なら Close を押す。

コピー後は Windows で Win + R を開き、Tabby または WinSCP 用 URL を貼り付けて起動する。Windows の URL ハンドラーに WinSCP が登録されている必要がある。WinSCP 側の登録方法は公式ドキュメント https://winscp.net/eng/docs/integration_url を参照。

## バージョン互換性と変更禁止事項

- UI v16/v17/v18 の HTML リソースは**変更せず**そのまま登録する。
- UI v19 は ui://mcp-file-manager/v19/app.html の独立したリソースを使用する。
- Download / Upload ボタンは復活させない。既存の転送用バックエンドは変更しない（無効のまま）。
- 既存の閲覧、編集、Git History、Slurm、Intel oneAPI、systemd 設定は変更しない。
- 今回は GitHub push およびサービス再起動を実施しない。

## 検証

- フロントエンドの型チェック、Node テスト（WinSCP末尾スラッシュ・URLエンコードを含む）、Vite ビルド。
- Python / MCP リソーステスト（v16〜v19、メタデータ、既存機能）。
- 本文の検証はv19実装当時の結果。最新v21はSVG表示とコピー操作を引き継ぐ。クリップボードやデスクトップ起動の動作は利用中のChatGPTホストとOSに依存する。
