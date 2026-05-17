"""Configuration dialog for AIRobotUI."""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import ImageTk
from icon import get_app_icon
from config import load_config, save_config, get_default_config
from startup import enable_autostart, disable_autostart, is_autostart_enabled
from logger import get_main_logger


class ConfigDialog:
    def __init__(self, root: tk.Tk) -> None:
        self._logger = get_main_logger()
        self._result: dict | None = None
        self._root_was_hidden = False

        self.dialog = tk.Toplevel(root)
        self.dialog.title("AIRobotUI - Settings")
        self._tk_icon = ImageTk.PhotoImage(get_app_icon())
        self.dialog.iconphoto(True, self._tk_icon)
        self.dialog.geometry("550x420")
        self.dialog.resizable(False, False)
        self.dialog.transient(root)

        # Center relative to parent
        self.dialog.update_idletasks()
        px = root.winfo_x()
        py = root.winfo_y()
        pw = root.winfo_width()
        ph = root.winfo_height()
        dx = px + (pw - 550) // 2
        dy = py + (ph - 420) // 2
        self.dialog.geometry(f"550x420+{max(0, dx)}+{max(0, dy)}")

        # Show root briefly so grab_set works, then re-hide after dialog closes
        root_was_hidden = not root.winfo_viewable()
        if root_was_hidden:
            root.deiconify()
            root.update_idletasks()
            self._root_was_hidden = True

        self.dialog.grab_set()

        # Prevent closing if no config exists (first run)
        self._blocking = load_config() is None
        if self._blocking:
            self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        else:
            self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._load_current_config()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- NapCat ---
        napcat_frame = ttk.LabelFrame(main_frame, text="NapCat QQ", padding=5)
        napcat_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(napcat_frame, text="Working Directory:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        self.napcat_cwd = tk.StringVar()
        ttk.Entry(napcat_frame, textvariable=self.napcat_cwd, width=40).grid(
            row=0, column=1, sticky=tk.EW, padx=(5, 2)
        )
        ttk.Button(
            napcat_frame,
            text="Browse...",
            command=lambda: self._browse_dir(self.napcat_cwd),
        ).grid(row=0, column=2)

        ttk.Label(napcat_frame, text="Command:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.napcat_cmd = tk.StringVar()
        ttk.Entry(napcat_frame, textvariable=self.napcat_cmd, width=40).grid(
            row=1, column=1, columnspan=2, sticky=tk.EW, padx=(5, 0)
        )

        ttk.Label(napcat_frame, text="Encoding:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.napcat_enc = tk.StringVar(value="utf-8")
        enc_combo_n = ttk.Combobox(
            napcat_frame,
            textvariable=self.napcat_enc,
            values=["utf-8", "gbk", "gb2312", "cp936", "shift_jis", "latin-1"],
            width=15,
            state="readonly",
        )
        enc_combo_n.grid(row=2, column=1, sticky=tk.W, padx=(5, 0))

        napcat_frame.columnconfigure(1, weight=1)

        # --- AstrBot ---
        astrbot_frame = ttk.LabelFrame(main_frame, text="AstrBot", padding=5)
        astrbot_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(astrbot_frame, text="Working Directory:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        self.astrbot_cwd = tk.StringVar()
        ttk.Entry(astrbot_frame, textvariable=self.astrbot_cwd, width=40).grid(
            row=0, column=1, sticky=tk.EW, padx=(5, 2)
        )
        ttk.Button(
            astrbot_frame,
            text="Browse...",
            command=lambda: self._browse_dir(self.astrbot_cwd),
        ).grid(row=0, column=2)

        ttk.Label(astrbot_frame, text="Command:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.astrbot_cmd = tk.StringVar()
        ttk.Entry(astrbot_frame, textvariable=self.astrbot_cmd, width=40).grid(
            row=1, column=1, columnspan=2, sticky=tk.EW, padx=(5, 0)
        )

        ttk.Label(astrbot_frame, text="Encoding:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.astrbot_enc = tk.StringVar(value="utf-8")
        enc_combo_a = ttk.Combobox(
            astrbot_frame,
            textvariable=self.astrbot_enc,
            values=["utf-8", "gbk", "gb2312", "cp936", "shift_jis", "latin-1"],
            width=15,
            state="readonly",
        )
        enc_combo_a.grid(row=2, column=1, sticky=tk.W, padx=(5, 0))

        astrbot_frame.columnconfigure(1, weight=1)

        # --- Autostart ---
        autostart_frame = ttk.Frame(main_frame)
        autostart_frame.pack(fill=tk.X, pady=(0, 5))
        self.autostart_var = tk.BooleanVar()
        ttk.Checkbutton(
            autostart_frame,
            text="Start with Windows (autostart)",
            variable=self.autostart_var,
        ).pack(anchor=tk.W)

        # --- Output refresh ---
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.X, pady=(0, 10))
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

        # --- Buttons ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side=tk.RIGHT, padx=(5, 0))
        if not self._blocking:
            ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

    def _browse_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Select Working Directory")
        if path:
            var.set(path)

    def _load_current_config(self) -> None:
        config = load_config()
        if config is None:
            config = get_default_config()

        self.napcat_cwd.set(config["napcat"]["cwd"])
        self.napcat_cmd.set(config["napcat"]["cmd"])
        self.napcat_enc.set(config["napcat"].get("encoding", "utf-8"))
        self.astrbot_cwd.set(config["astrbot"]["cwd"])
        self.astrbot_cmd.set(config["astrbot"]["cmd"])
        self.astrbot_enc.set(config["astrbot"].get("encoding", "gbk"))
        self.autostart_var.set(is_autostart_enabled())
        self.output_refresh_var.set(str(config.get("output_refresh_ms", 500)))

    def _validate(self) -> str | None:
        """Validate inputs. Returns error string or None if valid."""
        if not self.napcat_cwd.get().strip():
            return "NapCat working directory is required."
        if not self.napcat_cmd.get().strip():
            return "NapCat command is required."
        if not self.astrbot_cwd.get().strip():
            return "AstrBot working directory is required."
        if not self.astrbot_cmd.get().strip():
            return "AstrBot command is required."
        if not os.path.exists(self.napcat_cwd.get().strip()):
            return f"NapCat directory does not exist:\n{self.napcat_cwd.get()}"
        if not os.path.exists(self.astrbot_cwd.get().strip()):
            return f"AstrBot directory does not exist:\n{self.astrbot_cwd.get()}"
        return None

    def _on_close(self) -> None:
        """Handle dialog close - re-hide root if needed."""
        if self._root_was_hidden:
            self.dialog.master.withdraw()
        self.dialog.destroy()

    def _on_save(self) -> None:
        error = self._validate()
        if error:
            messagebox.showerror("Validation Error", error, parent=self.dialog)
            return

        config = {
            "napcat": {
                "cwd": self.napcat_cwd.get().strip(),
                "cmd": self.napcat_cmd.get().strip(),
                "encoding": self.napcat_enc.get().strip(),
            },
            "astrbot": {
                "cwd": self.astrbot_cwd.get().strip(),
                "cmd": self.astrbot_cmd.get().strip(),
                "encoding": self.astrbot_enc.get().strip(),
            },
            "output_refresh_ms": int(self.output_refresh_var.get()),
            "autostart": self.autostart_var.get(),
        }

        if save_config(config):
            self._logger.info("Config saved via settings dialog")

            # Handle autostart
            if config["autostart"]:
                enable_autostart()
            else:
                disable_autostart()

            self._result = config
            self._on_close()
        else:
            messagebox.showerror("Error", "Failed to save configuration.", parent=self.dialog)

    def _on_cancel(self) -> None:
        self._result = None
        self._on_close()

    def get_result(self) -> dict | None:
        """Wait for dialog and return config dict, or None if cancelled."""
        self.dialog.wait_window()
        return self._result
