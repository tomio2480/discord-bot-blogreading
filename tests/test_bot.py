"""
Discord Bot のテストコード

既存機能と新機能のすべてのテストを含む。
TDDアプローチで、テストを先に作成してから実装を行う。
"""

import asyncio
import pytest
import json
import os
import sys
import threading
import time as time_module
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, mock_open, MagicMock
import pytz

# テスト用の環境変数を設定（bot.py インポート前に必要）
os.environ.setdefault('DISCORD_TOKEN', 'test_token')
os.environ.setdefault('DISCORD_CHANNEL_ID', '123456789')
os.environ.setdefault('HACKMD_API_TOKEN', 'test_hackmd_token')

# feedparser のみモック化（RSS への実接続を伴わずに関数単体を検証するため）
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

    m.assert_any_call('data.json', 'w', encoding='utf-8')
    handle = m()
    written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
    assert json.loads(written_data) == test_data


# ========================================
# 非同期ラッパー（aload_data / asave_data）のテスト
# ========================================

@pytest.mark.asyncio
async def test_aload_data_runs_off_event_loop_thread():
    """aload_data は load_data を別スレッドで実行し，その戻り値をそのまま返す"""
    caller_thread_id = threading.get_ident()
    called_thread_ids = []
    expected = {'hackmd': 'https://hackmd.io/test', 'connpass': None}

    def fake_load_data():
        called_thread_ids.append(threading.get_ident())
        return expected

    with patch('bot.load_data', side_effect=fake_load_data):
        result = await bot.aload_data()

    assert result == expected
    assert called_thread_ids == [called_thread_ids[0]]
    assert called_thread_ids[0] != caller_thread_id


@pytest.mark.asyncio
async def test_asave_data_passes_data_and_runs_off_event_loop_thread():
    """asave_data は受け取ったデータをそのまま save_data へ渡し，別スレッドで実行する"""
    caller_thread_id = threading.get_ident()
    called_thread_ids = []
    received_data = []
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': None}

    def fake_save_data(data):
        called_thread_ids.append(threading.get_ident())
        received_data.append(data)

    with patch('bot.save_data', side_effect=fake_save_data):
        await bot.asave_data(test_data)

    assert received_data == [test_data]
    assert called_thread_ids[0] != caller_thread_id


@pytest.mark.asyncio
async def test_aload_data_does_not_block_event_loop():
    """load_data 内の time.sleep による待機中も，イベントループは他のコルーチンを進められる"""
    event = threading.Event()
    event_was_set_before_load_finished = []

    def slow_load_data():
        time_module.sleep(0.2)
        event_was_set_before_load_finished.append(event.is_set())
        return {'hackmd': None, 'connpass': None}

    async def set_event_soon():
        await asyncio.sleep(0.05)
        event.set()

    with patch('bot.load_data', side_effect=slow_load_data):
        await asyncio.gather(bot.aload_data(), set_event_soon())

    assert event_was_set_before_load_finished == [True]


@pytest.mark.asyncio
async def test_storage_lock_serializes_access():
    """save_data の読み込みからキャッシュ書き込みまでは lock で直列化され，割り込まれない
    （set_connpass と set_hackmd 等が重なっても互いの項目を消さないため）"""
    in_progress = threading.Event()
    overlap_detected = []

    def slow_write_local(data, unsynced):
        if in_progress.is_set():
            overlap_detected.append(True)
        in_progress.set()
        time_module.sleep(0.05)
        in_progress.clear()

    with patch('bot.get_worksheet', return_value=None):
        with patch('bot.load_local', return_value=({}, False)):
            with patch('bot.write_local', side_effect=slow_write_local):
                await asyncio.gather(
                    bot.asave_data({'hackmd': 'H'}),
                    bot.asave_data({'connpass': 'C'}),
                )

    assert overlap_detected == []


@pytest.mark.asyncio
async def test_concurrent_saves_do_not_lose_other_field(tmp_path):
    """異なる項目の部分更新が同時に走っても，互いのフィールドを消さない"""
    data_file = tmp_path / 'data.json'

    with patch('bot.DATA_FILE', str(data_file)):
        with patch('bot.get_worksheet', return_value=None):
            await asyncio.gather(
                bot.asave_data({'hackmd': 'H'}),
                bot.asave_data({'connpass': 'C'}),
            )

    saved = json.loads(data_file.read_text(encoding='utf-8'))
    assert saved['hackmd'] == 'H'
    assert saved['connpass'] == 'C'


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

def make_interaction(user_name):
    """スラッシュコマンドテスト用の interaction モックを作る"""
    mock_interaction = AsyncMock()
    mock_interaction.user.name = user_name
    return mock_interaction


