from pathlib import Path
import pytest
from karaoke.application.separation import SeparationError
from karaoke.infrastructure.local_files import LocalFileStore
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.worker import build_processor
from karaoke.config import Settings
from karaoke.separation_config import ROOT, SeparatorSettings


def test_paths_resolve_from_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KARAOKE_SEPARATOR_CMD", raising=False)
    monkeypatch.delenv("KARAOKE_MODEL_DIR", raising=False)
    settings = SeparatorSettings.from_env()
    assert Path(settings.cmd).is_relative_to(ROOT)
    assert settings.model_dir == ROOT / "models"
    assert "sep-test" not in str(settings.cmd)


@pytest.mark.parametrize("name, value", [
    ("KARAOKE_SEPARATOR_CMD", "../sep-test/.venv/Scripts/audio-separator.exe"),
    ("KARAOKE_MODEL_DIR", "../sep-test/models"),
    ("KARAOKE_BVE_MODEL_FILE", "../outside.pth"),
])
def test_reject_external_paths(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        SeparatorSettings.from_env()


def test_worker_requires_local_executable_before_models(monkeypatch, tmp_path):
    monkeypatch.setenv("KARAOKE_SEPARATOR_CMD", ".venv-separator/Scripts/missing-separator.exe")
    monkeypatch.setenv("KARAOKE_MODEL_DIR", "models")
    settings = Settings(data_dir=tmp_path)
    with pytest.raises(SeparationError, match="Ambiente local"):
        build_processor(settings, LocalFileStore(tmp_path))
