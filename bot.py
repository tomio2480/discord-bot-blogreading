import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import pytz
import os
import json
import re
import requests
import feedparser
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

# 環境変数の読み込み
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
HACKMD_API_TOKEN = os.getenv('HACKMD_API_TOKEN')
ALLOWED_USER = 'tomio2480'

# データファイル
DATA_FILE = 'data.json'

# 日本標準時
JST = pytz.timezone('Asia/Tokyo')

# Intentsの設定
intents = discord.Intents.default()

# Bot初期化
bot = commands.Bot(command_prefix='!', intents=intents)
scheduler = AsyncIOScheduler(timezone=JST)

# Google Sheets接続
def get_sheets_client():
    """Google Sheetsクライアントを取得"""
    try:
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            return None
        
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return gspread.authorize(creds)
    except Exception as e:
        print(f'Google Sheetsクライアント取得エラー: {e}')
        return None

def get_worksheet():
    """ワークシートを取得"""
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        if not spreadsheet_id:
            return None
        
        spreadsheet = client.open_by_key(spreadsheet_id)
        return spreadsheet.sheet1
    except Exception as e:
        print(f'ワークシート取得エラー: {e}')
        return None

# データ管理
def load_data():
    """Google Sheetsまたはローカルファイルからデータを読み込み"""
    try:
        worksheet = get_worksheet()
        if worksheet:
            # Google Sheetsから全データを取得
            records = worksheet.get_all_records()
            data = {}
            for record in records:
                key = record.get('キー') or record.get('key')
                value = record.get('値') or record.get('value')
                if key:
                    data[key] = value
            
            print(f'Google Sheetsからデータを読み込みました: {data}')
            return data if data else {'hackmd': None, 'connpass': None}
    except Exception as e:
        print(f'Google Sheetsからのデータ読み込みエラー: {e}')
    
    # Google Sheets未設定またはエラー時はローカルファイルを使用
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'hackmd': None, 'connpass': None}

def save_data(data):
    """Google Sheetsまたはローカルファイルにデータを保存"""
    try:
        worksheet = get_worksheet()
        if worksheet:
            # 既存データをクリア
            worksheet.clear()
            
            # ヘッダーを設定
            worksheet.update('A1:B1', [['キー', '値']])
            
            # データを書き込み
            rows = [[key, value if value else ''] for key, value in data.items()]
            if rows:
                worksheet.update(f'A2:B{len(rows)+1}', rows)
            
            print(f'Google Sheetsにデータを保存しました: {data}')
            return
    except Exception as e:
        print(f'Google Sheetsへのデータ保存エラー: {e}')
    
    # Google Sheets未設定またはエラー時はローカルファイルを使用
    os.makedirs(os.path.dirname(DATA_FILE) if os.path.dirname(DATA_FILE) else '.', exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'ローカルファイルにデータを保存しました: {data}')

def get_next_monday():
    """次の月曜日の日付を取得"""
    now = datetime.now(JST)
    days_ahead = 7 - now.weekday() if now.weekday() != 0 else 7
    next_monday = now + timedelta(days=days_ahead)
    return next_monday

