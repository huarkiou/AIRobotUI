"""Tests for startup.py — autostart registry management."""

import sys
from unittest.mock import patch, MagicMock
import startup


class TestGetExePath:
    def test_frozen_returns_executable(self):
        with patch.object(sys, "executable", "C:/Apps/TrayForge.exe"):
            with patch.object(sys, "frozen", True, create=True):
                result = startup._get_exe_path()
                assert result == "C:/Apps/TrayForge.exe"

    def test_dev_returns_python_with_script(self):
        with patch.object(sys, "executable", "C:/Python/python.exe"):
            with patch.object(sys, "frozen", False, create=True):
                result = startup._get_exe_path()
                assert "python.exe" in result
                assert "main.pyw" in result


class TestIsAutostartEnabled:
    def test_enabled_when_key_exists(self):
        mock_key = MagicMock()
        mock_key.__enter__.return_value = mock_key
        mock_key.__exit__.return_value = False

        with patch("winreg.OpenKey", return_value=mock_key):
            with patch("winreg.QueryValueEx") as mock_query:
                mock_query.return_value = ("C:/Apps/TrayForge.exe", 1)
                assert startup.is_autostart_enabled() is True

    def test_disabled_when_key_missing(self):
        with patch("winreg.OpenKey", side_effect=FileNotFoundError):
            assert startup.is_autostart_enabled() is False

    def test_disabled_on_os_error(self):
        with patch("winreg.OpenKey", side_effect=OSError):
            assert startup.is_autostart_enabled() is False


class TestEnableAutostart:
    def test_sets_value(self, monkeypatch):
        monkeypatch.setattr(startup, "_get_exe_path", lambda: "C:/Apps/TrayForge.exe")
        mock_key = MagicMock()

        with patch("winreg.OpenKey", return_value=mock_key):
            with patch("winreg.SetValueEx") as mock_set:
                assert startup.enable_autostart() is True
                mock_set.assert_called_once()

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(startup, "_get_exe_path", lambda: "C:/Apps/TrayForge.exe")
        with patch("winreg.OpenKey", side_effect=OSError):
            assert startup.enable_autostart() is False


class TestDisableAutostart:
    def test_deletes_value(self):
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key):
            with patch("winreg.DeleteValue") as mock_del:
                assert startup.disable_autostart() is True
                mock_del.assert_called_once()

    def test_returns_true_when_already_missing(self):
        with patch("winreg.OpenKey", side_effect=FileNotFoundError):
            assert startup.disable_autostart() is True

    def test_returns_false_on_os_error(self):
        with patch("winreg.OpenKey", side_effect=OSError):
            assert startup.disable_autostart() is False
