"""Tests for config.py — load, save, defaults, backup."""

import json
import os

from config import get_default_config, load_config, save_config, _prune_backups


def test_default_config_structure():
    cfg = get_default_config()
    assert "processes" in cfg
    assert "output_refresh_ms" in cfg
    assert "poll_interval_ms" in cfg
    assert "autostart" in cfg
    assert isinstance(cfg["processes"], list)
    assert cfg["output_refresh_ms"] == 500
    assert cfg["poll_interval_ms"] == 2000
    assert cfg["autostart"] is False


def test_default_config_returns_fresh_copy_each_time():
    cfg1 = get_default_config()
    cfg2 = get_default_config()
    assert cfg1 is not cfg2
    assert cfg1["processes"] is not cfg2["processes"]


def test_load_config_missing_file():
    import config as config_module

    original = config_module.get_data_dir

    def fake_dir():
        return "/nonexistent/path"

    config_module.get_data_dir = fake_dir
    try:
        result = load_config()
        assert result is None
    finally:
        config_module.get_data_dir = original


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    import config as config_module

    monkeypatch.setattr(config_module, "get_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(config_module, "_get_config_path", lambda: str(tmp_path / "config.json"))

    cfg = get_default_config()
    cfg["output_refresh_ms"] = 999
    assert save_config(cfg) is True

    loaded = load_config()
    assert loaded is not None
    assert loaded["output_refresh_ms"] == 999
    assert len(loaded["processes"]) == len(cfg["processes"])


class TestBackup:
    def test_creates_backup_on_save(self, tmp_path, monkeypatch):
        import config as config_module

        config_path = tmp_path / "config.json"
        monkeypatch.setattr(config_module, "get_data_dir", lambda: str(tmp_path))
        monkeypatch.setattr(config_module, "_get_config_path", lambda: str(config_path))

        # First save: no backup (config.json doesn't exist yet)
        cfg = get_default_config()
        save_config(cfg)
        backup_dir = tmp_path / "backups"
        assert not backup_dir.exists()

        # Second save: backup created
        cfg["output_refresh_ms"] = 300
        save_config(cfg)
        assert backup_dir.exists()
        backups = list(backup_dir.iterdir())
        assert len(backups) == 1
        assert backups[0].name.startswith("config.")

        # Verify backup content matches original (before modification)
        with open(backups[0], encoding="utf-8") as f:
            backup_data = json.load(f)
        assert backup_data["output_refresh_ms"] == 500  # original value

    def test_multiple_backups(self, tmp_path, monkeypatch):
        import config as config_module

        config_path = tmp_path / "config.json"
        monkeypatch.setattr(config_module, "get_data_dir", lambda: str(tmp_path))
        monkeypatch.setattr(config_module, "_get_config_path", lambda: str(config_path))

        cfg = get_default_config()
        for i in range(6):
            cfg["output_refresh_ms"] = i * 100
            save_config(cfg)

        # 6 saves = 5 backups (first save has no prior file to backup)
        backups = list((tmp_path / "backups").iterdir())
        assert len(backups) == 5

    def test_prune_when_over_limit(self, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create 5 fake backup files, each ~3MB (total ~15MB, over 10MB limit)
        import logging

        logger = logging.getLogger("test")
        chunk = b"x" * (3 * 1024 * 1024)
        paths = []
        for ts in [
            "2026-01-01-000000-000",
            "2026-02-01-000000-000",
            "2026-03-01-000000-000",
            "2026-04-01-000000-000",
            "2026-05-01-000000-000",
        ]:
            path = backup_dir / f"config.{ts}.json"
            with open(path, "wb") as f:
                f.write(chunk)
            paths.append(path)

        _prune_backups(str(backup_dir), logger)

        remaining = sorted(os.listdir(backup_dir))
        # Oldest two (~6MB) should be pruned, 3 remaining (~9MB) < 10MB
        assert len(remaining) == 3
        assert "config.2026-01-01-000000-000.json" not in remaining
        assert "config.2026-02-01-000000-000.json" not in remaining
