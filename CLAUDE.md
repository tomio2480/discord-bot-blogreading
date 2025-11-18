# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 開発コマンド

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# Bot の起動
python bot.py

# 環境変数の設定（初回のみ）
cp .env.example .env
# .env を編集して DISCORD_TOKEN, DISCORD_CHANNEL_ID, HACKMD_API_TOKEN を設定
```

## アーキテクチャ

### 全体構成

- **bot.py**: メインファイル。Discord Bot, スケジューラ, HackMD API を統合
- **data.json**: HackMD と connpass の URL を永続化（Git 管理外）
- **APScheduler**: JST タイムゾーンで月曜日のスケジュールを管理

### 主要コンポーネント

1. **スケジューラ**: APScheduler で JST 月曜日の 4 つの時刻に自動投稿
2. **スラッシュコマンド**: `/set_connpass`, `/set_hackmd` を処理（tomio2480 のみ許可，ephemeral で他人に非表示）
3. **HackMD 連携**: `create_hackmd_note()` で次週用メモを自動作成
4. **データ永続化**: JSON ファイルで URL を保存

### 重要な実装詳細

- `get_next_monday()`: 次の月曜日を計算（JST 基準）
- 日付フォーマット: `%Y`=4桁年, `%m`=2桁月, `%d`=2桁日
- HackMD 権限: `readPermission` と `writePermission` を `signed_in` に設定
- スケジュール時刻のズレは ±1 分程度を許容

### ホスティング

Northflank を推奨（無料枠で常時起動可能）．
Docker でデプロイ．Vercel 等の Serverless 環境は不可（常時接続が必要なため）．

### Docker 構成

- **Dockerfile**: Python 3.11 slim ベース
- **データ永続化の注意**: `data.json` は再起動で消えるため，長期的には外部 DB を推奨

---

# 制作するもの
- Discord サーバ－「とみおハウス」で動作する Discord bot を作成する．
- 時刻に応じて以下の処理を行う．
  - 月曜 08:00 (JST) になったら「📢 今日はブログを読む日です」と #blogreading に投稿する．
  - 月曜 18:15 (JST) になったら「👀 テックブログ一気読み選手権まであと少し」と #blogreading に投稿する．
  - 月曜 18:30 (JST) になったら次のテキストを投稿する．
```
MM/dd(月)
（HackMD のリンク）
（connpass のリンク）
　
18:38 くらいまでここから選んで読みましょう
https://yamadashy.github.io/tech-blog-rss-feed/
https://hatena.blog/dev
https://techplay.jp/blog
```
    - ただし，MM/dd は投稿時点の現在月日を表示する．
    - ただし，（HackMD のリンク）と（connpass のリンク）はそれぞれ set されているものを出力する．
      - set されているものがなければ，それぞれ設定されていないものを「（HackMD 未設定）」「（connpass 未設定）」と表示する．
    - HackMD のリンクと connpass のリンクの set については，説明を後述する．
  - 月曜 19:00 (JST) になったら次の処理を行なう．
    - HackMD のテンプレート "blogreading" を元に HackMD メモを新規作成する．
      - このとき，メモの名前は「テックブログ一気読み選手権 yyyyMMdd 杯」とする．
        - また，yyyy は次の月曜日の西暦年，MM は次の月曜日の月，dd は次の月曜日の日付を埋め込む．
      - このとき，共有 URL の末尾は "blogread_yyyyMMdd" とする．
        - また，yyyy は次の月曜日の西暦年，MM は次の月曜日の月，dd は次の月曜日の日付を埋め込む．
        - URL 末尾例 : "blogread_20251124"
      - できあがった HackMD メモの共有用リンクを set hackmd で保管する．
        - なお，この処理の一連の流れで，ユーザーに明示せず，内部的に set hackmd と同様の動作をしてしまってよい．
  - 月曜 19:00 (JST) の処理が済んだら，以下のテキストを投稿する．
```
MM/DD (月) 分
（HackMD のリンク）
※ connpass のリンクが未設定の場合は，set コマンドで connpass のリンクを設定してください．
```
- 受け取ったコマンドに応じて以下の処理を行う．
  - set connpass [URL]
    - connpass の URL を受け取って，次に出力する際のデータとして保管しておく．
  - set hackmd [URL]
    - hackmd の URL を受け取って，次に出力する際のデータとして保管しておく．

# 動作環境と開発制約
- 無料でホストできるサービスを利用する．
- bot の動作時刻のズレは 1 分前後まで許容する．
- 使用する言語やフレームワークは問わない．
- コンパクトな作りになるように，コードは短くするように工夫する．