@pytest.mark.asyncio
async def test_ls_command_authorized():
    """権限ありユーザーの/lsコマンド"""
    mock_interaction = make_interaction('tomio2480')

    test_data = {
        'hackmd': 'https://hackmd.io/test',
        'connpass': 'https://connpass.com/test'
    }

    JST = pytz.timezone('Asia/Tokyo')
    test_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=JST)

    with patch('bot.load_data', return_value=test_data):
        with patch('bot.get_next_monday', return_value=test_date):
            await bot.ls.callback(mock_interaction)

    # 3秒制限対策で defer してから followup で応答する
    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    mock_interaction.followup.send.assert_called_once()
    call_args = mock_interaction.followup.send.call_args
    assert '01/01 (月)' in call_args[0][0]
    assert 'https://hackmd.io/test' in call_args[0][0]
    assert 'https://connpass.com/test' in call_args[0][0]
    assert call_args[1]['ephemeral'] is True
    assert call_args[1]['suppress_embeds'] is True


@pytest.mark.asyncio
async def test_ls_command_unauthorized():
    """権限なしユーザーの/lsコマンド"""
    mock_interaction = make_interaction('other_user')

    await bot.ls.callback(mock_interaction)

    # エラーメッセージが送信されたことを確認し，defer/followup は使われないことを確認
    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    assert call_args[1]['ephemeral'] is True
    assert '権限がありません' in call_args[0][0]
    mock_interaction.response.defer.assert_not_called()
    mock_interaction.followup.send.assert_not_called()


@pytest.mark.asyncio
async def test_ls_command_load_error():
    """データ読み込みに失敗した場合はエラーメッセージを送信する"""
    mock_interaction = make_interaction('tomio2480')

    with patch('bot.load_data', return_value=None):
        await bot.ls.callback(mock_interaction)

    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    mock_interaction.followup.send.assert_called_once_with(bot.LOAD_ERROR_MESSAGE, ephemeral=True)


@pytest.mark.asyncio
async def test_ls_command_loads_via_thread():
    """/ls はデータ読み込みを aload_data（スレッド経由）で行う"""
    mock_interaction = make_interaction('tomio2480')
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': 'https://connpass.com/test'}

    with patch('bot.aload_data', AsyncMock(return_value=test_data)) as mock_aload:
        with patch('bot.get_next_monday', return_value=datetime(2024, 1, 1, tzinfo=pytz.timezone('Asia/Tokyo'))):
            await bot.ls.callback(mock_interaction)

    mock_aload.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_set_connpass_authorized():
    """connpass設定コマンド（クエリパラメータは取り除いて保存する）"""
    mock_interaction = make_interaction('tomio2480')

    test_url = 'https://connpass.com/event/12345/?utm_source=x'
    expected_url = 'https://connpass.com/event/12345/'

    with patch('bot.load_data', return_value={'hackmd': None, 'connpass': None}):
        with patch('bot.save_data') as mock_save:
            await bot.set_connpass.callback(mock_interaction, test_url)

    # データが保存されたことを確認
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    assert saved_data['connpass'] == expected_url

    # 成功メッセージが defer/followup で送信されたことを確認
    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    mock_interaction.followup.send.assert_called_once()
    call_args = mock_interaction.followup.send.call_args
    assert call_args[1]['ephemeral'] is True
    assert call_args[1]['suppress_embeds'] is True


@pytest.mark.asyncio
async def test_set_connpass_saves_via_thread():
    """/set_connpass はデータ読み書きを aload_data / asave_data（スレッド経由）で行う"""
    mock_interaction = make_interaction('tomio2480')
    test_url = 'https://connpass.com/event/12345/?utm_source=x'
    expected_url = 'https://connpass.com/event/12345/'

    with patch('bot.aload_data', AsyncMock(return_value={'hackmd': None, 'connpass': None})):
        with patch('bot.asave_data', AsyncMock()) as mock_asave:
            await bot.set_connpass.callback(mock_interaction, test_url)

    mock_asave.assert_awaited_once()
    saved_data = mock_asave.call_args[0][0]
    assert saved_data['connpass'] == expected_url


@pytest.mark.asyncio
async def test_set_connpass_saves_only_connpass():
    """/set_connpass は変更した connpass だけを部分更新で保存し，hackmd を巻き込まない
    （/set_hackmd や RSS ジョブとの同時実行で相手の更新を巻き戻さないため）"""
    mock_interaction = make_interaction('tomio2480')
    test_url = 'https://connpass.com/event/12345/?utm_source=x'
    expected_url = 'https://connpass.com/event/12345/'

    with patch('bot.aload_data', AsyncMock(return_value={'hackmd': 'https://hackmd.io/keep', 'connpass': None})):
        with patch('bot.asave_data', AsyncMock()) as mock_asave:
            await bot.set_connpass.callback(mock_interaction, test_url)

    mock_asave.assert_awaited_once_with({'connpass': expected_url})


