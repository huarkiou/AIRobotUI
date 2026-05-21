"""Tests for config.py — load, save, migrate, defaults."""

from config import get_default_config, load_config, save_config, _migrate_old_config


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


def test_migrate_old_config():
    old = {
        "napcat": {"cwd": "/nap", "cmd": "nc.exe"},
        "astrbot": {"cwd": "/ast", "cmd": "ab.exe", "encoding": "gbk"},
        "output_refresh_ms": 300,
        "autostart": True,
    }
    new = _migrate_old_config(old)
    assert len(new["processes"]) == 2
    napcat = next(p for p in new["processes"] if p["name"] == "NapCat")
    assert napcat["cwd"] == "/nap"
    assert napcat["cmd"] == "nc.exe"
    assert napcat["singleton"] is True
    astrbot = next(p for p in new["processes"] if p["name"] == "AstrBot")
    assert astrbot["cwd"] == "/ast"
    assert astrbot["cmd"] == "ab.exe"
    assert astrbot["encoding"] == "gbk"
    assert astrbot["delete_before_start"] == ["astrbot.lock"]
    assert new["output_refresh_ms"] == 300
    assert new["autostart"] is True


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
