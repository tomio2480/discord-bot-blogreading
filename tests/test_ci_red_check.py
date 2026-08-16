"""CI が失敗を赤で報告することを確認する一時テスト．確認後の commit で削除する．"""


def test_ci_reports_failure():
    assert False, "CI が赤になることの実測用"