@pytest.mark.asyncio
async def test_set_hackmd_authorized():
    """HackMD設定コマンド"""
    mock_interaction = make_interaction('tomio2480')

    test_url = 'https://hackmd.io/test123'

    with patch('bot.load_data', return_value={'hackmd': None, 'connpass': None}):
        with patch('bot.save_data') as mock_save:
            await bot.set_hackmd.callback(mock_interaction, test_url)

    # データが保存されたことを確認
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    assert saved_data['hackmd'] == test_url

    # 成功メッセージが defer/followup で送信されたことを確認
    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    mock_interaction.followup.send.assert_called_once()
    call_args = mock_interaction.followup.send.call_args
    assert call_args[1]['ephemeral'] is True
    assert call_args[1]['suppress_embeds'] is True


@pytest.mark.asyncio
async def test_set_hackmd_saves_only_hackmd():
    """/set_hackmd は変更した hackmd だけを部分更新で保存し，connpass を巻き込まない"""
    mock_interaction = make_interaction('tomio2480')
    test_url = 'https://hackmd.io/test123'

    with patch('bot.aload_data', AsyncMock(return_value={'hackmd': None, 'connpass': 'https://connpass.com/keep'})):
        with patch('bot.asave_data', AsyncMock()) as mock_asave:
            await bot.set_hackmd.callback(mock_interaction, test_url)

    mock_asave.assert_awaited_once_with({'hackmd': test_url})


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
    mock_worksheet.batch_update.assert_called_once()
    # ローカルファイルにも書き込まれる
    m.assert_any_call('data.json', 'w', encoding='utf-8')


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

    # ローカル失敗に関わらず Google Sheets へ保存される（ヘッダー + 2 項目）
    mock_worksheet.batch_update.assert_called_once()
    assert len(mock_worksheet.batch_update.call_args[0][0]) == 3


def test_write_sheet_partial_update_preserves_other_rows():
    """一部の項目だけ渡した場合，その行だけ更新し他の項目の行には触れない"""
    mock_worksheet = MagicMock()

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', mock_open()):
            bot.save_data({'hackmd': 'https://hackmd.io/only'})

    mock_worksheet.clear.assert_not_called()
    ranges = [u['range'] for u in mock_worksheet.batch_update.call_args[0][0]]
    assert ranges == ['A1:B1', 'A2:B2']  # ヘッダーと hackmd 行のみ．connpass 行（A3:B3）は保持
    values = [u['values'] for u in mock_worksheet.batch_update.call_args[0][0]]
    assert values[1] == [['hackmd', 'https://hackmd.io/only']]


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
            with patch('builtins.open', mock_open()):
                result = bot.load_data()

    assert result == {'hackmd': 'https://hackmd.io/test', 'connpass': None}
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


def test_load_data_refreshes_local_cache_after_sheets_read():
    """Sheets を読み込めたら，その内容でローカルキャッシュを更新する（古いキャッシュが再同期で昇格しないように）"""
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_records.return_value = [
        {'キー': 'hackmd', '値': 'https://hackmd.io/remote'},
        {'キー': 'connpass', '値': 'https://connpass.com/remote'},
    ]
    stale = json.dumps({'hackmd': 'https://hackmd.io/stale', 'connpass': None})
    m = mock_open(read_data=stale)

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', m):
            with patch('os.path.exists', return_value=True):
                result = bot.load_data()

    assert result == {'hackmd': 'https://hackmd.io/remote', 'connpass': 'https://connpass.com/remote'}
    m.assert_any_call('data.json', 'w', encoding='utf-8')
    assert _written_json(m) == result


def test_save_data_retries_sheets_write():
    """Sheets 書き込みが一時的に失敗しても再試行して保存する"""
    test_data = {'hackmd': 'https://hackmd.io/test', 'connpass': None}
    mock_worksheet = MagicMock()
    mock_worksheet.batch_update.side_effect = [Exception('transient'), None]

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', mock_open()):
            with patch('bot.time.sleep'):
                bot.save_data(test_data)

    assert mock_worksheet.batch_update.call_count == 2


def _written_json(m):
    """mock_open へ書き込まれた内容を JSON として返す"""
    handle = m()
    return json.loads(''.join(call.args[0] for call in handle.write.call_args_list))


def test_save_data_marks_cache_unsynced_when_sheets_fails():
    """Sheets 保存に失敗した場合，ローカルキャッシュに未同期の印を付けて書く（再起動後も判別できるように）"""
    newer = {'hackmd': 'https://hackmd.io/new', 'connpass': None}
    m = mock_open(read_data='')

    with patch('bot.get_worksheet', side_effect=Exception('down')):
        with patch('bot.time.sleep'):
            with patch('builtins.open', m):
                with patch('os.path.exists', return_value=False):
                    bot.save_data(newer)

    written = _written_json(m)
    assert written[bot.UNSYNCED_KEY] is True
    assert written['hackmd'] == newer['hackmd']


