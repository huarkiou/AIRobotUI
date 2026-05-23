"""Tests for CLI argument parsing and HTTP request dispatch."""

from unittest.mock import MagicMock, patch
import pytest
from cli import build_parser, main, get_port


class TestArgParsing:
    def test_list_command(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_status_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["status", "NapCat"])
        assert args.command == "status"
        assert args.name == "NapCat"

    def test_start_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["start", "AstrBot"])
        assert args.command == "start"
        assert args.name == "AstrBot"

    def test_stop_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["stop", "NapCat"])
        assert args.command == "stop"
        assert args.name == "NapCat"

    def test_restart_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["restart", "NapCat"])
        assert args.command == "restart"
        assert args.name == "NapCat"

    def test_webui_command_with_name(self):
        parser = build_parser()
        args = parser.parse_args(["webui", "NapCat"])
        assert args.command == "webui"
        assert args.name == "NapCat"

    def test_reload_command(self):
        parser = build_parser()
        args = parser.parse_args(["reload"])
        assert args.command == "reload"

    def test_help_flag(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_name_required_for_status(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["status"])


class TestGetPort:
    def test_returns_port_when_file_exists(self, tmp_path, monkeypatch):
        port_file = tmp_path / "cli_port.txt"
        port_file.write_text("12345")
        monkeypatch.setattr("cli.get_data_dir", lambda: str(tmp_path))
        assert get_port() == 12345

    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.get_data_dir", lambda: str(tmp_path))
        assert get_port() is None

    def test_returns_none_for_invalid_content(self, tmp_path, monkeypatch):
        port_file = tmp_path / "cli_port.txt"
        port_file.write_text("not-a-number")
        monkeypatch.setattr("cli.get_data_dir", lambda: str(tmp_path))
        assert get_port() is None


class TestCLIMain:
    def test_list_command_dispatches_correctly(self):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.return_value = (200, "NapCat    Running\nAstrBot   Stopped")
            result = main(["list"])
            assert result == 0
            mock_send.assert_called_once_with(12345, "/list")

    def test_start_command_dispatches_correctly(self):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.return_value = (200, "NapCat started")
            result = main(["start", "NapCat"])
            assert result == 0
            mock_send.assert_called_once_with(12345, "/start", method="POST", name="NapCat")

    def test_status_command_dispatches_correctly(self):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.return_value = (200, "Name: NapCat\nStatus: Running")
            result = main(["status", "NapCat"])
            assert result == 0
            mock_send.assert_called_once_with(12345, "/status", name="NapCat")

    def test_help_outputs_usage(self, capsys):
        result = main(["--help"])
        captured = capsys.readouterr()
        assert "usage:" in captured.out
        assert result == 0

    def test_no_args_outputs_usage(self, capsys):
        result = main([])
        captured = capsys.readouterr()
        assert "usage:" in captured.out
        assert result == 1

    def test_trayforge_not_running(self, capsys):
        with patch("cli.get_port", return_value=None):
            result = main(["list"])
            captured = capsys.readouterr()
            assert "TrayForge is not running" in captured.out
            assert result == 1

    def test_connection_refused(self, capsys):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.side_effect = ConnectionRefusedError
            result = main(["list"])
            captured = capsys.readouterr()
            assert "TrayForge is not running" in captured.out
            assert result == 1

    def test_error_status_code_returns_1(self, capsys):
        with patch("cli.get_port", return_value=12345), patch("cli.send_request") as mock_send:
            mock_send.return_value = (404, "Unknown process: Ghost")
            result = main(["status", "Ghost"])
            assert result == 1
