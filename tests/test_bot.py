"""
Discord Bot のテストコード

既存機能と新機能のすべてのテストを含む。
TDDアプローチで、テストを先に作成してから実装を行う。
"""

import pytest
import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, mock_open, MagicMock
import pytz

# テスト用の環境変数を設定（bot.py インポート前に必要）
os.environ.setdefault('DISCORD_TOKEN', 'test_token')
os.environ.setdefault('DISCORD_CHANNEL_ID', '123456789')
os.environ.setdefault('HACKMD_API_TOKEN', 'test_hackmd_token')

# discord.pyのインポートをモック化（Discord への接続を伴わずに関数単体を検証するため）
sys.modules['discord'] = MagicMock()
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['discord.app_commands'] = MagicMock()
sys.modules['feedparser'] = MagicMock()

# bot.pyをインポート
import bot


# ========================================
# データ管理のテスト
# ========================================

def test_load_data_existing_file():
    """既存ファイルからデータを読み込むテスト"""
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': 'https://connpass.com/test'}
    
    with patch('builtins.open', mock_open(read_data=json.dumps(test_data))):
        with patch('os.path.exists', return_value=True):
            result = bot.load_data()
            
    assert result == test_data


def test_load_data_no_file():
    """ファイルが存在しない場合のテスト"""
    with patch('os.path.exists', return_value=False):
        result = bot.load_data()
        
    assert result == {'hackmd': None, 'connpass': None}


def test_save_data():
    """データを保存するテスト"""
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': 'https://connpass.com/test'}
    
    m = mock_open()
    with patch('builtins.open', m):
        bot.save_data(test_data)
        
    m.assert_called_once_with('data.json', 'w', encoding='utf-8')
    handle = m()
    written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
    assert json.loads(written_data) == test_data


# ========================================
# 日付計算のテスト
# ========================================

def test_get_next_monday_from_monday():
    """月曜日から次の月曜日を計算"""
    JST = pytz.timezone('Asia/Tokyo')
    # 2024年1月1日は月曜日
    test_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=JST)
    
    with patch('bot.datetime') as mock_datetime:
        mock_datetime.now.return_value = test_date
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = bot.get_next_monday()
        
    # 次の月曜日は7日後
    expected = test_date + timedelta(days=7)
    assert result.date() == expected.date()


def test_get_next_monday_from_tuesday():
    """火曜日から次の月曜日を計算"""
    JST = pytz.timezone('Asia/Tokyo')
    # 2024年1月2日は火曜日
    test_date = datetime(2024, 1, 2, 12, 0, 0, tzinfo=JST)
    
    with patch('bot.datetime') as mock_datetime:
        mock_datetime.now.return_value = test_date
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = bot.get_next_monday()
        
    # 次の月曜日は6日後
    expected = test_date + timedelta(days=6)
    assert result.date() == expected.date()


def test_get_next_monday_from_sunday():
    """日曜日から次の月曜日を計算"""
    JST = pytz.timezone('Asia/Tokyo')
    # 2024年1月7日は日曜日
    test_date = datetime(2024, 1, 7, 12, 0, 0, tzinfo=JST)
    
    with patch('bot.datetime') as mock_datetime:
        mock_datetime.now.return_value = test_date
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = bot.get_next_monday()
        
    # 次の月曜日は1日後
    expected = test_date + timedelta(days=1)
    assert result.date() == expected.date()


# ========================================
# HackMD API関連のテスト
# ========================================