def test_load_data_resyncs_unsynced_cache_when_sheets_recovers():
    """未同期の印が付いたキャッシュがあれば，復旧した Sheets の古い値ではなくキャッシュを正として書き戻す"""
    newer = {'hackmd': 'https://hackmd.io/new', 'connpass': None}
    cached_file = json.dumps({**newer, bot.UNSYNCED_KEY: True})
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_records.return_value = [{'キー': 'hackmd', '値': ''}]  # 古いリモート
    m = mock_open(read_data=cached_file)

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('bot.time.sleep'):
            with patch('builtins.open', m):
                with patch('os.path.exists', return_value=True):
                    result = bot.load_data()

    # キャッシュが返り，Sheets へ書き戻され，キャッシュの未同期の印が消える
    assert result == newer
    mock_worksheet.batch_update.assert_called_once()
    mock_worksheet.get_all_records.assert_not_called()
    assert bot.UNSYNCED_KEY not in _written_json(m)


def test_load_data_keeps_unsynced_when_resync_fails():
    """再同期にも失敗した場合はキャッシュを返し，未同期の印を残す"""
    newer = {'hackmd': 'https://hackmd.io/new', 'connpass': None}
    m = mock_open(read_data=json.dumps({**newer, bot.UNSYNCED_KEY: True}))

    with patch('bot.get_worksheet', side_effect=Exception('still down')):
        with patch('bot.time.sleep'):
            with patch('builtins.open', m):
                with patch('os.path.exists', return_value=True):
                    result = bot.load_data()

    assert result == newer
    assert _written_json(m)[bot.UNSYNCED_KEY] is True


def test_save_data_merges_partial_update_into_local_cache():
    """部分更新でも，ローカルキャッシュには既存内容と統合した全項目を書く"""
    cached_file = json.dumps({'hackmd': 'https://hackmd.io/old', 'connpass': 'https://connpass.com/keep'})
    mock_worksheet = MagicMock()
    m = mock_open(read_data=cached_file)

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', m):
            with patch('os.path.exists', return_value=True):
                bot.save_data({'hackmd': 'https://hackmd.io/new'})

    # Sheets へは hackmd 行だけ，ローカルには統合済みスナップショット
    ranges = [u['range'] for u in mock_worksheet.batch_update.call_args[0][0]]
    assert ranges == ['A1:B1', 'A2:B2']
    assert _written_json(m) == {'hackmd': 'https://hackmd.io/new', 'connpass': 'https://connpass.com/keep'}


def test_save_data_pushes_full_cache_when_it_was_unsynced():
    """未同期のキャッシュがある状態で部分更新すると，キャッシュの内容ごと Sheets へ書き戻す"""
    cached_file = json.dumps({'hackmd': None, 'connpass': 'https://connpass.com/unsynced', bot.UNSYNCED_KEY: True})
    mock_worksheet = MagicMock()
    m = mock_open(read_data=cached_file)

    with patch('bot.get_worksheet', return_value=mock_worksheet):
        with patch('builtins.open', m):
            with patch('os.path.exists', return_value=True):
                bot.save_data({'hackmd': 'https://hackmd.io/new'})

    ranges = [u['range'] for u in mock_worksheet.batch_update.call_args[0][0]]
    assert ranges == ['A1:B1', 'A2:B2', 'A3:B3']
    assert bot.UNSYNCED_KEY not in _written_json(m)


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
    saved = mock_save.call_args[0][0]
    assert saved['hackmd'] == hackmd_url
    # 読み込めなかった項目（connpass）は書かず，Sheets 上の既存値を保持する
    assert 'connpass' not in saved
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


@pytest.mark.asyncio
async def test_post_start_clears_both_links():
    """18:30 投稿後は hackmd・connpass の両方を None として部分更新で保存する
    （19:00 の新規作成に備えた意図的な消去．辞書全体ではなく明示的な 2 項目のみ渡す）"""
    mock_channel = AsyncMock()
    test_data = {
        'hackmd': 'https://hackmd.io/test',
        'connpass': 'https://connpass.com/test'
    }

    with patch.object(bot.bot, 'get_channel', return_value=mock_channel):
        with patch('bot.aload_data', AsyncMock(return_value=test_data)):
            with patch('bot.asave_data', AsyncMock()) as mock_asave:
                await bot.post_start()

    mock_asave.assert_awaited_once_with({'hackmd': None, 'connpass': None})
