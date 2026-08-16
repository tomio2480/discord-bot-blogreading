# Discord Bot - ブログ読み会自動投稿

Discord サーバー「とみおハウス」で動作する，テックブログ一気読み選手権の自動投稿 Bot．

## 機能

- 月曜日の指定時刻に自動投稿
  - 08:00: 開始通知
  - 18:15: リマインダー
  - 18:30: ブログリンク集の投稿
  - 18:38: 感想記入の促し
  - 18:42: 画面共有準備の促し
  - 19:00: 次週用 HackMD 作成と投稿
  - リンクを含む投稿はリンクプレビュー（埋め込み）を抑止して送信
- connpass RSS 自動取得（10分間隔）
  - connpass URL が未設定の場合、RSS から次の月曜日のイベントを自動検出
  - 検出時はスプレッドシートに保存し、Discord に自動投稿
- スラッシュコマンド
  - `/ls` で次の月曜日の日付と設定されているリンクを表示
  - `/announce` で次回の月曜日の情報をチャンネルに投稿
  - `/set_connpass url:` で connpass リンクを設定
  - `/set_hackmd url:` で HackMD リンクを設定
  - `/check_time` で現在時刻とタイムゾーンを確認
  - コマンドと応答は実行者のみに表示（他のユーザーには見えません）
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
4. OAuth2 → URL Generator で以下を選択
   - スコープ: `bot` と `applications.commands`
   - Bot 権限: `Send Messages`
5. 生成された URL でサーバーに Bot を招待

### 4. チャンネル ID の取得

Discord で開発者モードを有効化し，`#blogreading` チャンネルを右クリックして ID をコピー．

### 5. HackMD API トークンの取得

1. [HackMD Settings](https://hackmd.io/settings) にアクセス
2. API タブでトークンを生成
3. トークンを `.env` に設定

### 6. Google Sheets データ保存の設定（推奨）

Bot の再起動後もデータを保持するため、Google Sheets を使用したデータ保存を推奨します。

詳細な手順は [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md) を参照してください。

**メリット：**
- Bot 再起動後もデータが保持される
- Web ブラウザで直接データを確認・編集可能
- 完全無料

**設定しない場合：**
- Northflank での再起動時にデータが消えます
- `/set_connpass` と `/set_hackmd` で設定したリンクが失われます

## 実行

```bash
python bot.py
```

## 使い方

Bot が起動すると，スラッシュコマンドが利用可能になります。

1. Discord で `/set_connpass` または `/set_hackmd` を入力
2. `url:` パラメータに URL を入力
3. 入力内容と応答は自分にのみ表示されます

## Northflank へのデプロイ（推奨）

Northflank の無料枠では常時起動が可能で，Discord bot に最適です。

### 前提条件

- GitHub アカウント
- Northflank アカウント（[northflank.com](https://northflank.com) で無料登録）

### デプロイ手順

1. **GitHub リポジトリの作成**
   ```bash
   # GitHub で新規リポジトリを作成後
   git remote add origin https://github.com/yourusername/discord-bot-blogreading.git
   git push -u origin main
   ```

2. **Northflank でプロジェクト作成**
   - [Northflank](https://app.northflank.com) にログイン
   - "Create Project" をクリック
   - プロジェクト名を入力

3. **サービスの作成**
   - "Add Service" → "Combined service"
   - GitHub リポジトリを選択
   - Build type: "Dockerfile"
   - Port: 設定不要（Discord bot は HTTP サーバーではないため）

4. **環境変数の設定**
   - "Environment" タブで以下を追加：
     - `DISCORD_TOKEN`: Discord Bot トークン
     - `DISCORD_CHANNEL_ID`: チャンネル ID
     - `HACKMD_API_TOKEN`: HackMD API トークン

5. **デプロイ**
   - "Deploy" をクリック
   - ログで起動を確認

### データ永続化の注意

Northflank では再起動時にファイルが消えます。`data.json` は揮発性です。
長期的には外部データベース（MongoDB Atlas 無料枠等）の使用を推奨します。

## 技術スタック

- Python 3.x
- discord.py
- APScheduler（JST スケジューリング）
- HackMD API
- feedparser（RSS 解析）
- gspread（Google Sheets 連携）
