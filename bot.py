import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import pytz
import os
import json
import requests
from dotenv import load_dotenv

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

# データ管理
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'hackmd': None, 'connpass': None}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
        return f'https://hackmd.io/{alias}'
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

        hackmd_url = create_hackmd_note(title, alias, template_content)

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

@bot.event
async def on_ready():
    print(f'{bot.user} でログインしました')

    # スラッシュコマンドを同期
    await bot.tree.sync()
    print('スラッシュコマンドを同期しました')

    # スケジュール設定（月曜日のみ実行、すべてJST）
    scheduler.add_job(post_morning, CronTrigger(day_of_week='mon', hour=8, minute=0))
    scheduler.add_job(post_reminder, CronTrigger(day_of_week='mon', hour=18, minute=15))
    scheduler.add_job(post_start, CronTrigger(day_of_week='mon', hour=18, minute=30))
    scheduler.add_job(post_writing_time, CronTrigger(day_of_week='mon', hour=18, minute=38))
    scheduler.add_job(post_sharing_reminder, CronTrigger(day_of_week='mon', hour=18, minute=42))
    scheduler.add_job(post_create_hackmd, CronTrigger(day_of_week='mon', hour=19, minute=0))

    scheduler.start()
    print('スケジューラーを起動しました（JST）')

if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
