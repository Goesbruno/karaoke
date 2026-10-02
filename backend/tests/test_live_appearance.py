import pytest

from karaoke.application.live_session import LiveSession, SessionError
from karaoke.infrastructure.sqlite_store import SqliteStore


def make(tmp_path):
    session = LiveSession(SqliteStore(tmp_path / "db"), lambda: 1000)
    session.host(True)
    return session


def test_host_sets_appearance_and_it_persists(tmp_path):
    session = make(tmp_path)
    snap = session.command("host", "appearance", {"blur": 12, "opacity": 0.6})
    assert snap["blur"] == 12 and snap["bg_opacity"] == 0.6
    restarted = LiveSession(SqliteStore(tmp_path / "db"), lambda: 1000)
    assert restarted.snapshot()["blur"] == 12
    assert restarted.snapshot()["bg_opacity"] == 0.6


def test_partial_update_keeps_other_value(tmp_path):
    session = make(tmp_path)
    session.command("host", "appearance", {"blur": 8, "opacity": 0.5})
    snap = session.command("host", "appearance", {"opacity": 0.9})
    assert snap["blur"] == 8 and snap["bg_opacity"] == 0.9


def test_guest_cannot_change_appearance(tmp_path):
    session = make(tmp_path)
    with pytest.raises(SessionError):
        session.command("guest", "appearance", {"blur": 5})
    assert session.snapshot()["blur"] == 0


@pytest.mark.parametrize("value", [
    None, {}, {"blur": 31}, {"blur": -1}, {"blur": 2.5}, {"blur": True},
    {"opacity": 1.1}, {"opacity": -0.1}, {"opacity": "x"}, {"other": 1},
    {"blur": 5, "opacity": 2},
])
def test_invalid_appearance_changes_nothing(tmp_path, value):
    session = make(tmp_path)
    with pytest.raises(SessionError):
        session.command("host", "appearance", value)
    snap = session.snapshot()
    assert snap["blur"] == 0 and snap["bg_opacity"] == 1.0
