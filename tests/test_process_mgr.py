"""Tests for process_mgr.py — config building, state management, crash recovery."""

from unittest.mock import patch, MagicMock
from process_mgr import ProcessManager


def _make_config(processes=None):
    if processes is None:
        processes = [
            {
                "name": "TestProc",
                "cwd": "",
                "cmd": "echo hello",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "webui_pattern": None,
                "delete_before_start": [],
            }
        ]
    return {
        "processes": processes,
        "output_refresh_ms": 500,
        "poll_interval_ms": 2000,
        "autostart": False,
    }


class TestBuildFromConfig:
    def test_adds_new_processes(self):
        pm = ProcessManager(_make_config())
        assert pm.process_names() == ["TestProc"]

    def test_preserves_existing_state_on_reconfig(self):
        cfg = _make_config()
        pm = ProcessManager(cfg)
        old_ps = pm._procs["TestProc"]

        cfg2 = _make_config(
            [
                {
                    "name": "TestProc",
                    "cwd": "/new/path",
                    "cmd": "echo world",
                    "encoding": "utf-8",
                    "singleton": False,
                    "autostart": False,
                    "webui_pattern": None,
                    "delete_before_start": [],
                }
            ]
        )
        pm.update_config(cfg2)
        assert pm.process_names() == ["TestProc"]
        assert pm._procs["TestProc"] is old_ps
        assert pm._procs["TestProc"].cfg["cwd"] == "/new/path"

    def test_removes_deleted_processes(self):
        cfg = _make_config()
        pm = ProcessManager(cfg)
        cfg2 = _make_config(
            [
                {
                    "name": "OtherProc",
                    "cwd": "",
                    "cmd": "echo",
                    "encoding": "utf-8",
                    "singleton": False,
                    "autostart": False,
                    "webui_pattern": None,
                    "delete_before_start": [],
                }
            ]
        )
        pm.update_config(cfg2)
        assert pm.process_names() == ["OtherProc"]
        assert "TestProc" not in pm._procs


class TestProcessState:
    def test_is_running_false_when_no_proc(self):
        pm = ProcessManager(_make_config())
        assert not pm.is_running("TestProc")

    def test_is_running_false_for_nonexistent(self):
        pm = ProcessManager(_make_config())
        assert not pm.is_running("Nonexistent")

    def test_has_webui_false_when_null(self):
        pm = ProcessManager(_make_config())
        assert not pm.has_webui("TestProc")

    def test_has_webui_true_when_pattern_set(self):
        cfg = _make_config(
            [
                {
                    "name": "WebProc",
                    "cwd": "",
                    "cmd": "echo",
                    "encoding": "utf-8",
                    "singleton": False,
                    "autostart": False,
                    "webui_pattern": "http://\\S+",
                    "delete_before_start": [],
                }
            ]
        )
        pm = ProcessManager(cfg)
        assert pm.has_webui("WebProc")

    def test_drain_returns_empty_for_nonexistent(self):
        pm = ProcessManager(_make_config())
        assert pm.drain("Nonexistent") == []

    def test_drain_returns_queued_messages(self):
        pm = ProcessManager(_make_config())
        ps = pm._procs["TestProc"]
        ps.msg_queue.put("msg1")
        ps.msg_queue.put("msg2")
        lines = pm.drain("TestProc")
        assert lines == ["msg1", "msg2"]
        assert pm.drain("TestProc") == []

    def test_system_msg_injects_timestamped_message(self):
        pm = ProcessManager(_make_config())
        pm._system_msg("TestProc", "hello world")
        lines = pm.drain("TestProc")
        assert len(lines) == 1
        assert "[SYSTEM] hello world" in lines[0]