# HackMD API関連
def get_hackmd_template():
    """テンプレートの内容を取得"""
    template_id = 'Ocjjk_IDTDyi9tS76ARjbw'
    url = f'https://api.hackmd.io/v1/notes/{template_id}'
    headers = {
        'Authorization': f'Bearer {HACKMD_API_TOKEN}',
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('content', '')
    return None

def create_hackmd_note(title, alias, content=''):
    """HackMDのテンプレートから新規メモを作成"""
    url = 'https://api.hackmd.io/v1/notes'
    headers = {
        'Authorization': f'Bearer {HACKMD_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        'title': title,
        'content': content,
        'readPermission': 'signed_in',
        'writePermission': 'signed_in',
        'commentPermission': 'everyone',
        'permalink': alias
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        note_id = response.json()['id']
        # コンテンツが設定されていない場合、PATCHで更新を試みる
        if content and response.json().get('content') != content:
            patch_url = f'https://api.hackmd.io/v1/notes/{note_id}'
            patch_payload = {'content': content}
            requests.patch(patch_url, json=patch_payload, headers=headers)
        return f'https://hackmd.io/@tomio2480/{alias}'
    return None

# スケジュールされた投稿
async def post_morning():
    """月曜 08:00 (JST) の投稿"""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send('📢 今日はブログを読む日です')

async def post_reminder():
    """月曜 18:15 (JST) の投稿"""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send('👀 テックブログ一気読み選手権まであと少し')

async def post_start():
    """月曜 18:30 (JST) の投稿"""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        data = load_data()
        now = datetime.now(JST)
        date_str = now.strftime('%m/%d(月)')

        hackmd_text = data.get('hackmd') or '（HackMD 未設定）'
        connpass_text = data.get('connpass') or '（connpass 未設定）'

        message = f"""{date_str}
{hackmd_text}
{connpass_text}

18:38 くらいまでここから選んで読みましょう
https://yamadashy.github.io/tech-blog-rss-feed/
https://hatena.blog/dev
https://techplay.jp/blog"""

        await channel.send(message)
        
        # 投稿後にデータを削除（19:00の新規作成のため）
        data['hackmd'] = None
        data['connpass'] = None
        save_data(data)
        print('18:30投稿後にデータを削除しました')

async def post_writing_time():
    """月曜 18:38 (JST) の投稿"""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send('18:38 になりました\n感想を書きましょう')

async def post_sharing_reminder():
    """月曜 18:42 (JST) の投稿"""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send('そろそろ感想を共有します\n画面共有の準備をしてください')

async def post_create_hackmd():
    """月曜 19:00 (JST) の投稿（HackMD作成）"""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        # 次の月曜日の日付を取得
        next_monday = get_next_monday()

        # yyyy=4桁年, MM=2桁月, dd=2桁日
        title = next_monday.strftime('テックブログ一気読み選手権 %Y%m%d 杯')
        alias = next_monday.strftime('blogread_%Y%m%d')

        # テンプレート内容を取得
        template_content = get_hackmd_template()
        if template_content is None:
            template_content = ''  # テンプレート取得失敗時は空文字

        # タイトルを content の先頭に追加（HackMD はドキュメント内の # 見出しをタイトルとして表示）
        content_with_title = f'# {title}\n\n{template_content}'

        hackmd_url = create_hackmd_note(title, alias, content_with_title)

        # データ保存
        if hackmd_url:
            data = load_data()
            data['hackmd'] = hackmd_url
            save_data(data)

        # 投稿
        date_str = next_monday.strftime('%m/%d (月)')
        hackmd_text = hackmd_url or '（HackMD作成失敗）'

        message = f"""{date_str} 分
{hackmd_text}
※ connpass のリンクが未設定の場合は，set コマンドで connpass のリンクを設定してください．"""

        await channel.send(message)

# connpass RSS 自動取得
CONNPASS_RSS_URL = 'https://blogreading.connpass.com/ja.atom'

def get_next_monday_date_str():
    """次の月曜日の日付文字列（yyyyMMdd形式）を取得"""
    next_monday = get_next_monday()
    return next_monday.strftime('%Y%m%d')

def check_connpass_rss():
    """connpass RSS から次の月曜日のイベントを探す"""
    try:
        feed = feedparser.parse(CONNPASS_RSS_URL)
        if not feed.entries:
            return None

        next_monday_str = get_next_monday_date_str()
        pattern = rf'テックブログ一気読み選手権{next_monday_str}杯'

        for entry in feed.entries:
            title = entry.get('title', '')
            if re.search(pattern, title):
                return entry.get('link')
        return None
    except Exception as e:
        print(f'connpass RSS 取得エラー: {e}')
        return None

async def check_and_post_connpass():
    """connpass URL が未設定の場合、RSS をチェックして自動投稿"""
    data = load_data()

    # connpass URL が設定済みの場合はスキップ
    if data.get('connpass'):
        return

    # RSS から次の月曜日のイベントを探す
    connpass_url = check_connpass_rss()
    if not connpass_url:
        return

    # connpass URL を保存
    data['connpass'] = connpass_url
    save_data(data)
    print(f'connpass URL を自動設定しました: {connpass_url}')

    # /announce と同じ内容を投稿
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        hackmd_url = data.get('hackmd')
        if hackmd_url:
            next_monday = get_next_monday()
            date_str = next_monday.strftime('%m/%d(月)')
            message = f"""次回 {date_str} 分
{hackmd_url}
{connpass_url}"""
            await channel.send(message)
            print('connpass 自動取得による投稿を行いました')

# スラッシュコマンド
@bot.tree.command(name="ls", description="次の月曜日の日付と設定されているリンクを表示します")
async def ls(interaction: discord.Interaction):
    # tomio2480 のみ実行可能
    if interaction.user.name != ALLOWED_USER:
        await interaction.response.send_message('❌ このコマンドを実行する権限がありません', ephemeral=True)
        return

    # 次の月曜日の日付を取得
    next_monday = get_next_monday()
    date_str = next_monday.strftime('%m/%d (月)')

    # 現在の設定を読み込み
    data = load_data()
    hackmd_text = data.get('hackmd') or '（HackMD 未設定）'
    connpass_text = data.get('connpass') or '（connpass 未設定）'

    message = f"""次の月曜日: {date_str}
HackMD: {hackmd_text}
connpass: {connpass_text}"""

    await interaction.response.send_message(message, ephemeral=True)

@bot.tree.command(name="announce", description="次回の月曜日の情報をチャンネルに投稿します")
async def announce(interaction: discord.Interaction):
    # tomio2480 のみ実行可能
    if interaction.user.name != ALLOWED_USER:
        await interaction.response.send_message('❌ このコマンドを実行する権限がありません', ephemeral=True)
        return

    # 次の月曜日の日付を取得
    next_monday = get_next_monday()
    date_str = next_monday.strftime('%m/%d(月)')

    # 現在の設定を読み込み
    data = load_data()
    hackmd_url = data.get('hackmd')
    connpass_url = data.get('connpass')
    
    # URLが空の場合は警告を表示
    if not hackmd_url or not connpass_url:
        missing = []
        if not hackmd_url:
            missing.append('HackMD')
        if not connpass_url:
            missing.append('connpass')
        
        warning = f"⚠️ {' と '.join(missing)} の URL が設定されていません。\n先に `/set_hackmd` と `/set_connpass` で URL を設定してください。"
        await interaction.response.send_message(warning, ephemeral=True)
        return

    message = f"""次回 {date_str} 分
{hackmd_url}
{connpass_url}"""

    # チャンネルに投稿（ephemeralではない）
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(message)
        await interaction.response.send_message('✅ お知らせを投稿しました', ephemeral=True)
    else:
        await interaction.response.send_message('❌ チャンネルが見つかりません', ephemeral=True)

@bot.tree.command(name="set_connpass", description="connpass の URL を設定します")
@app_commands.describe(url="connpass イベントの URL")
async def set_connpass(interaction: discord.Interaction, url: str):
    # tomio2480 のみ実行可能
    if interaction.user.name != ALLOWED_USER:
        await interaction.response.send_message('❌ このコマンドを実行する権限がありません', ephemeral=True)
        return

    data = load_data()
    data['connpass'] = url
    save_data(data)
    await interaction.response.send_message(f'✅ connpass URL を設定しました: {url}', ephemeral=True)

@bot.tree.command(name="set_hackmd", description="HackMD の URL を設定します")
@app_commands.describe(url="HackMD メモの URL")
async def set_hackmd(interaction: discord.Interaction, url: str):
    # tomio2480 のみ実行可能
    if interaction.user.name != ALLOWED_USER:
        await interaction.response.send_message('❌ このコマンドを実行する権限がありません', ephemeral=True)
        return

    data = load_data()
    data['hackmd'] = url
    save_data(data)
    await interaction.response.send_message(f'✅ HackMD URL を設定しました: {url}', ephemeral=True)

@bot.tree.command(name="check_time", description="現在時刻とタイムゾーンを確認します")
async def check_time(interaction: discord.Interaction):
    # tomio2480 のみ実行可能
    if interaction.user.name != ALLOWED_USER:
        await interaction.response.send_message('❌ このコマンドを実行する権限がありません', ephemeral=True)
        return

    import time
    
    # 現在時刻（JST）
    now_jst = datetime.now(JST)
    
    # システムのタイムゾーン
    system_tz = time.tzname
    
    # 環境変数TZ
    env_tz = os.getenv('TZ', '未設定')
    
    message = f"""⏰ タイムゾーン情報

**現在時刻（JST）:** {now_jst.strftime('%Y-%m-%d %H:%M:%S %Z')}
**システムタイムゾーン:** {system_tz}
**環境変数 TZ:** {env_tz}
**次の月曜日:** {get_next_monday().strftime('%Y-%m-%d (%a)')}

✅ JSTで正しく動作しています。"""

    await interaction.response.send_message(message, ephemeral=True)

# スケジューラ初期化フラグ
scheduler_started = False

@bot.event
async def on_ready():
    global scheduler_started
    print(f'{bot.user} でログインしました')

    # スラッシュコマンドを同期
    await bot.tree.sync()
    print('スラッシュコマンドを同期しました')

    # スケジューラは一度だけ設定（再接続時の二重登録を防止）
    if not scheduler_started:
        # スケジュール設定（月曜日のみ実行、すべてJST）
        scheduler.add_job(post_morning, CronTrigger(day_of_week='mon', hour=8, minute=0), id='post_morning')
        scheduler.add_job(post_reminder, CronTrigger(day_of_week='mon', hour=18, minute=15), id='post_reminder')
        scheduler.add_job(post_start, CronTrigger(day_of_week='mon', hour=18, minute=30), id='post_start')
        scheduler.add_job(post_writing_time, CronTrigger(day_of_week='mon', hour=18, minute=38), id='post_writing_time')
        scheduler.add_job(post_sharing_reminder, CronTrigger(day_of_week='mon', hour=18, minute=42), id='post_sharing_reminder')
        scheduler.add_job(post_create_hackmd, CronTrigger(day_of_week='mon', hour=19, minute=0), id='post_create_hackmd')

        # connpass RSS 自動取得（10分間隔）
        scheduler.add_job(check_and_post_connpass, IntervalTrigger(minutes=10), id='check_connpass_rss')

        scheduler.start()
        scheduler_started = True
        print('スケジューラーを起動しました（JST）')
    else:
        print('スケジューラーは既に起動済みです（再接続）')

if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
