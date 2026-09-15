"""设置存储：掩码不能被当成真值写回去。"""

from app.services import settings_store as ss


def test_masked_value_is_not_written(monkeypatch):
    """界面回传的掩码是「占位符 + 末 4 位」，直接比较占位符会漏掉，密钥当场作废。"""
    written: dict[str, str] = {}

    class FakeRow:
        def __init__(self) -> None:
            self.value_enc = ""

    class FakeDB:
        def get(self, _model, key):  # noqa: ANN001
            return rows.setdefault(key, FakeRow())

        def add(self, _row):  # noqa: ANN001
            pass

    rows: dict[str, FakeRow] = {}

    class FakeSession:
        def __enter__(self):
            return FakeDB()

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(ss, "session", lambda: FakeSession())
    monkeypatch.setattr(ss, "_enc", lambda v: f"enc:{v}")

    masked = ss.masked("sk-abcdefgh1234", secret=True)
    assert masked.startswith(ss.MASK_PLACEHOLDER) and masked.endswith("1234")

    done = ss.set_many({"cc.api_key": masked, "cc.image": "img:1"})
    assert "cc.api_key" not in done          # 掩码跳过
    assert "cc.image" in done
    written.update({k: rows[k].value_enc for k in rows})
    assert written.get("cc.api_key", "") == ""
    assert written["cc.image"] == "enc:img:1"

    assert "cc.api_key" in ss.set_many({"cc.api_key": "sk-real-value"})
