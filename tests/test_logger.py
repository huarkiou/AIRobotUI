"""Tests for logger.py — logger naming and sanitization."""

from logger import get_process_logger, get_main_logger


def test_get_main_logger_returns_same_instance():
    lg1 = get_main_logger()
    lg2 = get_main_logger()
    assert lg1 is lg2
    assert lg1.name == "trayforge.main"


def test_get_process_logger_name_sanitization():
    lg = get_process_logger("NapCat")
    assert lg.name.startswith("trayforge.process.")
    assert "NapCat" in lg.name


def test_get_process_logger_chinese_name():
    lg = get_process_logger("测试进程")
    assert lg.name.startswith("trayforge.process.")


def test_get_process_logger_special_chars():
    lg = get_process_logger("bad/name\\with:chars")
    assert "/" not in lg.name
    assert "\\" not in lg.name
    assert lg.name.startswith("trayforge.process.")


def test_get_process_logger_returns_same_for_same_name():
    lg1 = get_process_logger("MyProc")
    lg2 = get_process_logger("MyProc")
    assert lg1 is lg2
