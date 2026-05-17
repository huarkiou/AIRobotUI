"""Process manager - all Popen operations on calling thread (assumed main)."""

import subprocess
import sys
import threading
import queue
import shlex
import os
import re
import time  # noqa: F401  (will be used in follow-up task)
from datetime import datetime
from logger import get_main_logger, get_napcat_logger, get_astrbot_logger


_STRIP_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


class ProcessManager:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._napcat_proc: subprocess.Popen | None = None
        self._astrbot_proc: subprocess.Popen | None = None
        self._napcat_restarts = 0
        self._astrbot_restarts = 0
        self._max_restarts = 3
        self._napcat_queue: queue.Queue[str] = queue.Queue()
        self._astrbot_queue: queue.Queue[str] = queue.Queue()
        self._status_listeners: list[callable] = []
        self._notify_listeners: list[callable] = []
        self._napcat_webui_url: str | None = None
        self._astrbot_webui_url: str | None = None
        self._napcat_last_restart: float = 0.0
        self._astrbot_last_restart: float = 0.0

    # --- Public API ---

    def update_config(self, config: dict) -> None:
        self._config = config

    def on_status_change(self, cb: callable) -> None:
        self._status_listeners.append(cb)

    def on_notification(self, cb: callable) -> None:
        self._notify_listeners.append(cb)

    def start_napcat(self) -> None:
        self._start("napcat")

    def start_astrbot(self) -> None:
        self._start("astrbot")

    def stop_napcat(self) -> None:
        self._stop("napcat")

    def stop_astrbot(self) -> None:
        self._stop("astrbot")

    def start_all(self) -> None:
        self.start_napcat()
        self.start_astrbot()

    def stop_all(self) -> None:
        self.stop_napcat()
        self.stop_astrbot()

    def shutdown(self) -> None:
        self.stop_all()

    def is_napcat_running(self) -> bool:
        return self._running("napcat")

    def is_astrbot_running(self) -> bool:
        return self._running("astrbot")

    def poll_crashes(self) -> None:
        """Check for unexpected exits; auto-restart or notify."""
        for name in ("napcat", "astrbot"):
            proc = self._get_proc(name)
            if proc is None:
                continue
            ret = proc.poll()
            if ret is not None:
                pname = self._name(name)
                logger = get_main_logger()
                count = self._restart_count(name)
                self._set_proc(name, None)
                logger.warning(
                    "%s exited code=%d restarts=%d/%d", pname, ret, count, self._max_restarts
                )
                if count < self._max_restarts:
                    self._inc_restart(name)
                    self._notify(
                        f"{pname} Crashed",
                        f"Auto-restarting ({count + 1}/{self._max_restarts})...",
                    )
                    self._start(name)
                else:
                    self._notify(
                        f"{pname} Stopped",
                        "Max restart attempts reached.",
                    )

    def drain_napcat(self) -> list[str]:
        return self._drain(self._napcat_queue)

    def drain_astrbot(self) -> list[str]:
        return self._drain(self._astrbot_queue)

    # --- Internal ---

    def _drain(self, q: queue.Queue) -> list[str]:
        lines: list[str] = []
        while True:
            try:
                lines.append(q.get_nowait())
            except queue.Empty:
                break
        return lines

    def _system_msg(self, name: str, msg: str) -> None:
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"
        q = self._napcat_queue if name == "napcat" else self._astrbot_queue
        q.put(f"[{ts}] [SYSTEM] {msg}")

    def _try_parse_webui_url(self, name: str, line: str) -> str | None:
        line = _STRIP_ANSI.sub("", line)
        if name == "napcat":
            marker = "[WebUi] WebUi User Panel Url: "
            idx = line.find(marker)
            if idx == -1:
                return None
            rest = line[idx + len(marker) :].strip()
        else:  # astrbot
            marker = "Starting WebUI at "
            idx = line.find(marker)
            if idx == -1:
                return None
            rest = line[idx + len(marker) :].strip()
        m = re.search(r"https?://\S+", rest)
        return m.group(0) if m else None

    def get_napcat_webui_url(self) -> str | None:
        return self._napcat_webui_url

    def get_astrbot_webui_url(self) -> str | None:
        return self._astrbot_webui_url

    def _name(self, n: str) -> str:
        return "NapCat" if n == "napcat" else "AstrBot"

    def _proc_attr(self, n: str) -> str:
        return "_napcat_proc" if n == "napcat" else "_astrbot_proc"

    def _restart_attr(self, n: str) -> str:
        return "_napcat_restarts" if n == "napcat" else "_astrbot_restarts"

    def _get_proc(self, n: str) -> subprocess.Popen | None:
        return getattr(self, self._proc_attr(n))

    def _set_proc(self, n: str, p: subprocess.Popen | None) -> None:
        setattr(self, self._proc_attr(n), p)

    def _restart_count(self, n: str) -> int:
        return getattr(self, self._restart_attr(n))

    def _inc_restart(self, n: str) -> None:
        setattr(self, self._restart_attr(n), self._restart_count(n) + 1)

    def _reset_restart(self, n: str) -> None:
        setattr(self, self._restart_attr(n), 0)

    def _running(self, n: str) -> bool:
        p = self._get_proc(n)
        return p is not None and p.poll() is None

    def _notify(self, title: str, msg: str) -> None:
        for cb in self._notify_listeners:
            try:
                cb(title, msg)
            except Exception:
                pass

    def _emit_status(self) -> None:
        for cb in self._status_listeners:
            try:
                cb()
            except Exception:
                pass

    def _reader(self, pipe, q: queue.Queue, name: str) -> None:
        proc_logger = get_napcat_logger() if name == "napcat" else get_astrbot_logger()
        url_parsed = False
        try:
            for line in iter(pipe.readline, ""):
                line = line.rstrip("\n\r")
                line = _STRIP_ANSI.sub("", line)
                if line:
                    proc_logger.info(line)
                    q.put(line)
                    if not url_parsed:
                        url = self._try_parse_webui_url(name, line)
                        if url is not None:
                            setattr(self, f"_{name}_webui_url", url)
                            url_parsed = True
                            self._emit_status()
        except (ValueError, IOError):
            pass

    def _start(self, name: str) -> None:
        logger = get_main_logger()
        pname = self._name(name)
        if self._running(name):
            return
        cfg = self._config[name]
        cwd: str = cfg["cwd"]
        cmd: str = cfg["cmd"]
        enc: str = cfg.get("encoding", "utf-8")

        # Clean stale lock files
        if name == "astrbot":
            lock = os.path.join(cwd, "astrbot.lock")
            if os.path.exists(lock):
                try:
                    os.remove(lock)
                except OSError:
                    pass

        if not os.path.exists(cwd):
            logger.error("%s cwd not found: %s", pname, cwd)
            return

        args = shlex.split(cmd)
        if not os.path.isabs(args[0]) and os.sep not in args[0] and "/" not in args[0]:
            resolved = os.path.join(cwd, args[0])
            if os.path.exists(resolved):
                args[0] = resolved

        logger.info("Starting %s: %s", pname, args)
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            kwargs: dict = {
                "cwd": cwd,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
                "text": True,
                "encoding": enc,
                "errors": "replace",
                "env": env,
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(args, **kwargs)
            self._set_proc(name, proc)
            self._reset_restart(name)
            q = self._napcat_queue if name == "napcat" else self._astrbot_queue
            threading.Thread(
                target=self._reader,
                args=(proc.stdout, q, name),
                daemon=True,
            ).start()
            logger.info("%s started PID=%d", pname, proc.pid)
            self._system_msg(name, f"{pname} started (PID={proc.pid})")
        except Exception as e:
            logger.error("Failed to start %s: %s", pname, e)
        self._emit_status()

    def _stop(self, name: str) -> None:
        logger = get_main_logger()
        pname = self._name(name)
        proc = self._get_proc(name)
        if proc is None:
            return
        pid = proc.pid
        logger.info("Stopping %s PID=%d", pname, pid)
        setattr(self, self._restart_attr(name), self._max_restarts)

        # taskkill /f /t kills entire process tree (including QQ.exe for NapCat)
        # Tested: 0.3s, reliable, no orphans. WM_CLOSE doesn't work for either process.
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/f", "/t", "/pid", str(pid)],
                capture_output=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._set_proc(name, None)
        setattr(self, f"_{name}_webui_url", None)
        self._system_msg(name, f"{pname} stopped")
        self._emit_status()
