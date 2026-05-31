"""Tests for config_ui.py — settings dialog, process list manipulation."""

import tkinter as tk
from unittest.mock import patch
import pytest
import config_ui
from config_ui import ConfigDialog


@pytest.fixture(scope="module")
def root():
    """Shared hidden Tk root for all config_ui tests (module scope to avoid Tcl init flaky)."""
    r = tk.Tk()
    r.withdraw()
    yield r
    try:
        r.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def dlg(root):
    """ConfigDialog with default entries cleared, no disk I/O."""
    with patch.object(config_ui, "load_config", return_value=None):
        with patch.object(config_ui, "is_autostart_enabled", return_value=False):
            d = ConfigDialog(root)
            # Clear preloaded default entries so tests start clean
            for entry in list(d._proc_entries):
                entry["frame"].destroy()
            d._proc_entries.clear()
            yield d
            try:
                d._on_close()
            except tk.TclError:
                pass


def _add_entry(dlg, name="TestProc", cmd="echo hello"):
    """Helper: add a process entry and return its frame."""
    dlg._add_process(
        {
            "name": name,
            "cwd": "D:/test",
            "cmd": cmd,
            "encoding": "utf-8",
            "singleton": True,
            "autostart": False,
            "cleanup_cwd": False,
            "webui_pattern": "",
            "delete_before_start": "",
        }
    )
    return dlg._proc_entries[-1]["frame"]


# --- Logic methods ---


class TestFindIndex:
    def test_finds_existing_frame(self, dlg):
        f1 = _add_entry(dlg, "A")
        f2 = _add_entry(dlg, "B")
        assert dlg._find_index(f1) == 0
        assert dlg._find_index(f2) == 1

    def test_returns_none_for_unknown(self, dlg):
        fake = tk.Frame(dlg.dialog)
        assert dlg._find_index(fake) is None

    def test_returns_none_for_empty(self, dlg):
        assert dlg._find_index(tk.Frame(dlg.dialog)) is None


class TestRenumber:
    def test_updates_labels(self, dlg):
        f1 = _add_entry(dlg, "A")
        f2 = _add_entry(dlg, "B")
        dlg._renumber()
        assert f1.cget("text") == "Process 1"
        assert f2.cget("text") == "Process 2"

    def test_handles_empty_list(self, dlg):
        dlg._renumber()  # should not raise


class TestValidate:
    def test_empty_name_fails(self, dlg):
        _add_entry(dlg, "")
        assert dlg._validate() == "Process name cannot be empty."

    def test_duplicate_name_fails(self, dlg):
        _add_entry(dlg, "A")
        _add_entry(dlg, "A")
        assert "Duplicate" in dlg._validate()

    def test_path_separator_in_name_fails(self, dlg):
        _add_entry(dlg, "a/b")
        assert "path separator" in dlg._validate()
        dlg._proc_entries.clear()
        _add_entry(dlg, "a\\b")
        assert "path separator" in dlg._validate()

    def test_empty_cmd_fails(self, dlg):
        _add_entry(dlg, "A", cmd="")
        assert "Command is required" in dlg._validate()

    def test_invalid_webui_pattern_fails(self, dlg):
        dlg._add_process(
            {
                "name": "A",
                "cwd": "",
                "cmd": "x",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "cleanup_cwd": False,
                "webui_pattern": "[invalid",
                "delete_before_start": "",
            }
        )
        assert "Invalid regex" in dlg._validate()

    def test_valid_config_passes(self, dlg):
        _add_entry(dlg, "A", cmd="echo hi")
        assert dlg._validate() is None

    def test_missing_cwd_allowed(self, dlg):
        _add_entry(dlg, "A", cmd="echo hi")
        dlg._proc_entries[0]["vars"]["cwd"].set("/nonexistent/path")
        assert dlg._validate() is None  # warning only, not an error


class TestOnSave:
    def test_produces_correct_config(self, dlg):
        with patch.object(config_ui, "save_config", return_value=True):
            with patch.object(config_ui, "enable_autostart"):
                dlg._add_process(
                    {
                        "name": "Test",
                        "cwd": "D:/apps",
                        "cmd": "test.exe --flag",
                        "encoding": "gbk",
                        "singleton": True,
                        "autostart": True,
                        "cleanup_cwd": True,
                        "webui_pattern": "url: (https?://\\S+)",
                        "delete_before_start": "a.lock, b.lock",
                    }
                )
                dlg.output_refresh_var.set("300")
                dlg._on_save()
                result = dlg._result
                assert result is not None
                assert result["output_refresh_ms"] == 300
                proc = result["processes"][0]
                assert proc["name"] == "Test"
                assert proc["cwd"] == "D:/apps"
                assert proc["cmd"] == "test.exe --flag"
                assert proc["encoding"] == "gbk"
                assert proc["singleton"] is True
                assert proc["webui_pattern"] == "url: (https?://\\S+)"
                assert proc["delete_before_start"] == ["a.lock", "b.lock"]

    def test_empty_delete_files_handled(self, dlg):
        with patch.object(config_ui, "save_config", return_value=True):
            with patch.object(config_ui, "enable_autostart"):
                _add_entry(dlg, "A", cmd="x")
                dlg._proc_entries[0]["vars"]["delete_before_start"].set("")
                dlg._on_save()
                assert dlg._result["processes"][0]["delete_before_start"] == []

    def test_null_webui_pattern(self, dlg):
        with patch.object(config_ui, "save_config", return_value=True):
            with patch.object(config_ui, "enable_autostart"):
                _add_entry(dlg, "A", cmd="x")
                dlg._proc_entries[0]["vars"]["webui_pattern"].set("")
                dlg._on_save()
                assert dlg._result["processes"][0]["webui_pattern"] is None


