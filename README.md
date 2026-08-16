# Discord Bot - ブログ読み会自動投稿

<!-- 本ファイルは利用者向けの手引きのため「ですます調」で書く．この 1 ルールだけ無効化する． -->
<!-- textlint-disable ja-technical-writing/no-mix-dearu-desumasu -->

Discord サーバー「とみおハウス」で動作する，テックブログ一気読み選手権の自動投稿 Bot．

## 機能

- 月曜日の指定時刻に自動投稿
  - 08:00: 開始通知
  - 18:15: リマインダー
  - 18:30: ブログリンク集の投稿
  - 18:38: 感想記入の促し
  - 18:42: 画面共有準備の促し
  - 19:00: 次週用 HackMD 作成と投稿
  - リンク付き投稿はリンクプレビュー（埋め込み）を抑止して送信
- connpass RSS 自動取得（10 分間隔）
  - connpass URL が未設定なら，RSS から次の月曜日のイベントを自動検出
  - 検出時はスプレッドシートへ保存し，Discord に自動投稿
- スラッシュコマンド
  - `/ls` で次の月曜日の日付と設定されているリンクを表示
  - `/announce` で次回の月曜日の情報をチャンネルに投稿
  - `/set_connpass url:` で connpass リンクを設定
  - `/set_hackmd url:` で HackMD リンクを設定
  - `/check_time` で現在時刻とタイムゾーンを確認
  - コマンドと応答は実行者のみへ表示（他のユーザーには見えません）
  - コマンドは tomio2480 のみ実行可能

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example` を `.env` にコピーします．以下を設定します．

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

Discord で開発者モードを有効化します．
`#blogreading` チャンネルの右クリックメニューから ID をコピーします．

### 5. HackMD API トークンの取得

1. [HackMD Settings](https://hackmd.io/settings) にアクセス
2. API タブでトークンを生成
3. トークンを `.env` に設定

### 6. Google Sheets データ保存の設定（推奨）

Bot の再起動後もデータを保持したい場合は，Google Sheets によるデータ保存を推奨します．

詳細な手順は [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md) を参照してください．

**メリット:**
- Bot 再起動後もデータが保持される
- Web ブラウザで直接データを確認・編集可能
- 完全無料

**設定しない場合:**
- Northflank での再起動時にデータが消えます
- `/set_connpass` と `/set_hackmd` で設定したリンクが失われます

## 実行

```bash
python bot.py
```

## 使い方

Bot の起動後は，スラッシュコマンドが利用可能になります．

1. Discord で `/set_connpass` または `/set_hackmd` を入力
2. `url:` パラメータに URL を入力
3. 入力内容と応答は自分にのみ表示されます

## Northflank へのデプロイ（推奨）

Northflank の無料枠は常時起動が可能で，Discord bot に最適です．

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
   - "Environment" タブで以下を追加します．
     - `DISCORD_TOKEN`: Discord Bot トークン
     - `DISCORD_CHANNEL_ID`: チャンネル ID
     - `HACKMD_API_TOKEN`: HackMD API トークン

5. **デプロイ**
   - "Deploy" をクリック
   - ログで起動を確認

### データ永続化の注意

Northflank では再起動時にファイルが消えます．`data.json` は揮発性です．
[Google Sheets データ保存](#6-google-sheets-データ保存の設定推奨) を設定してください．
設定時は Google Sheets を正とし，`data.json` は障害時のキャッシュに使います．
詳細は [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md) の「フォールバック機能」を参照してください．

## 技術スタック

- Python 3.x
- discord.py
- APScheduler（JST スケジューリング）
- HackMD API
- feedparser（RSS 解析）
- gspread（Google Sheets 連携）
