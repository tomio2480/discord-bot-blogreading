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

# discord.pyのインポートをモック化（Python 3.13のaudioop問題を回避）
sys.modules['discord'] = MagicMock()
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['discord.app_commands'] = MagicMock()

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
        
    assert result == 'https://hackmd.io/test_alias'


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
            
    assert result == 'https://hackmd.io/test_alias'


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
    hackmd_url = 'https://hackmd.io/blogread_20240108'
    
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
