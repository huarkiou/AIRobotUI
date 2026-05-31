"""Configuration dialog for TrayForge — dynamic process list editor."""

import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import ImageTk
from icon import get_app_icon
from config import load_config, save_config, get_default_config
from startup import enable_autostart, disable_autostart, is_autostart_enabled
from logger import get_main_logger
from trayforge_types import AppConfig


class ConfigDialog:
    def __init__(self, root: tk.Tk) -> None:
        self._logger = get_main_logger()
        self._result: dict | None = None
        self._root_was_hidden = False

        self.dialog = tk.Toplevel(root)
        self.dialog.title("TrayForge - Settings")
        self._tk_icon = ImageTk.PhotoImage(get_app_icon())
        self.dialog.iconphoto(True, self._tk_icon)
        self.dialog.geometry("650x520")
        self.dialog.resizable(False, False)
        self.dialog.transient(root)

        # Center relative to parent
        self.dialog.update_idletasks()
        px = root.winfo_x()
        py = root.winfo_y()
        pw = root.winfo_width()
        ph = root.winfo_height()
        dx = px + (pw - 650) // 2
        dy = py + (ph - 520) // 2
        self.dialog.geometry(f"650x520+{max(0, dx)}+{max(0, dy)}")

        root_was_hidden = not root.winfo_viewable()
        if root_was_hidden:
            root.deiconify()
            root.update_idletasks()
            self._root_was_hidden = True

        self.dialog.grab_set()

        self._blocking = load_config() is None
        if self._blocking:
            self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        else:
            self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._proc_entries: list[dict] = []
        self._build_ui()
        self._load_current_config()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Global settings (top) ---
        global_frame = ttk.LabelFrame(main_frame, text="Global", padding=5)
        global_frame.pack(fill=tk.X, pady=(0, 5))

        output_frame = ttk.Frame(global_frame)
        output_frame.pack(fill=tk.X, pady=2)
        ttk.Label(output_frame, text="Output refresh interval (ms):").pack(side=tk.LEFT)
        self.output_refresh_var = tk.StringVar(value="500")
        ttk.Spinbox(
            output_frame,
            textvariable=self.output_refresh_var,
            from_=100,
            to=5000,
            increment=100,
            width=6,
        ).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(output_frame, text="(lower = smoother, higher = less CPU)").pack(
            side=tk.LEFT, padx=(5, 0)
        )

        self.autostart_var = tk.BooleanVar()
        ttk.Checkbutton(
            global_frame,
            text="Start TrayForge with Windows (autostart)",
            variable=self.autostart_var,
        ).pack(anchor=tk.W, pady=2)

        poll_frame = ttk.Frame(global_frame)
        poll_frame.pack(fill=tk.X, pady=2)
        ttk.Label(poll_frame, text="Crash poll interval (ms):").pack(side=tk.LEFT)
        self.poll_interval_var = tk.StringVar(value="2000")
        ttk.Spinbox(
            poll_frame,
            textvariable=self.poll_interval_var,
            from_=500,
            to=10000,
            increment=500,
            width=6,
        ).pack(side=tk.LEFT, padx=(5, 0))

        # --- Processes header + add button ---
        proc_header = ttk.Frame(main_frame)
        proc_header.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(proc_header, text="Processes", font=("Microsoft YaHei", 9, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Button(proc_header, text="Add Process", command=self._add_process).pack(side=tk.RIGHT)

        # Scrollable process list (wrapped so scrollbar doesn't extend past buttons)
        list_container = ttk.Frame(main_frame)
        list_container.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        canvas = tk.Canvas(list_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        self._proc_frame = ttk.Frame(canvas)
        self._proc_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._canvas_window = canvas.create_window((0, 0), window=self._proc_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_canvas_resize(event):
            canvas.itemconfig(self._canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_resize, add="+")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # Buttons (bottom-right, below scroll area)
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side=tk.RIGHT, padx=(5, 0))
        if not self._blocking:
            ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

    # --- Process row construction ---

    def _build_process_row(self, frame: ttk.LabelFrame, defaults: dict) -> dict[str, tk.Variable]:
        """Populate a LabelFrame with process config widgets. Returns vars dict.
        Does NOT pack the frame — caller is responsible for that.
        """
        v: dict[str, tk.Variable] = {}

        # Row 0: Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=1)
        v["name"] = tk.StringVar(value=defaults["name"])
        ttk.Entry(frame, textvariable=v["name"], width=20).grid(
            row=0, column=1, sticky=tk.W, padx=5
        )

        # Row 1: CWD
        ttk.Label(frame, text="CWD:").grid(row=1, column=0, sticky=tk.W, pady=1)
        v["cwd"] = tk.StringVar(value=defaults["cwd"])
        ttk.Entry(frame, textvariable=v["cwd"], width=50).grid(
            row=1, column=1, sticky=tk.EW, padx=5
        )
        ttk.Button(frame, text="...", width=3, command=lambda: self._browse_dir(v["cwd"])).grid(
            row=1, column=2
        )

        # Row 2: Cmd
        ttk.Label(frame, text="Cmd:").grid(row=2, column=0, sticky=tk.W, pady=1)
        v["cmd"] = tk.StringVar(value=defaults["cmd"])
        ttk.Entry(frame, textvariable=v["cmd"], width=50).grid(
            row=2, column=1, sticky=tk.EW, padx=(5, 0)
        )
        ttk.Button(
            frame, text="...", width=3, command=lambda var=v["cmd"]: self._edit_cmd(var)
        ).grid(row=2, column=2)

        # Row 3: Encoding
        ttk.Label(frame, text="Encoding:").grid(row=3, column=0, sticky=tk.W, pady=1)
        v["encoding"] = tk.StringVar(value=defaults["encoding"])
        ttk.Combobox(
            frame,
            textvariable=v["encoding"],
            values=["utf-8", "gbk", "gb2312", "cp936", "shift_jis", "latin-1"],
            width=12,
            state="readonly",
        ).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Row 4: Singleton, Autostart, Cleanup CWD
        check_frame = ttk.Frame(frame)
        check_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=2)
        v["singleton"] = tk.BooleanVar(value=defaults["singleton"])
        ttk.Checkbutton(check_frame, text="Singleton", variable=v["singleton"]).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        v["autostart"] = tk.BooleanVar(value=defaults["autostart"])
        ttk.Checkbutton(check_frame, text="Autostart", variable=v["autostart"]).pack(side=tk.LEFT)
        v["cleanup_cwd"] = tk.BooleanVar(value=defaults["cleanup_cwd"])
        ttk.Checkbutton(check_frame, text="Cleanup CWD", variable=v["cleanup_cwd"]).pack(
            side=tk.LEFT, padx=(10, 0)
        )

        # Row 5: WebUI Pattern
        ttk.Label(frame, text="WebUI Pattern:").grid(row=5, column=0, sticky=tk.W, pady=1)
        v["webui_pattern"] = tk.StringVar(value=defaults["webui_pattern"])
        ttk.Entry(frame, textvariable=v["webui_pattern"], width=50).grid(
            row=5, column=1, columnspan=2, sticky=tk.EW, padx=5
        )

        # Row 6: Delete before start
        ttk.Label(frame, text="Delete files:").grid(row=6, column=0, sticky=tk.W, pady=1)
        v["delete_before_start"] = tk.StringVar(value=defaults["delete_before_start"])
        ttk.Entry(frame, textvariable=v["delete_before_start"], width=50).grid(
            row=6, column=1, columnspan=2, sticky=tk.EW, padx=5
        )
        ttk.Label(frame, text="(comma-separated, relative to CWD)", foreground="gray").grid(
            row=7, column=1, columnspan=2, sticky=tk.W, padx=5
        )

        # Row 8: Action buttons (Copy, ▲, ▼, Delete)
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=3, sticky=tk.E, pady=(5, 0))
        ttk.Button(btn_frame, text="▲", width=3, command=lambda f=frame: self._move_up(f)).pack(
            side=tk.LEFT, padx=(0, 2)
        )
        ttk.Button(btn_frame, text="▼", width=3, command=lambda f=frame: self._move_down(f)).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(btn_frame, text="Copy", command=lambda f=frame: self._copy_process(f)).pack(
            side=tk.LEFT, padx=(0, 2)
        )
        ttk.Button(btn_frame, text="Delete", command=lambda f=frame: self._delete_process(f)).pack(
            side=tk.LEFT
        )

        frame.columnconfigure(1, weight=1)
        return v

    # --- Process list manipulation ---

    def _find_index(self, frame: ttk.Frame) -> int | None:
        for i, entry in enumerate(self._proc_entries):
            if entry["frame"] is frame:
                return i
        return None

    def _renumber(self) -> None:
        for i, entry in enumerate(self._proc_entries):
            entry["frame"].configure(text=f"Process {i + 1}")

    def _repack(self) -> None:
        """Re-pack all frames in list order (for after insert/swap)."""
        for entry in self._proc_entries:
            entry["frame"].pack_forget()
        for entry in self._proc_entries:
            entry["frame"].pack(fill=tk.X, pady=2)
        self._proc_frame.update_idletasks()

    def _add_process(self, defaults: dict | None = None) -> None:
        if defaults is None:
            defaults = {
                "name": "",
                "cwd": "",
                "cmd": "",
                "encoding": "utf-8",
                "singleton": False,
                "autostart": False,
                "cleanup_cwd": False,
                "webui_pattern": "",
                "delete_before_start": "",
            }

        frame = ttk.LabelFrame(
            self._proc_frame,
            text=f"Process {len(self._proc_entries) + 1}",
            padding=5,
        )
        v = self._build_process_row(frame, defaults)
        frame.pack(fill=tk.X, pady=2)
        self._proc_entries.append({"frame": frame, "vars": v})

    def _insert_process(self, idx: int, defaults: dict) -> None:
        """Insert a new process entry at the given index, then renumber + repack."""
        frame = ttk.LabelFrame(self._proc_frame, padding=5)
        v = self._build_process_row(frame, defaults)
        self._proc_entries.insert(idx, {"frame": frame, "vars": v})
        self._renumber()
        self._repack()

    def _copy_process(self, frame: ttk.Frame) -> None:
        idx = self._find_index(frame)
        if idx is None:
            return
        v = self._proc_entries[idx]["vars"]
        defaults = {
            "name": v["name"].get(),
            "cwd": v["cwd"].get(),
            "cmd": v["cmd"].get(),
            "encoding": v["encoding"].get(),
            "singleton": v["singleton"].get(),
            "autostart": v["autostart"].get(),
            "cleanup_cwd": v["cleanup_cwd"].get(),
            "webui_pattern": v["webui_pattern"].get(),
            "delete_before_start": v["delete_before_start"].get(),
        }
        self._insert_process(idx + 1, defaults)

    def _move_up(self, frame: ttk.Frame) -> None:
        idx = self._find_index(frame)
        if idx is None or idx <= 0:
            return
        self._proc_entries[idx], self._proc_entries[idx - 1] = (
            self._proc_entries[idx - 1],
            self._proc_entries[idx],
        )
        self._renumber()
        self._repack()

    def _move_down(self, frame: ttk.Frame) -> None:
        idx = self._find_index(frame)
        if idx is None or idx >= len(self._proc_entries) - 1:
            return
        self._proc_entries[idx], self._proc_entries[idx + 1] = (
            self._proc_entries[idx + 1],
            self._proc_entries[idx],
        )
        self._renumber()
        self._repack()

    def _delete_process(self, frame: ttk.Frame) -> None:
        idx = self._find_index(frame)
        if idx is None:
            return
        frame.destroy()
        del self._proc_entries[idx]
        self._renumber()

    def _browse_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Select Working Directory")
        if path:
            var.set(path)

    def _edit_cmd(self, var: tk.StringVar) -> None:
        """Open a multi-line editor dialog for the command string."""
        dlg = tk.Toplevel(self.dialog)
        dlg.title("Edit Command")
        dlg.transient(self.dialog)
        dlg.geometry("640x220")
        dlg.resizable(True, True)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

        dlg.update_idletasks()
        px = self.dialog.winfo_x()
        py = self.dialog.winfo_y()
        pw = self.dialog.winfo_width()
        ph = self.dialog.winfo_height()
        dx = px + (pw - 640) // 2
        dy = py + (ph - 220) // 2
        dlg.geometry(f"640x220+{max(0, dx)}+{max(0, dy)}")

        # Buttons pinned to bottom, packed first
        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Label(btn_frame, text="Ctrl+Enter to save", foreground="gray").pack(side=tk.LEFT)

        def _on_save():
            # Collapse newlines to spaces: the Text widget allows multi-line
            # editing for readability, but the command itself is a single line.
            cmd = text.get("1.0", "end-1c").rstrip()
            var.set(cmd.replace("\n", " "))
            dlg.destroy()

        ttk.Button(btn_frame, text="Save", command=_on_save).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)

        # Text with scrollbar fills remaining space
        text_frame = ttk.Frame(dlg)
        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(
            text_frame,
            font=("Consolas", 10),
            wrap=tk.WORD,
            undo=True,
            yscrollcommand=scrollbar.set,
        )
        text.insert("1.0", var.get())
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        text.bind("<Control-Return>", lambda e: _on_save())
        text.focus_set()
        dlg.grab_set()
        dlg.wait_window()

    def _load_current_config(self) -> None:
        config = load_config()
        if config is None:
            config = get_default_config()

        for proc in config.get("processes", []):
            self._add_process(
                {
                    "name": proc["name"],
                    "cwd": proc.get("cwd", ""),
                    "cmd": proc.get("cmd", ""),
                    "encoding": proc.get("encoding", "utf-8"),
                    "singleton": proc.get("singleton", False),
                    "autostart": proc.get("autostart", False),
                    "cleanup_cwd": proc.get("cleanup_cwd", False),
                    "webui_pattern": proc.get("webui_pattern") or "",
                    "delete_before_start": ", ".join(proc.get("delete_before_start", [])),
                }
            )

        self.output_refresh_var.set(str(config.get("output_refresh_ms", 500)))
        self.poll_interval_var.set(str(config.get("poll_interval_ms", 2000)))
        self.autostart_var.set(is_autostart_enabled())

    def _validate(self) -> str | None:
        names: set[str] = set()
        for entry in self._proc_entries:
            v = entry["vars"]
            name = v["name"].get().strip()
            if not name:
                return "Process name cannot be empty."
            if name in names:
                return f"Duplicate process name: {name}"
            names.add(name)
            if "/" in name or "\\" in name:
                return f"Process name cannot contain path separators: {name}"
            cwd = v["cwd"].get().strip()
            if cwd and not os.path.exists(cwd):
                self._logger.warning(
                    "CWD not found for '%s': %s (allowed, may be created later)", name, cwd
                )
            if not v["cmd"].get().strip():
                return f"Command is required for '{name}'."
            webui = v["webui_pattern"].get().strip()
            if webui:
                try:
                    re.compile(webui)
                except re.error as e:
                    return f"Invalid regex in WebUI Pattern for '{name}': {e}"
        return None

    def _on_save(self) -> None:
        error = self._validate()
        if error:
            messagebox.showerror("Validation Error", error, parent=self.dialog)
            return

        processes = []
        for entry in self._proc_entries:
            v = entry["vars"]
            delete_files = [
                f.strip() for f in v["delete_before_start"].get().split(",") if f.strip()
            ]
            processes.append(
                {
                    "name": v["name"].get().strip(),
                    "cwd": v["cwd"].get().strip(),
                    "cmd": v["cmd"].get().strip(),
                    "encoding": v["encoding"].get().strip(),
                    "singleton": v["singleton"].get(),
                    "autostart": v["autostart"].get(),
                    "cleanup_cwd": v["cleanup_cwd"].get(),
                    "webui_pattern": v["webui_pattern"].get().strip() or None,
                    "delete_before_start": delete_files,
                }
            )

        config = {
            "processes": processes,
            "output_refresh_ms": int(self.output_refresh_var.get()),
            "poll_interval_ms": int(self.poll_interval_var.get()),
            "autostart": self.autostart_var.get(),
        }

        if save_config(config):
            self._logger.info("Config saved via settings dialog")
            if config["autostart"]:
                enable_autostart()
            else:
                disable_autostart()
            self._result = config
            self._on_close()
        else:
            messagebox.showerror("Error", "Failed to save configuration.", parent=self.dialog)

    def _on_close(self) -> None:
        if self._root_was_hidden:
            self.dialog.master.withdraw()
        self.dialog.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        self._on_close()

    def lift_to_front(self) -> None:
        self.dialog.grab_set()
        self.dialog.lift()
        self.dialog.focus_force()

    def get_result(self) -> AppConfig | None:
        self.dialog.wait_window()
        return self._result
