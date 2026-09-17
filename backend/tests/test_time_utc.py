"""库里读出来的时间是 naive，参与算术前必须补上 UTC。

真实事故：接管容器时算已跑时长，utc_now() 减 started_at 抛
「can't subtract offset-naive and offset-aware datetimes」，接管协程当场崩，
任务被误判成中断，容器却还在跑。
"""

from datetime import datetime, timedelta, timezone

from app.models import as_utc, utc_now


def test_naive_gets_utc():
    naive = datetime(2026, 9, 16, 3, 48, 19)
    assert as_utc(naive) == naive.replace(tzinfo=timezone.utc)


def test_aware_is_left_alone():
    aware = datetime(2026, 9, 16, 3, 48, 19, tzinfo=timezone.utc)
    assert as_utc(aware) is aware


def test_none_passes_through():
    assert as_utc(None) is None


def test_subtracting_a_db_value_works():
    """这就是崩掉的那行：SQLite 读回的 started_at 不带时区。"""
    started = (utc_now() - timedelta(minutes=30)).replace(tzinfo=None)
    elapsed = (utc_now() - as_utc(started)).total_seconds()
    assert 1790 < elapsed < 1810


def test_timestamp_is_not_shifted_by_local_tz():
    """轨迹筛选按 mtime 比较，naive 的 .timestamp() 会被当本地时间而整体偏移。"""
    aware = datetime(2026, 9, 16, 3, 48, 19, tzinfo=timezone.utc)
    assert as_utc(aware.replace(tzinfo=None)).timestamp() == aware.timestamp()
