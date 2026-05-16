"""Main window with two-tab output display for NapCat and AstrBot."""

import tkinter as tk
from tkinter import ttk
from logger import get_main_logger

MAX_LINES = 5000


class MainWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("AIRobotUI - Process Control")
        self.root.geometry("800x500")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 800) // 2
        y = (sh - 500) // 2
        self.root.geometry(f"800x500+{x}+{y}")

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # NapCat tab
        self.napcat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.napcat_frame, text="NapCat")
        self.napcat_text = self._create_text_widget(self.napcat_frame)

        # AstrBot tab
        self.astrbot_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.astrbot_frame, text="AstrBot")
        self.astrbot_text = self._create_text_widget(self.astrbot_frame)

        self._visible = False
        self._close_callback: callable | None = None
        self._logger = get_main_logger()

        # Start hidden (show only when user requests)
        self.root.withdraw()

    def _create_text_widget(self, parent: ttk.Frame) -> tk.Text:
        """Create a read-only text widget with Clear button."""
        frame = tk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)

        # Clear button
        toolbar = tk.Frame(frame)
        toolbar.pack(fill=tk.X)
        clear_btn = tk.Button(toolbar, text="Clear", command=lambda t=text: self._clear_tab(t))
        clear_btn.pack(side=tk.RIGHT, padx=2, pady=2)

        # Text area
        text_frame = tk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(
            text_frame,
            bg="white",
            fg="black",
            insertbackground="black",
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            yscrollcommand=scrollbar.set,
        )
        text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        # Right-click context menu
        context_menu = tk.Menu(text, tearoff=0)
        context_menu.add_command(
            label="Clear", command=lambda t=text: self._clear_tab(t)
        )
        context_menu.add_command(
            label="Copy", command=lambda t=text: self._copy_selection(t)
        )
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
            pass  # No selection

    def set_on_close(self, callback: callable) -> None:
        """Set callback for when user closes the window."""
        self._close_callback = callback

    def _on_close(self) -> None:
        """Hide window instead of closing."""
        self.root.withdraw()
        self._visible = False
        self._logger.info("Main window hidden")
        if self._close_callback:
            self._close_callback()

    def show(self) -> None:
        """Show and focus the window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._visible = True
        self._logger.info("Main window shown")

    def hide(self) -> None:
        """Hide the window."""
        self.root.withdraw()
        self._visible = False

    def toggle(self) -> None:
        """Toggle window visibility. If visible, flash to front then hide as cue."""
        if self._visible:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.after(150, self.hide)
        else:
            self.show()

    def is_visible(self) -> bool:
        return self._visible

    def append_output(self, process_name: str, line: str) -> None:
        """Append a line to the appropriate tab. Thread-safe via root.after."""
        self.root.after(0, self._append_output_impl, process_name, line)

    def _append_output_impl(self, process_name: str, line: str) -> None:
        """Actually append the output line (must run on main thread)."""
        if process_name == "NapCat":
            text = self.napcat_text
        elif process_name == "AstrBot":
            text = self.astrbot_text
        else:
            return

        text.config(state=tk.NORMAL)
        text.insert(tk.END, line + "\n")

        # Enforce line limit
        line_count = int(text.index("end-1c").split(".")[0])
        if line_count > MAX_LINES:
            excess = line_count - MAX_LINES
            text.delete("1.0", f"{excess}.0")

        text.config(state=tk.DISABLED)
        text.see(tk.END)

    def destroy(self) -> None:
        """Destroy the window."""
        try:
            self.root.destroy()
        except Exception:
            pass