# --- Process list manipulation ---


class TestDeleteProcess:
    def test_removes_entry(self, dlg):
        f = _add_entry(dlg, "A")
        assert len(dlg._proc_entries) == 1
        dlg._delete_process(f)
        assert len(dlg._proc_entries) == 0

    def test_renumbers_after_delete(self, dlg):
        f1 = _add_entry(dlg, "A")
        _add_entry(dlg, "B")
        dlg._delete_process(f1)
        assert dlg._proc_entries[0]["frame"].cget("text") == "Process 1"


class TestMoveUp:
    def test_swaps_order(self, dlg):
        f1 = _add_entry(dlg, "A")
        f2 = _add_entry(dlg, "B")
        dlg._move_up(f2)
        assert dlg._find_index(f2) == 0
        assert dlg._find_index(f1) == 1

    def test_first_element_noop(self, dlg):
        f1 = _add_entry(dlg, "A")
        _add_entry(dlg, "B")
        dlg._move_up(f1)
        assert dlg._find_index(f1) == 0


class TestMoveDown:
    def test_swaps_order(self, dlg):
        f1 = _add_entry(dlg, "A")
        f2 = _add_entry(dlg, "B")
        dlg._move_down(f1)
        assert dlg._find_index(f1) == 1
        assert dlg._find_index(f2) == 0

    def test_last_element_noop(self, dlg):
        _add_entry(dlg, "A")
        f2 = _add_entry(dlg, "B")
        dlg._move_down(f2)
        assert dlg._find_index(f2) == 1


class TestCopyProcess:
    def test_duplicates_entry(self, dlg):
        f = _add_entry(dlg, "Original", cmd="echo test")
        dlg._proc_entries[0]["vars"]["webui_pattern"].set("http://test")
        dlg._copy_process(f)
        assert len(dlg._proc_entries) == 2
        assert dlg._find_index(f) == 0  # original stays in place
        copy_vars = dlg._proc_entries[1]["vars"]
        assert copy_vars["name"].get() == "Original"
        assert copy_vars["cmd"].get() == "echo test"
        assert copy_vars["webui_pattern"].get() == "http://test"

    def test_copy_has_distinct_frame(self, dlg):
        f = _add_entry(dlg, "A")
        dlg._copy_process(f)
        assert dlg._proc_entries[0]["frame"] is not dlg._proc_entries[1]["frame"]


# --- Build process row ---


class TestBuildProcessRow:
    def test_creates_all_var_keys(self, dlg):
        frame = tk.LabelFrame(dlg.dialog)
        defaults = {
            "name": "T",
            "cwd": "",
            "cmd": "",
            "encoding": "utf-8",
            "singleton": False,
            "autostart": False,
            "cleanup_cwd": False,
            "webui_pattern": "",
            "delete_before_start": "",
        }
        v = dlg._build_process_row(frame, defaults)
        expected_keys = {
            "name",
            "cwd",
            "cmd",
            "encoding",
            "singleton",
            "autostart",
            "cleanup_cwd",
            "webui_pattern",
            "delete_before_start",
        }
        assert set(v.keys()) == expected_keys

    def test_defaults_set_correctly(self, dlg):
        frame = tk.LabelFrame(dlg.dialog)
        defaults = {
            "name": "MyProc",
            "cwd": "D:/path",
            "cmd": "run.bat",
            "encoding": "gbk",
            "singleton": True,
            "autostart": True,
            "cleanup_cwd": True,
            "webui_pattern": "http://x",
            "delete_before_start": "a.lock",
        }
        v = dlg._build_process_row(frame, defaults)
        assert v["name"].get() == "MyProc"
        assert v["cwd"].get() == "D:/path"
        assert v["cmd"].get() == "run.bat"
        assert v["encoding"].get() == "gbk"
        assert v["singleton"].get() is True
        assert v["autostart"].get() is True
        assert v["cleanup_cwd"].get() is True
        assert v["webui_pattern"].get() == "http://x"
        assert v["delete_before_start"].get() == "a.lock"
