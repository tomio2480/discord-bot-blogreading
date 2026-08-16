# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ドキュメントの文体

- `README.md` と `GOOGLE_SHEETS_SETUP.md` は利用者向けの手引きのため「ですます調」で書く．他はである調．

## 開発コマンド

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# Bot の起動
python bot.py

# テスト（TDD: 実装前にテストを書く）
python -m pytest -q

# 環境変数の設定（初回のみ）
cp .env.example .env
# .env を編集して DISCORD_TOKEN, DISCORD_CHANNEL_ID, HACKMD_API_TOKEN を設定
```

## アーキテクチャ

### 全体構成

- **bot.py**: メインファイル．Discord Bot・スケジューラ・HackMD API・Google Sheets・connpass RSS を統合
- **Google Sheets**: HackMD と connpass の URL の正本（環境変数 `GOOGLE_SHEETS_*` 設定時）
- **data.json**: ローカルキャッシュ（Git 管理外）．Sheets 未設定時は唯一の保存先
- **APScheduler**: JST タイムゾーンで月曜日のスケジュールを管理
- **tests/test_bot.py**: pytest．`feedparser` はモック化して関数単体を検証

### 主要コンポーネント

1. **スケジューラ**: APScheduler で JST 月曜日の 6 つの時刻に自動投稿．connpass RSS を 10 分間隔で確認
2. **スラッシュコマンド**: `/ls`・`/announce`・`/set_connpass`・`/set_hackmd`・`/check_time`
   - tomio2480 のみ許可し，ephemeral で他人に非表示
3. **HackMD 連携**: `create_hackmd_note()` で次週用メモを自動作成
4. **データ永続化**: `load_data()` / `save_data()`．Sheets の読み書きは 3 回再試行し，失敗時はキャッシュへ倒す
   - 読み込みに失敗しキャッシュも無ければ `None` を返す．他の呼び出し側は既定値で上書き保存しない
   - 例外は 18:30 の投稿後で，読み込みの成否によらず両リンクを消す（19:00 の新規作成に備えた意図的な消去）
   - Sheets 保存が失敗したら `data.json` へ `_unsynced` を付け，次回読み込み時に再同期する
   - Sheets 書き込みは行位置固定（2 行目 hackmd，3 行目 connpass）の部分更新
   - 非同期処理からは `aload_data` / `asave_data`（`asyncio.to_thread`）経由で呼ぶ
   - 再試行の待機中もイベントループは止まらない
   - 呼び出し側は変更した項目だけを `save_data` へ渡す．辞書全体を渡すと同時実行で相手の更新を戻す
   - `load_data` / `save_data` は `threading.RLock` で直列化する．複数スレッドから同時に呼ばれるため

### 重要な実装詳細

- `get_next_monday()`: 次の月曜日を計算（JST 基準）
- 日付フォーマット: `%Y`=4桁年, `%m`=2桁月, `%d`=2桁日
- HackMD 権限: `readPermission` と `writePermission` を `signed_in` に設定
- スケジュール時刻のズレは ±1 分程度を許容
- リンクを含む投稿・応答は `suppress_embeds=True` で埋め込みを抑止
- ストレージへアクセスするスラッシュコマンドは先に `defer` し，`followup` で応答（3 秒制限対策）

### ホスティング

Northflank を推奨（無料枠で常時起動可能）．
Docker でデプロイ．Vercel 等の Serverless 環境は不可（常時接続が必要なため）．

### Docker 構成

- **Dockerfile**: Python 3.11 slim ベース
- **データ永続化の注意**: `data.json` は再起動で消えるため，Google Sheets の設定を前提とする（`GOOGLE_SHEETS_SETUP.md`）

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