# Google Sheets データ保存セットアップガイド

このガイドでは、Google Sheets APIを使用してBotのデータを永続化する方法を説明します。

## 前提条件

- Googleアカウント
- Google Cloud Platformへのアクセス（無料）

## セットアップ手順

### 1. Google Cloud Platformでプロジェクトを作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 画面上部の「プロジェクトを選択」→「新しいプロジェクト」をクリック
3. プロジェクト名を入力（例：`discord-bot-blogreading`）
4. 「作成」をクリック

### 2. Google Sheets APIを有効化

1. 左側のメニューから「APIとサービス」→「ライブラリ」を選択
2. 検索ボックスに「Google Sheets API」と入力
3. 「Google Sheets API」をクリック
4. 「有効にする」をクリック

### 3. サービスアカウントを作成

1. 左側のメニューから「APIとサービス」→「認証情報」を選択
2. 「認証情報を作成」→「サービスアカウント」をクリック
3. サービスアカウント名を入力（例：`discord-bot`）
4. 「作成して続行」をクリック
5. ロールは選択せずに「続行」をクリック
6. 「完了」をクリック

### 4. サービスアカウントのキーを作成

1. 作成したサービスアカウントをクリック
2. 「キー」タブを選択
3. 「鍵を追加」→「新しい鍵を作成」をクリック
4. キーのタイプで「JSON」を選択
5. 「作成」をクリック
6. JSONファイルがダウンロードされます（**このファイルは安全に保管してください**）

### 5. Google Sheetsを作成

1. [Google Sheets](https://sheets.google.com/)にアクセス
2. 「空白」をクリックして新しいスプレッドシートを作成
3. スプレッドシート名を「ブログ読み会設定」に変更
4. 以下の形式でヘッダーを作成：

| キー | 値 |
|------|-----|

5. URLから**スプレッドシートID**をコピー
   - URL: `https://docs.google.com/spreadsheets/d/【ここがスプレッドシートID】/edit`
   - 例: `1a2b3c4d5e6f7g8h9i0j`

### 6. スプレッドシートを共有

1. 右上の「共有」ボタンをクリック
2. ダウンロードしたJSONファイルを開き、`client_email`の値をコピー
   - 例: `discord-bot@project-id.iam.gserviceaccount.com`
3. コピーしたメールアドレスを共有相手として追加
4. 権限を「編集者」に設定
5. 「送信」をクリック（通知メールは送信しなくてOK）

### 7. Northflankで環境変数を設定

1. [Northflankダッシュボード](https://app.northflank.com)にアクセス
2. プロジェクト → サービス → 「Environment」タブを選択
3. 以下の環境変数を追加：

#### GOOGLE_SHEETS_CREDENTIALS

- **名前**: `GOOGLE_SHEETS_CREDENTIALS`
- **値**: ダウンロードしたJSONファイルの**全内容**をコピー＆ペースト
  - JSONファイルをテキストエディタで開き、全文をコピー
  - 改行も含めてそのまま貼り付け

#### GOOGLE_SHEETS_SPREADSHEET_ID

- **名前**: `GOOGLE_SHEETS_SPREADSHEET_ID`
- **値**: 手順5でコピーしたスプレッドシートID

4. 「Save」をクリック
5. サービスが自動的に再起動されます

## 動作確認

1. Discordで `/set_connpass` コマンドを実行してURLを設定
2. Discordで `/set_hackmd` コマンドを実行してURLを設定
3. Google Sheetsを開いて、データが保存されていることを確認
4. Northflankでサービスを再起動
5. Discordで `/ls` コマンドを実行して、設定が保持されていることを確認

## トラブルシューティング

### データが保存されない

1. Northflankのログを確認
   - 「Google Sheetsにデータを保存しました」というメッセージが表示されているか
   - エラーメッセージが表示されていないか

2. 環境変数を確認
   - `GOOGLE_SHEETS_CREDENTIALS`が正しく設定されているか
   - `GOOGLE_SHEETS_SPREADSHEET_ID`が正しいか

3. スプレッドシートの共有設定を確認
   - サービスアカウントのメールアドレスが「編集者」として追加されているか

### エラーメッセージが表示される

- **「Google Sheetsクライアント取得エラー」**: 環境変数`GOOGLE_SHEETS_CREDENTIALS`が正しく設定されていません
- **「ワークシート取得エラー」**: スプレッドシートIDが間違っているか、共有設定が正しくありません
- **「Google Sheetsへのデータ保存エラー」**: サービスアカウントに編集権限がありません

## フォールバック機能

Google Sheets APIが利用できない場合（環境変数未設定、API制限など）は、自動的にローカルの`data.json`ファイルにフォールバックします。ただし、Northflankでは再起動時にローカルファイルが消えるため、Google Sheetsの設定を推奨します。

## API制限

Google Sheets APIの無料枠：
- 読み取り：100リクエスト/100秒/ユーザー
- 書き込み：100リクエスト/100秒/ユーザー

このBotの使用頻度では十分です。
