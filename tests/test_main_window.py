"""Tests for main_window.py — dynamic tab management."""

import tkinter as tk
import pytest
from main_window import MainWindow


@pytest.fixture(scope="module")
def window():
    """Create a hidden MainWindow for testing (module scope to avoid Tcl init flaky)."""
    win = MainWindow()
    yield win
    try:
        win.destroy()
    except tk.TclError:
        pass


class TestSetProcesses:
    def test_adds_new_tabs(self, window):
        window.set_processes(["A", "B"])
        assert set(window._tabs.keys()) == {"A", "B"}
        assert len(window.notebook.tabs()) == 2

    def test_removes_old_tabs(self, window):
        window.set_processes(["A", "B", "C"])
        window.set_processes(["A"])
        assert set(window._tabs.keys()) == {"A"}
        assert len(window.notebook.tabs()) == 1
        assert window.notebook.tab(window.notebook.tabs()[0], "text") == "A"

    def test_preserves_existing_tabs(self, window):
        window.set_processes(["A", "B"])
        tab_a_before = window._tabs["A"]
        window.set_processes(["A", "B", "C"])
        assert window._tabs["A"] is tab_a_before  # same widget preserved
        assert set(window._tabs.keys()) == {"A", "B", "C"}

    def test_empty_list_clears_all(self, window):
        window.set_processes(["A", "B"])
        window.set_processes([])
        assert len(window._tabs) == 0
        assert len(window.notebook.tabs()) == 0

    def test_rename_preserves_widget(self, window):
        """Renaming 'A' to 'X': old tab removed, new tab added."""
        window.set_processes(["A", "B"])
        old_widget_a = window._tabs["A"]
        window.set_processes(["X", "B"])
        assert "A" not in window._tabs
        assert "X" in window._tabs
        assert window._tabs["X"] is not old_widget_a
        assert "B" in window._tabs

    def test_subset_preserves_remaining(self, window):
        window.set_processes(["A", "B", "C"])
        window.set_processes(["B"])
        assert set(window._tabs.keys()) == {"B"}
        assert len(window.notebook.tabs()) == 1
        assert window.notebook.tab(window.notebook.tabs()[0], "text") == "B"


class TestAppendOutput:
    def test_writes_to_correct_tab(self, window):
        window.set_processes(["A", "B"])
        window._append_output_impl("A", "hello")
        text_a = window._tabs["A"]
        # _append_output_impl appends line + "\n"
        assert text_a.get("1.0", "end-1c").rstrip("\n") == "hello"

    def test_ignores_unknown_process(self, window):
        window.set_processes(["A"])
        window._append_output_impl("B", "hello")  # should not raise

    def test_trims_old_lines(self, window, monkeypatch):
        import main_window as mw

        monkeypatch.setattr(mw, "MAX_LINES", 4)
        window.set_processes(["A"])
        text = window._tabs["A"]
        for i in range(6):
            window._append_output_impl("A", f"line {i}")
        # After 6 inserts with MAX_LINES=4, oldest 2 lines trimmed
        content = text.get("1.0", "end-1c").rstrip("\n")
        lines = content.split("\n")
        assert lines[0] == "line 2"
        assert lines[-1] == "line 5"


class TestVisibility:
    def test_hide_and_show(self, window):
        window.show()
        assert window.is_visible() is True
        window.hide()
        assert window.is_visible() is False

    def test_toggle(self, window):
        assert window.is_visible() is False
        window.toggle()
        assert window.is_visible() is True
        window.toggle()
        assert window.is_visible() is False