def test_get_hackmd_template_success():
    """テンプレート取得成功のテスト"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'id': 'Ocjjk_IDTDyi9tS76ARjbw',
        'content': '# テンプレート\n\nこれはテンプレートです。'
    }
    
    with patch('requests.get', return_value=mock_response):
        result = bot.get_hackmd_template()
        
    assert result == '# テンプレート\n\nこれはテンプレートです。'


def test_get_hackmd_template_failure():
    """テンプレート取得失敗のテスト"""
    mock_response = Mock()
    mock_response.status_code = 404
    
    with patch('requests.get', return_value=mock_response):
        result = bot.get_hackmd_template()
        
    assert result is None


def test_create_hackmd_note_success():
    """ノート作成成功のテスト"""
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {'id': 'test123', 'content': ''}
    
    with patch('requests.post', return_value=mock_response):
        result = bot.create_hackmd_note('テストタイトル', 'test_alias', '')
        
    assert result == 'https://hackmd.io/@tomio2480/test_alias'


def test_create_hackmd_note_with_content():
    """コンテンツ付きノート作成のテスト"""
    mock_post_response = Mock()
    mock_post_response.status_code = 201
    mock_post_response.json.return_value = {'id': 'test123', 'content': ''}
    
    mock_patch_response = Mock()
    mock_patch_response.status_code = 202
    
    with patch('requests.post', return_value=mock_post_response):
        with patch('requests.patch', return_value=mock_patch_response):
            result = bot.create_hackmd_note('テストタイトル', 'test_alias', '# テスト内容')
            
    assert result == 'https://hackmd.io/@tomio2480/test_alias'


def test_create_hackmd_note_failure():
    """ノート作成失敗のテスト"""
    mock_response = Mock()
    mock_response.status_code = 400
    
    with patch('requests.post', return_value=mock_response):
        result = bot.create_hackmd_note('テストタイトル', 'test_alias', '')
        
    assert result is None


# ========================================
# スラッシュコマンドのテスト
# ========================================

@pytest.mark.skip(reason="デコレーター関数のため、統合テストで確認")
@pytest.mark.asyncio
async def test_ls_command_authorized():
    """権限ありユーザーの/lsコマンド"""
    # モックの設定
    mock_interaction = AsyncMock()
    mock_interaction.user.name = 'tomio2480'
    
    test_data = {
        'hackmd': 'https://hackmd.io/test',
        'connpass': 'https://connpass.com/test'
    }
    
    JST = pytz.timezone('Asia/Tokyo')
    test_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=JST)
    
    with patch('bot.load_data', return_value=test_data):
        with patch('bot.get_next_monday', return_value=test_date):
            await bot.ls(mock_interaction)
    
    # ephemeralで応答が送信されたことを確認
    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    assert call_args[1]['ephemeral'] is True
    assert '01/01 (月)' in call_args[0][0]
    assert 'https://hackmd.io/test' in call_args[0][0]
    assert 'https://connpass.com/test' in call_args[0][0]


@pytest.mark.skip(reason="デコレーター関数のため、統合テストで確認")
@pytest.mark.asyncio
async def test_ls_command_unauthorized():
    """権限なしユーザーの/lsコマンド"""
    mock_interaction = AsyncMock()
    mock_interaction.user.name = 'other_user'
    
    await bot.ls(mock_interaction)
    
    # エラーメッセージが送信されたことを確認
    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    assert call_args[1]['ephemeral'] is True
    assert '権限がありません' in call_args[0][0]


@pytest.mark.skip(reason="デコレーター関数のため、統合テストで確認")
@pytest.mark.asyncio
async def test_set_connpass_authorized():
    """connpass設定コマンド"""
    mock_interaction = AsyncMock()
    mock_interaction.user.name = 'tomio2480'
    
    test_url = 'https://connpass.com/event/12345/'
    
    with patch('bot.load_data', return_value={'hackmd': None, 'connpass': None}):
        with patch('bot.save_data') as mock_save:
            await bot.set_connpass(mock_interaction, test_url)
    
    # データが保存されたことを確認
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    assert saved_data['connpass'] == test_url
    
    # 成功メッセージが送信されたことを確認
    mock_interaction.response.send_message.assert_called_once()


@pytest.mark.skip(reason="デコレーター関数のため、統合テストで確認")
@pytest.mark.asyncio
async def test_set_hackmd_authorized():
    """HackMD設定コマンド"""
    mock_interaction = AsyncMock()
    mock_interaction.user.name = 'tomio2480'
    
    test_url = 'https://hackmd.io/test123'
    
    with patch('bot.load_data', return_value={'hackmd': None, 'connpass': None}):
        with patch('bot.save_data') as mock_save:
            await bot.set_hackmd(mock_interaction, test_url)
    
    # データが保存されたことを確認
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    assert saved_data['hackmd'] == test_url
    
    # 成功メッセージが送信されたことを確認
    mock_interaction.response.send_message.assert_called_once()


# ========================================
# スケジュール投稿のテスト
# ========================================

@pytest.mark.asyncio
async def test_post_morning():
    """朝の投稿"""
    mock_channel = AsyncMock()
    
    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        await bot.post_morning()
    
    mock_channel.send.assert_called_once_with('📢 今日はブログを読む日です')


@pytest.mark.asyncio
async def test_post_reminder():
    """リマインダー投稿"""
    mock_channel = AsyncMock()
    
    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        await bot.post_reminder()
    
    mock_channel.send.assert_called_once_with('👀 テックブログ一気読み選手権まであと少し')


@pytest.mark.asyncio
async def test_post_start():
    """開始投稿"""
    mock_channel = AsyncMock()
    test_data = {
        'hackmd': 'https://hackmd.io/test',
        'connpass': 'https://connpass.com/test'
    }
    
    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        with patch('bot.load_data', return_value=test_data):
            await bot.post_start()
    
    mock_channel.send.assert_called_once()
    call_args = mock_channel.send.call_args[0][0]
    assert 'https://hackmd.io/test' in call_args
    assert 'https://connpass.com/test' in call_args
    # リンクを含む投稿は埋め込みを抑止する
    assert mock_channel.send.call_args.kwargs.get('suppress_embeds') is True


@pytest.mark.asyncio
async def test_post_writing_time():
    """18:38の投稿"""
    mock_channel = AsyncMock()
    
    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        await bot.post_writing_time()
    
    mock_channel.send.assert_called_once_with('18:38 になりました\n感想を書きましょう')


@pytest.mark.asyncio
async def test_post_sharing_reminder():
    """18:42の投稿"""
    mock_channel = AsyncMock()
    
    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        await bot.post_sharing_reminder()
    
    mock_channel.send.assert_called_once_with('そろそろ感想を共有します\n画面共有の準備をしてください')


@pytest.mark.asyncio
async def test_post_create_hackmd():
    """HackMD作成投稿"""
    mock_channel = AsyncMock()
    
    JST = pytz.timezone('Asia/Tokyo')
    test_date = datetime(2024, 1, 8, 12, 0, 0, tzinfo=JST)  # 次の月曜日
    
    template_content = '# テンプレート'
    hackmd_url = 'https://hackmd.io/@tomio2480/blogread_20240108'
    
    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        with patch('bot.get_next_monday', return_value=test_date):
            with patch('bot.get_hackmd_template', return_value=template_content):
                with patch('bot.create_hackmd_note', return_value=hackmd_url):
                    with patch('bot.load_data', return_value={'hackmd': None, 'connpass': None}):
                        with patch('bot.save_data'):
                            await bot.post_create_hackmd()
    
    mock_channel.send.assert_called_once()
    call_args = mock_channel.send.call_args[0][0]
    assert '01/08 (月)' in call_args
    assert hackmd_url in call_args
    # リンクを含む投稿は埋め込みを抑止する
    assert mock_channel.send.call_args.kwargs.get('suppress_embeds') is True


# ========================================
# 二重投稿防止のテスト
# ========================================

def test_scheduler_started_flag_initial():
    """スケジューラ初期化フラグの初期値"""
    # bot.py がインポートされた直後は False
    # ただし、テスト実行順によっては True になっている可能性があるため
    # フラグの存在確認のみ行う
    assert hasattr(bot, 'scheduler_started')


# ========================================
# connpass RSS 自動取得のテスト
# ========================================

def test_get_next_monday_date_str():
    """次の月曜日の日付文字列（yyyyMMdd形式）を取得"""
    JST = pytz.timezone('Asia/Tokyo')
    test_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=JST)  # 月曜日
    next_monday = test_date + timedelta(days=7)  # 次の月曜日は1/8

    with patch('bot.get_next_monday', return_value=next_monday):
        result = bot.get_next_monday_date_str()

    assert result == '20240108'


def test_check_connpass_rss_found():
    """RSS から次の月曜日のイベントが見つかった場合"""
    JST = pytz.timezone('Asia/Tokyo')
    next_monday = datetime(2024, 1, 8, 12, 0, 0, tzinfo=JST)

    mock_feed = MagicMock()
    mock_feed.entries = [
        {'title': 'テックブログ一気読み選手権20240108杯', 'link': 'https://blogreading.connpass.com/event/12345/'},
        {'title': '別のイベント', 'link': 'https://connpass.com/other/'},
    ]

    with patch('bot.get_next_monday', return_value=next_monday):
        with patch('bot.feedparser.parse', return_value=mock_feed):
            result = bot.check_connpass_rss()

    assert result == 'https://blogreading.connpass.com/event/12345/'


def test_check_connpass_rss_not_found():
    """RSS から次の月曜日のイベントが見つからない場合"""
    JST = pytz.timezone('Asia/Tokyo')
    next_monday = datetime(2024, 1, 8, 12, 0, 0, tzinfo=JST)

    mock_feed = MagicMock()
    mock_feed.entries = [
        {'title': 'テックブログ一気読み選手権20240101杯', 'link': 'https://blogreading.connpass.com/event/99999/'},
    ]

    with patch('bot.get_next_monday', return_value=next_monday):
        with patch('bot.feedparser.parse', return_value=mock_feed):
            result = bot.check_connpass_rss()

    assert result is None


def test_check_connpass_rss_empty_feed():
    """RSS が空の場合"""
    mock_feed = MagicMock()
    mock_feed.entries = []

    with patch('bot.feedparser.parse', return_value=mock_feed):
        result = bot.check_connpass_rss()

    assert result is None


def test_check_connpass_rss_error():
    """RSS 取得エラーの場合"""
    with patch('bot.feedparser.parse', side_effect=Exception('Network error')):
        result = bot.check_connpass_rss()

    assert result is None


@pytest.mark.asyncio
async def test_check_and_post_connpass_already_set():
    """connpass URL が設定済みの場合はスキップ"""
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': 'https://connpass.com/existing'}

    with patch('bot.load_data', return_value=test_data):
        with patch('bot.check_connpass_rss') as mock_check:
            await bot.check_and_post_connpass()
            # RSS チェックが呼ばれないことを確認
            mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_check_and_post_connpass_not_found():
    """RSS からイベントが見つからない場合"""
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': None}

    with patch('bot.load_data', return_value=test_data):
        with patch('bot.check_connpass_rss', return_value=None):
            with patch('bot.save_data') as mock_save:
                await bot.check_and_post_connpass()
                # save_data が呼ばれないことを確認
                mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_check_and_post_connpass_found_and_post():
    """RSS からイベントが見つかり、投稿する場合"""
    mock_channel = AsyncMock()
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': None}
    connpass_url = 'https://blogreading.connpass.com/event/12345/'

    JST = pytz.timezone('Asia/Tokyo')
    next_monday = datetime(2024, 1, 8, 12, 0, 0, tzinfo=JST)

    with patch('bot.load_data', return_value=test_data):
        with patch('bot.check_connpass_rss', return_value=connpass_url):
            with patch('bot.save_data') as mock_save:
                with patch('bot.get_next_monday', return_value=next_monday):
                    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
                        await bot.check_and_post_connpass()

    # データが保存されたことを確認
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    assert saved_data['connpass'] == connpass_url

    # 投稿が行われたことを確認
    mock_channel.send.assert_called_once()
    call_args = mock_channel.send.call_args[0][0]
    assert '01/08(月)' in call_args
    assert 'https://hackmd.io/test' in call_args
    assert connpass_url in call_args
    # リンクを含む投稿は埋め込みを抑止する
    assert mock_channel.send.call_args.kwargs.get('suppress_embeds') is True


@pytest.mark.asyncio
async def test_check_and_post_connpass_no_hackmd():
    """hackmd が未設定の場合は投稿しない"""
    mock_channel = AsyncMock()
    test_data = {'hackmd': None, 'connpass': None}
    connpass_url = 'https://blogreading.connpass.com/event/12345/'

    with patch('bot.load_data', return_value=test_data):
        with patch('bot.check_connpass_rss', return_value=connpass_url):
            with patch('bot.save_data') as mock_save:
                with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
                    await bot.check_and_post_connpass()

    # connpass URL は保存されるが、投稿は行われない
    mock_save.assert_called_once()
    mock_channel.send.assert_not_called()


# ========================================
# データストア整合性のテスト
# ========================================

def test_save_data_always_writes_local_file():
    """Google Sheets 保存成功時もローカルファイルに書き込むことを確認"""
    test_data = {'hackmd': None, 'connpass': None}

    mock_worksheet = MagicMock()
    m = mock_open()

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', m):
            bot.save_data(test_data)

    # Google Sheets にも保存される
    mock_worksheet.clear.assert_called_once()
    # ローカルファイルにも書き込まれる
    m.assert_called_once_with('data.json', 'w', encoding='utf-8')


def test_save_data_local_file_has_cleared_data_after_google_sheets_save():
    """Google Sheets 保存後にローカルファイルにクリア済みデータが書き込まれることを確認"""
    test_data = {'hackmd': None, 'connpass': None}

    mock_worksheet = MagicMock()
    m = mock_open()

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', m):
            bot.save_data(test_data)

    # ローカルファイルに書き込まれたデータを検証
    handle = m()
    written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
    saved = json.loads(written_data)
    assert saved['hackmd'] is None
    assert saved['connpass'] is None


def test_save_data_local_write_failure_does_not_skip_google_sheets():
    """ローカル書き込みが失敗しても Google Sheets への保存は実行されることを確認"""
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': None}

    mock_worksheet = MagicMock()

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', side_effect=OSError('read-only file system')):
            bot.save_data(test_data)

    # ローカル失敗に関わらず Google Sheets へ保存される
    mock_worksheet.clear.assert_called_once()
    assert mock_worksheet.update.call_count == 2


# ========================================
# Google Sheets 障害時のデータ消失防止テスト
# ========================================

def test_load_data_returns_none_when_sheets_fails_and_no_cache():
    """Sheets 設定済みで読み込みに失敗し，ローカルキャッシュも無ければ None を返す"""
    with patch('bot.get_worksheet', side_effect=Exception('API error')):
        with patch('os.path.exists', return_value=False):
            with patch('bot.time.sleep'):
                result = bot.load_data()

    # 既定値ではなく None を返し，呼び出し側が上書き保存しないようにする
    assert result is None


def test_load_data_returns_local_cache_when_sheets_fails():
    """Sheets 読み込みに失敗した場合はローカルキャッシュを返す"""
    cached = {'hackmd': 'https://hackmd.io/cached', 'connpass': None}

    with patch('bot.get_worksheet', side_effect=Exception('API error')):
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(cached))):
                with patch('bot.time.sleep'):
                    result = bot.load_data()

    assert result == cached


def test_load_data_retries_sheets_read():
    """Sheets 読み込みが一時的に失敗しても再試行して読み込む"""
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_records.return_value = [
        {'キー': 'hackmd', '値': 'https://hackmd.io/test'},
        {'キー': 'connpass', '値': ''},
    ]

    with patch('bot.get_worksheet', side_effect=[Exception('transient'), mock_worksheet]) as mock_get:
        with patch('bot.time.sleep') as mock_sleep:
            result = bot.load_data()

    assert result == {'hackmd': 'https://hackmd.io/test', 'connpass': None}
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


def test_save_data_retries_sheets_write():
    """Sheets 書き込みが一時的に失敗しても再試行して保存する"""
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': None}
    mock_worksheet = MagicMock()
    mock_worksheet.clear.side_effect = [Exception('transient'), None]

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', mock_open()):
            with patch('bot.time.sleep'):
                bot.save_data(test_data)

    assert mock_worksheet.clear.call_count == 2
    assert mock_worksheet.update.call_count == 2


@pytest.mark.asyncio
async def test_check_and_post_connpass_skips_when_load_fails():
    """データを読み込めない場合は RSS 確認も保存も行わない（hackmd の上書き消失を防ぐ）"""
    with patch('bot.load_data', return_value=None):
        with patch('bot.check_connpass_rss') as mock_check:
            with patch('bot.save_data') as mock_save:
                await bot.check_and_post_connpass()

    mock_check.assert_not_called()
    mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_post_create_hackmd_saves_url_even_if_load_fails():
    """19:00 にデータを読み込めなくても作成した HackMD URL は保存し投稿する"""
    mock_channel = AsyncMock()
    JST = pytz.timezone('Asia/Tokyo')
    test_date = datetime(2024, 1, 8, 12, 0, 0, tzinfo=JST)
    hackmd_url = 'https://hackmd.io/@tomio2480/blogread_20240108'

    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        with patch('bot.get_next_monday', return_value=test_date):
            with patch('bot.get_hackmd_template', return_value=''):
                with patch('bot.create_hackmd_note', return_value=hackmd_url):
                    with patch('bot.load_data', return_value=None):
                        with patch('bot.check_connpass_rss', return_value=None):
                            with patch('bot.save_data') as mock_save:
                                await bot.post_create_hackmd()

    mock_save.assert_called_once()
    assert mock_save.call_args[0][0]['hackmd'] == hackmd_url
    mock_channel.send.assert_called_once()
    assert hackmd_url in mock_channel.send.call_args[0][0]


@pytest.mark.asyncio
async def test_post_start_posts_and_clears_even_if_load_fails():
    """18:30 にデータを読み込めなくても投稿し，データをクリアする"""
    mock_channel = AsyncMock()

    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        with patch('bot.load_data', return_value=None):
            with patch('bot.save_data') as mock_save:
                await bot.post_start()

    mock_channel.send.assert_called_once()
    assert '（HackMD 未設定）' in mock_channel.send.call_args[0][0]
    saved = mock_save.call_args[0][0]
    assert saved['hackmd'] is None and saved['connpass'] is None


# ========================================
# post_start データクリアの堅牢性テスト
# ========================================

@pytest.mark.asyncio
async def test_post_start_clears_data_after_send():
    """18:30 投稿後にデータがクリアされることを確認"""
    mock_channel = AsyncMock()
    test_data = {
        'hackmd': 'https://hackmd.io/test',
        'connpass': 'https://connpass.com/test'
    }

    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        with patch('bot.load_data', return_value=test_data):
            with patch('bot.save_data') as mock_save:
                await bot.post_start()

    # save_data が呼ばれ、両方のURLがNoneになっていることを確認
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    assert saved_data['hackmd'] is None
    assert saved_data['connpass'] is None


@pytest.mark.asyncio
async def test_post_start_clears_data_even_if_send_fails():
    """channel.send が失敗してもデータがクリアされることを確認"""
    mock_channel = AsyncMock()
    mock_channel.send.side_effect = Exception('Discord API error')
    test_data = {
        'hackmd': 'https://hackmd.io/test',
        'connpass': 'https://connpass.com/test'
    }

    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        with patch('bot.load_data', return_value=test_data):
            with patch('bot.save_data') as mock_save:
                await bot.post_start()

    # send が失敗しても save_data が呼ばれ、データがクリアされることを確認
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    assert saved_data['hackmd'] is None
    assert saved_data['connpass'] is None
