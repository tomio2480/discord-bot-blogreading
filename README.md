# Discord Bot - ブログ読み会自動投稿

Discord サーバー「とみおハウス」で動作する，テックブログ一気読み選手権の自動投稿 Bot．

## 機能

- 月曜日の指定時刻に自動投稿
  - 08:00: 開始通知
  - 18:15: リマインダー
  - 18:30: ブログリンク集の投稿
  - 19:00: 次週用 HackMD 作成と投稿
- `set connpass [URL]` で connpass リンクを設定
- `set hackmd [URL]` で HackMD リンクを設定
- コマンドは tomio2480 のみ実行可能

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example` をコピーして `.env` を作成し，以下を設定：

```
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
HACKMD_API_TOKEN=your_hackmd_api_token_here
```

### 3. Discord Bot の作成

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリケーション作成
2. Bot タブで Bot を追加
3. TOKEN をコピーして `.env` に設定
4. Privileged Gateway Intents で `MESSAGE CONTENT INTENT` を有効化
5. OAuth2 → URL Generator で `bot` スコープと `Send Messages` 権限を選択
6. 生成された URL でサーバーに Bot を招待

### 4. チャンネル ID の取得

Discord で開発者モードを有効化し，`#blogreading` チャンネルを右クリックして ID をコピー．

### 5. HackMD API トークンの取得

1. [HackMD Settings](https://hackmd.io/settings) にアクセス
2. API タブでトークンを生成
3. トークンを `.env` に設定

## 実行

```bash
python bot.py
```

## PythonAnywhere へのデプロイ

1. PythonAnywhere でアカウント作成
2. Files タブからファイルをアップロード
3. Consoles タブで Bash コンソールを開く
4. 依存パッケージをインストール
5. `.env` ファイルを作成して環境変数を設定
6. `python bot.py` で起動

## 技術スタック

- Python 3.x
- discord.py
- APScheduler（JST スケジューリング）
- HackMD API
