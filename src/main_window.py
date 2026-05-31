"""Main window with dynamic tabs for all managed processes."""

import tkinter as tk
from tkinter import ttk
from PIL import ImageTk
from icon import get_app_icon, save_ico
from config import get_data_dir
from logger import get_main_logger
import sys
import os

MAX_LINES = 5000


class MainWindow:
    def __init__(self) -> None:
        # Taskbar icon fix: must be set BEFORE Tk() on Windows
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TrayForge")

        self.root = tk.Tk()
        self.root.title("TrayForge - Process Control")
        self._tk_icon = ImageTk.PhotoImage(get_app_icon())
        self.root.iconphoto(True, self._tk_icon)

        # Taskbar icon via .ico file
        if sys.platform == "win32":
            ico_path = os.path.join(get_data_dir(), "icon.ico")
            save_ico(ico_path)
            self.root.iconbitmap(default=ico_path)

        self.root.geometry("800x500")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 800) // 2
        y = (sh - 500) // 2
        self.root.geometry(f"800x500+{x}+{y}")

        # Notebook (tabs) — dynamic, populated by set_processes()
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._tabs: dict[str, tk.Text] = {}  # name -> Text widget

        self._visible = False
        self._close_callback: callable | None = None
        self._logger = get_main_logger()

        self.root.withdraw()

    def set_processes(self, names: list[str]) -> None:
        """Rebuild tabs to match the given process name list. Preserves existing tabs."""
        # Remove tabs not in names — use notebook API to find tabs by name
        for tab_id in self.notebook.tabs():
            tab_name = self.notebook.tab(tab_id, "text")
            if tab_name not in names:
                self.notebook.forget(tab_id)
                if tab_name in self._tabs:
                    del self._tabs[tab_name]

        # Add new tabs
        for name in names:
            if name not in self._tabs:
                frame = ttk.Frame(self.notebook)
                self.notebook.add(frame, text=name)
                text = self._create_text_widget(frame)
                self._tabs[name] = text

    def _create_text_widget(self, parent: ttk.Frame) -> tk.Text:
        """Create a read-only text widget with Clear button at bottom."""
        frame = tk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(
            text_frame,
            bg="white",
            fg="black",
            insertbackground="black",
            font=("Microsoft YaHei", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            yscrollcommand=scrollbar.set,
        )
        text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        context_menu = tk.Menu(text, tearoff=0)
        context_menu.add_command(label="Clear", command=lambda t=text: self._clear_tab(t))
        context_menu.add_command(label="Copy", command=lambda t=text: self._copy_selection(t))
        text.bind(
            "<Button-3>",
            lambda e, m=context_menu: m.tk_popup(e.x_root, e.y_root),
        )

        return text

    def _clear_tab(self, text: tk.Text) -> None:
        text.config(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.config(state=tk.DISABLED)

    def _copy_selection(self, text: tk.Text) -> None:
        try:
            sel = text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)
        except tk.TclError:
            pass

    def set_on_close(self, callback: callable) -> None:
        self._close_callback = callback

    def _on_close(self) -> None:
        self.root.withdraw()
        self._visible = False
        self._logger.info("Main window hidden")
        if self._close_callback:
            self._close_callback()

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._visible = True
        self._logger.info("Main window shown")

    def hide(self) -> None:
        self.root.withdraw()
        self._visible = False

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    def is_visible(self) -> bool:
        return self._visible

    def append_output(self, process_name: str, line: str) -> None:
        self.root.after(0, self._append_output_impl, process_name, line)

    def _append_output_impl(self, process_name: str, line: str) -> None:
        text = self._tabs.get(process_name)
        if text is None:
            return

        text.config(state=tk.NORMAL)
        text.insert(tk.END, line + "\n")

        line_count = int(text.index("end-1c").split(".")[0])
        if line_count > MAX_LINES:
            excess = line_count - MAX_LINES
            text.delete("1.0", f"{excess}.0")

        text.config(state=tk.DISABLED)
        text.see(tk.END)

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