class TestStartStop:
    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_start_empty_command_shows_error(self, mock_thread, mock_popen):
        cfg = _make_config(
            [
                {
                    "name": "BadProc",
                    "cwd": "",
                    "cmd": "",
                    "encoding": "utf-8",
                    "singleton": False,
                    "autostart": False,
                    "webui_pattern": None,
                    "delete_before_start": [],
                }
            ]
        )
        pm = ProcessManager(cfg)
        pm._start("BadProc")
        lines = pm.drain("BadProc")
        assert any("no command configured" in line.lower() for line in lines)

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_start_missing_cwd_shows_error(self, mock_thread, mock_popen):
        cfg = _make_config(
            [
                {
                    "name": "BadProc",
                    "cwd": "/definitely/not/a/real/path",
                    "cmd": "echo hello",
                    "encoding": "utf-8",
                    "singleton": False,
                    "autostart": False,
                    "webui_pattern": None,
                    "delete_before_start": [],
                }
            ]
        )
        pm = ProcessManager(cfg)
        pm._start("BadProc")
        lines = pm.drain("BadProc")
        assert any("working directory not found" in line.lower() for line in lines)

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_stop_stops_running_process(self, mock_thread, mock_popen, mock_run):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        cfg = _make_config()
        pm = ProcessManager(cfg)
        pm._start("TestProc")
        assert pm.is_running("TestProc")

        pm.stop("TestProc")
        assert not pm.is_running("TestProc")

    def test_start_all_and_stop_all(self):
        cfg = _make_config(
            [
                {
                    "name": "Proc1",
                    "cwd": "",
                    "cmd": "",
                    "encoding": "utf-8",
                    "singleton": False,
                    "autostart": False,
                    "webui_pattern": None,
                    "delete_before_start": [],
                },
                {
                    "name": "Proc2",
                    "cwd": "",
                    "cmd": "",
                    "encoding": "utf-8",
                    "singleton": False,
                    "autostart": False,
                    "webui_pattern": None,
                    "delete_before_start": [],
                },
            ]
        )
        pm = ProcessManager(cfg)
        pm.start_all()
        lines1 = pm.drain("Proc1")
        lines2 = pm.drain("Proc2")
        assert any("no command configured" in line.lower() for line in lines1)
        assert any("no command configured" in line.lower() for line in lines2)


class TestCrashPolling:
    def test_poll_crashes_ignores_none_proc(self):
        pm = ProcessManager(_make_config())
        pm.poll_crashes()

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_max_restarts_reached_stops_process(self, mock_thread, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = 1
        mock_popen.return_value = mock_proc

        cfg = _make_config()
        pm = ProcessManager(cfg)
        pm._start("TestProc")

        from process_mgr import MAX_RESTARTS

        pm._procs["TestProc"].restarts = MAX_RESTARTS
        pm.poll_crashes()

        assert pm._procs["TestProc"].proc is None
        lines = pm.drain("TestProc")
        assert any("max restart attempts" in line.lower() for line in lines)


class TestStatusListeners:
    def test_on_status_change_called_after_start_stop(self):
        pm = ProcessManager(_make_config())
        calls = []
        pm.on_status_change(lambda: calls.append(1))
        pm._emit_status()
        assert len(calls) == 1

    def test_failing_listener_does_not_block_others(self):
        pm = ProcessManager(_make_config())
        calls = []

        def failing():
            raise RuntimeError("boom")

        pm.on_status_change(failing)
        pm.on_status_change(lambda: calls.append(1))
        pm._emit_status()
        assert len(calls) == 1

    def test_on_notification_fires(self):
        pm = ProcessManager(_make_config())
        notes = []
        pm.on_notification(lambda t, m: notes.append((t, m)))
        pm._notify("Title", "Message")
        assert notes == [("Title", "Message")]


class TestGetStatus:
    def test_get_status_returns_none_for_unknown_process(self, pm):
        """pm fixture from conftest provides a ProcessManager with default config."""
        assert pm.get_status("nonexistent") is None

    def test_get_status_returns_dict_for_known_process(self, pm):
        status = pm.get_status("NapCat")
        assert status is not None
        assert status["name"] == "NapCat"
        assert status["running"] is False
        assert status["pid"] is None
        assert status["has_webui"] is True
        assert status["webui_url"] is None
        assert status["restarts"] == 0
        assert status["max_restarts"] == 3

    @patch("threading.Thread")
    def test_get_status_reflects_running_state(self, mock_thread, pm):
        # Status before start
        status = pm.get_status("NapCat")
        assert status["running"] is False

        # After start — mock Popen to avoid actually spawning
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            pm.start("NapCat")

        status = pm.get_status("NapCat")
        assert status["running"] is True
        assert status["pid"] == 12345
        assert status["restarts"] == 0
        assert status["has_webui"] is True
        assert status["max_restarts"] == 3
