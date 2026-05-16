"""Process manager for NapCat QQ and AstrBot - lifecycle, monitoring, output capture."""

import subprocess
import sys
import threading
import time
import shlex
import os
import logging
from typing import Callable
from logger import get_main_logger, get_napcat_logger, get_astrbot_logger


StatusCallback = Callable[[], None]
OutputCallback = Callable[[str, str], None]  # (process_name, line)
NotifyCallback = Callable[[str, str], None]  # (title, message)


class ProcessManager:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._napcat_proc: subprocess.Popen | None = None
        self._astrbot_proc: subprocess.Popen | None = None
        self._napcat_restart_count = 0
        self._astrbot_restart_count = 0
        self._max_restarts = 3
        self._monitor_running = False
        self._monitor_thread: threading.Thread | None = None
        self._output_callbacks: list[OutputCallback] = []
        self._status_callbacks: list[StatusCallback] = []
        self._notify_callbacks: list[NotifyCallback] = []

    # --- Public API ---

    def update_config(self, config: dict) -> None:
        """Update config without stopping running processes."""
        self._config = config

    def on_status_change(self, callback: StatusCallback) -> None:
        self._status_callbacks.append(callback)

    def on_output(self, callback: OutputCallback) -> None:
        self._output_callbacks.append(callback)

    def on_notification(self, callback: NotifyCallback) -> None:
        self._notify_callbacks.append(callback)

    def start_all(self) -> None:
        self.start_napcat()
        self.start_astrbot()

    def stop_all(self) -> None:
        self.stop_napcat()
        self.stop_astrbot()

    def start_napcat(self) -> None:
        self._start_process("napcat")

    def start_astrbot(self) -> None:
        self._start_process("astrbot")

    def stop_napcat(self) -> None:
        self._stop_process("napcat")

    def stop_astrbot(self) -> None:
        self._stop_process("astrbot")

    def is_napcat_running(self) -> bool:
        return self._is_running("napcat")

    def is_astrbot_running(self) -> bool:
        return self._is_running("astrbot")

    def start_monitor(self) -> None:
        """Start the background monitor thread."""
        if self._monitor_running:
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    def stop_monitor(self) -> None:
        """Stop the background monitor thread."""
        self._monitor_running = False

    # --- Internal ---

    def _proc_name(self, name: str) -> str:
        return "NapCat" if name == "napcat" else "AstrBot"

    def _proc_config(self, name: str) -> dict:
        return self._config[name]

    def _proc_attr(self, name: str) -> str:
        return "_napcat_proc" if name == "napcat" else "_astrbot_proc"

    def _restart_count_attr(self, name: str) -> str:
        return (
            "_napcat_restart_count" if name == "napcat"
            else "_astrbot_restart_count"
        )

    def _get_proc(self, name: str) -> subprocess.Popen | None:
        return getattr(self, self._proc_attr(name))

    def _set_proc(self, name: str, proc: subprocess.Popen | None) -> None:
        setattr(self, self._proc_attr(name), proc)

    def _get_restart_count(self, name: str) -> int:
        return getattr(self, self._restart_count_attr(name))

    def _set_restart_count(self, name: str, value: int) -> None:
        setattr(self, self._restart_count_attr(name), value)

    def _is_running(self, name: str) -> bool:
        proc = self._get_proc(name)
        return proc is not None and proc.poll() is None

    def _get_logger(self, name: str) -> logging.Logger:
        if name == "napcat":
            return get_napcat_logger()
        return get_astrbot_logger()

    def _notify_status(self) -> None:
        for cb in self._status_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _notify_output(self, name: str, line: str) -> None:
        proc_name = self._proc_name(name)
        for cb in self._output_callbacks:
            try:
                cb(proc_name, line)
            except Exception:
                pass

    def _notify_user(self, title: str, message: str) -> None:
        for cb in self._notify_callbacks:
            try:
                cb(title, message)
            except Exception:
                pass

    def _read_output(self, pipe, name: str) -> None:
        """Read lines from a process pipe in a dedicated thread."""
        proc_logger = self._get_logger(name)
        try:
            for line in iter(pipe.readline, ""):
                if not line:
                    break
                line = line.rstrip("\n\r")
                if line:
                    proc_logger.info(line)
                    self._notify_output(name, line)
        except (ValueError, IOError):
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _start_process(self, name: str) -> None:
        logger = get_main_logger()
        proc_name = self._proc_name(name)

        if self._is_running(name):
            logger.info("%s is already running", proc_name)
            return

        proc_config = self._proc_config(name)
        cwd = proc_config["cwd"]
        cmd = proc_config["cmd"]

        # Clean up stale lock files before starting (e.g. astrbot.lock)
        lock_file = os.path.join(cwd, "astrbot.lock")
        if name == "astrbot" and os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                logger.info("Removed stale lock file: %s", lock_file)
            except OSError:
                pass

        if not os.path.exists(cwd):
            err_msg = f"{proc_name}: working directory not found: {cwd}"
            logger.error(err_msg)
            self._notify_output(name, f"[ERROR] Working directory not found: {cwd}")
            self._notify_user("Startup Error", err_msg)
            return

        logger.info("Starting %s: cwd=%s cmd=%s", proc_name, cwd, cmd)

        try:
            args = shlex.split(cmd)

            # Determine encoding from config
            proc_encoding = proc_config.get("encoding", "utf-8")

            # Build Popen kwargs
            popen_kwargs: dict = {
                "cwd": cwd,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
                "text": True,
                "encoding": proc_encoding,
                "errors": "replace",
            }
            # Force Python subprocesses to use UTF-8 for stdout
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            popen_kwargs["env"] = env
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(args, **popen_kwargs)
            self._set_proc(name, proc)
            self._set_restart_count(name, 0)

            # Start output reader thread
            reader = threading.Thread(
                target=self._read_output,
                args=(proc.stdout, name),
                daemon=True,
            )
            reader.start()

            logger.info("%s started (PID: %d)", proc_name, proc.pid)
            self._notify_output(name, f"[SYSTEM] {proc_name} started (PID: {proc.pid})")
            self._notify_status()

            # Start monitor if not already running
            self.start_monitor()

        except FileNotFoundError:
            err_msg = f"{proc_name}: executable not found: {cmd}"
            logger.error(err_msg)
            self._notify_output(name, f"[ERROR] Executable not found: {cmd}")
            self._notify_user("Startup Error", err_msg)
        except Exception as e:
            err_msg = f"{proc_name}: failed to start: {e}"
            logger.error(err_msg)
            self._notify_output(name, f"[ERROR] Failed to start: {e}")
            self._notify_user("Startup Error", err_msg)

    def _stop_process(self, name: str) -> None:
        logger = get_main_logger()
        proc_name = self._proc_name(name)
        proc = self._get_proc(name)

        if proc is None:
            logger.info("%s is not running", proc_name)
            return

        pid = proc.pid
        logger.info("Stopping %s (PID: %d)...", proc_name, pid)
        self._set_restart_count(name, self._max_restarts)

        # Close stdout pipe
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass

        # Step 1: Graceful terminate
        try:
            proc.terminate()
        except Exception:
            pass

        # Step 2: Wait for graceful exit
        exited = False
        try:
            proc.wait(timeout=3)
            exited = True
            logger.info("%s stopped gracefully", proc_name)
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

        # Step 3: Force kill if still running
        if not exited:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass

        # Step 4: Kill entire process tree (catches orphans from shims/wrappers)
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/f", "/t", "/pid", str(pid)],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass

        self._set_proc(name, None)
        self._notify_output(name, f"[SYSTEM] {proc_name} stopped")
        logger.info("%s stop completed", proc_name)
        self._notify_status()

    def _monitor_loop(self) -> None:
        """Background thread: poll process status every 2 seconds."""
        logger = get_main_logger()
        while self._monitor_running:
            for name in ("napcat", "astrbot"):
                proc = self._get_proc(name)
                if proc is None:
                    continue

                ret = proc.poll()
                if ret is not None:
                    proc_name = self._proc_name(name)
                    count = self._get_restart_count(name)
                    logger.warning(
                        "%s exited with code %d (restart count: %d/%d)",
                        proc_name, ret, count, self._max_restarts,
                    )
                    self._notify_output(
                        name,
                        f"[SYSTEM] {proc_name} exited with code {ret}",
                    )
                    self._set_proc(name, None)
                    self._notify_status()

                    if count < self._max_restarts:
                        self._set_restart_count(name, count + 1)
                        logger.info("Auto-restarting %s...", proc_name)
                        msg = f"Auto-restarting {proc_name} ({count + 1}/{self._max_restarts})..."
                        self._notify_output(name, f"[SYSTEM] {msg}")
                        self._notify_user(
                            f"{proc_name} Crashed",
                            f"Auto-restarting ({count + 1}/{self._max_restarts})..."
                        )
                        self._start_process(name)
                    else:
                        logger.error(
                            "%s: max restarts (%d) reached, giving up",
                            proc_name, self._max_restarts,
                        )
                        msg = f"{proc_name}: max restarts reached, giving up"
                        self._notify_output(name, f"[SYSTEM] {msg}")
                        self._notify_user(
                            f"{proc_name} Stopped",
                            "Max restart attempts reached. Please check logs."
                        )

            time.sleep(2)

    def shutdown(self) -> None:
        """Stop all processes and monitor."""
        logger = get_main_logger()
        logger.info("Shutting down...")
        self.stop_monitor()
        self.stop_all()
        logger.info("Shutdown complete")
