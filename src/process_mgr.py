"""Process manager — generic dict-based process registry."""

from __future__ import annotations

from dataclasses import dataclass, field
import subprocess
import sys
import threading
import queue
import shlex
import os
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING
import psutil
from logger import get_main_logger, get_process_logger
from trayforge_types import ProcessConfig, AppConfig

if TYPE_CHECKING:
    from trayforge_types import ProcessStatus


_STRIP_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

MAX_RESTARTS = 3
RESTART_COOLDOWN = 60.0


@dataclass
class _ProcState:
    proc: subprocess.Popen | None = None
    msg_queue: queue.Queue = field(default_factory=queue.Queue)
    restarts: int = 0
    webui_url: str | None = None
    last_restart: float = 0.0
    cooldown_notified: bool = False
    cfg: ProcessConfig = field(default_factory=dict)  # type: ignore[assignment]


class ProcessManager:
    def __init__(self, config: AppConfig) -> None:
        self._procs: dict[str, _ProcState] = {}
        self._status_listeners: list[callable] = []
        self._notify_listeners: list[callable] = []
        self._build_from_config(config)

    # --- Public API ---

    def update_config(self, config: AppConfig) -> None:
        self._build_from_config(config)
        self._emit_status()

    def process_names(self) -> list[str]:
        return list(self._procs.keys())

    def on_status_change(self, cb: callable) -> None:
        self._status_listeners.append(cb)

    def on_notification(self, cb: callable) -> None:
        self._notify_listeners.append(cb)

    def start(self, name: str) -> None:
        self._start(name)

    def stop(self, name: str) -> None:
        self._stop(name)

    def restart(self, name: str) -> None:
        self._stop_internal(name)
        ps = self._procs.get(name)
        if ps is not None:
            ps.restarts = 0
        self._start(name, _reset_counter=True)
        self._emit_status()

    def start_all(self) -> None:
        for name in self._procs:
            self._start(name)

    def stop_all(self) -> None:
        for name in self._procs:
            self._stop(name)

    def shutdown(self) -> None:
        self.stop_all()

    def is_running(self, name: str) -> bool:
        ps = self._procs.get(name)
        if ps is None:
            return False
        proc = ps.proc
        return proc is not None and proc.poll() is None

    def has_webui(self, name: str) -> bool:
        ps = self._procs.get(name)
        if ps is None:
            return False
        return ps.cfg.get("webui_pattern") is not None

    def get_status(self, name: str) -> "ProcessStatus | None":
        """Return a ProcessStatus dict for the named process, or None if unknown."""
        ps = self._procs.get(name)
        if ps is None:
            return None
        proc = ps.proc
        running = proc is not None and proc.poll() is None
        result: ProcessStatus = {
            "name": name,
            "running": running,
            "pid": proc.pid if running else None,
            "webui_url": ps.webui_url,
            "has_webui": ps.cfg.get("webui_pattern") is not None,
            "restarts": ps.restarts,
            "max_restarts": MAX_RESTARTS,
        }
        return result

    def get_webui_url(self, name: str) -> str | None:
        ps = self._procs.get(name)
        if ps is None:
            return None
        return ps.webui_url

    def drain(self, name: str) -> list[str]:
        ps = self._procs.get(name)
        if ps is None:
            return []
        lines: list[str] = []
        q = ps.msg_queue
        while True:
            try:
                lines.append(q.get_nowait())
            except queue.Empty:
                break
        return lines

    def poll_crashes(self) -> None:
        for name, ps in self._procs.items():
            if ps.proc is None:
                continue
            ret = ps.proc.poll()
            if ret is not None:
                if ps.restarts >= MAX_RESTARTS:
                    ps.proc = None
                    ps.webui_url = None
                    self._system_msg(
                        name,
                        f"{name} max restart attempts ({MAX_RESTARTS}) reached, stopped",
                    )
                    self._emit_status()
                    continue

                now = time.monotonic()
                if ps.restarts > 0 and now - ps.last_restart < RESTART_COOLDOWN:
                    if not ps.cooldown_notified:
                        ps.cooldown_notified = True
                        remaining = int(RESTART_COOLDOWN - (now - ps.last_restart))
                        self._system_msg(
                            name,
                            f"{name} restart cooldown, next attempt in {remaining}s",
                        )
                    continue

                ps.proc = None
                ps.webui_url = None
                ps.restarts += 1
                ps.cooldown_notified = False
                ps.last_restart = now
                self._system_msg(
                    name,
                    f"{name} exited (code={ret}), auto-restarting ({ps.restarts}/{MAX_RESTARTS})...",
                )
                self._start(name, _reset_counter=False)
                self._emit_status()

    # --- Internal ---

    def _build_from_config(self, config: AppConfig) -> None:
        new_procs: dict[str, _ProcState] = {}
        for proc_cfg in config.get("processes", []):
            name = proc_cfg["name"]
            if name in self._procs:
                existing = self._procs[name]
                existing.cfg = proc_cfg
                new_procs[name] = existing
            else:
                new_procs[name] = _ProcState(cfg=proc_cfg)
        for old_name in self._procs:
            if old_name not in new_procs:
                self._stop_internal(old_name)
        self._procs = new_procs

    def _system_msg(self, name: str, msg: str) -> None:
        ps = self._procs.get(name)
        if ps is None:
            return
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"
        ps.msg_queue.put(f"[{ts}] [SYSTEM] {msg}")

    def _notify(self, title: str, msg: str) -> None:
        for cb in self._notify_listeners:
            try:
                cb(title, msg)
            except Exception:
                logger = get_main_logger()
                logger.warning("notification listener failed", exc_info=True)

    def _emit_status(self) -> None:
        for cb in self._status_listeners:
            try:
                cb()
            except Exception:
                logger = get_main_logger()
                logger.warning("status listener failed", exc_info=True)

    def _kill_cwd_processes(self, cwd: str) -> None:
        """Kill all processes whose cwd matches the given directory."""
        if not cwd:
            return
        norm_cwd = os.path.normpath(cwd)
        try:
            for proc in psutil.process_iter(["pid", "cwd"]):
                try:
                    p_cwd = proc.info["cwd"]
                    if sys.platform == "win32":
                        if not (
                            p_cwd
                            and os.path.normcase(os.path.normpath(p_cwd))
                            == os.path.normcase(norm_cwd)
                        ):
                            continue
                    elif not (p_cwd and os.path.normpath(p_cwd) == norm_cwd):
                        continue
                    subprocess.run(
                        ["taskkill", "/f", "/t", "/pid", str(proc.info["pid"])],
                        capture_output=True,
                        timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                except Exception:
                    logger = get_main_logger()
                    logger.debug("kill_cwd_processes iter error", exc_info=True)
        except Exception:
            pass

    def _start(self, name: str, _reset_counter: bool = True) -> None:
        logger = get_main_logger()
        ps = self._procs.get(name)
        if ps is None:
            return
        if self.is_running(name):
            return

        cfg = ps.cfg
        cwd: str = cfg.get("cwd", "")
        cmd: str = cfg.get("cmd", "")
        enc: str = cfg.get("encoding", "utf-8")
        delete_files: list[str] = cfg.get("delete_before_start", [])

        if not cmd or not cmd.strip():
            msg = f"{name} has no command configured — open Settings to set cmd"
            logger.error(msg)
            self._system_msg(name, msg)
            return

        # Cleanup cwd: kill all processes matching cwd (for processes that leave zombies)
        cleanup = cfg.get("cleanup_cwd", False)
        if cleanup and sys.platform == "win32":
            self._kill_cwd_processes(cwd)

        # Delete files before start
        for rel_path in delete_files:
            file_path = os.path.join(cwd, rel_path) if cwd else rel_path
            if cwd:
                real_file = os.path.realpath(file_path)
                real_cwd = os.path.realpath(cwd)
                if not real_file.startswith(real_cwd + os.sep) and real_file != real_cwd:
                    msg = f"{name} skipped delete {rel_path}: path outside cwd"
                    logger.warning(msg)
                    self._system_msg(name, msg)
                    continue
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except PermissionError:
                    if sys.platform == "win32":
                        self._kill_cwd_processes(cwd)
                        time.sleep(0.3)
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        msg = f"{name} failed to delete {rel_path}: {e}"
                        logger.warning(msg)
                        self._system_msg(name, msg)

        if cwd and not os.path.exists(cwd):
            msg = f"{name} working directory not found: {cwd}"
            logger.error(msg)
            self._system_msg(name, msg)
            return

        args = shlex.split(cmd, posix=(sys.platform != "win32"))
        if not os.path.isabs(args[0]):
            if cwd:
                resolved = os.path.join(cwd, args[0])
                if os.path.exists(resolved):
                    args[0] = resolved

        # Check exe reachable before launching
        exe = args[0]
        exe_found = os.path.exists(exe)
        if not exe_found and (os.sep not in exe and "/" not in exe):
            # Bare name — will be resolved by PATH in Popen, skip check
            pass
        elif not exe_found:
            msg = f"{name} executable not found: {exe}"
            logger.error(msg)
            self._system_msg(name, msg)
            return

        logger.info("Starting %s: %s", name, args)
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            kwargs: dict = {
                "cwd": cwd or None,
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
            ps.proc = proc
            if _reset_counter:
                ps.restarts = 0
            threading.Thread(
                target=self._reader,
                args=(proc.stdout, ps.msg_queue, name, ps),
                daemon=True,
            ).start()
            logger.info("%s started PID=%d", name, proc.pid)
            self._system_msg(name, f"{name} started (PID={proc.pid})")
        except FileNotFoundError:
            msg = f"{name} failed to start — command not found: {args[0]}"
            logger.error(msg)
            self._system_msg(name, msg)
        except Exception as e:
            msg = f"{name} failed to start: {e}"
            logger.error(msg)
            self._system_msg(name, msg)
        self._emit_status()

    def _stop(self, name: str) -> None:
        self._stop_internal(name)
        self._emit_status()

    def _stop_internal(self, name: str) -> None:
        logger = get_main_logger()
        ps = self._procs.get(name)
        if ps is None or ps.proc is None:
            return
        pid = ps.proc.pid
        logger.info("Stopping %s PID=%d", name, pid)
        ps.restarts = MAX_RESTARTS
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/f", "/t", "/pid", str(pid)],
                capture_output=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            try:
                ps.proc.terminate()
                ps.proc.wait(timeout=2)
            except Exception:
                try:
                    ps.proc.kill()
                except Exception:
                    pass
        ps.proc = None
        ps.webui_url = None
        self._system_msg(name, f"{name} stopped")

    def _reader(self, pipe, q: queue.Queue, name: str, ps: _ProcState) -> None:
        proc_logger = get_process_logger(name)
        url_parsed = False
        webui_pattern_str = ps.cfg.get("webui_pattern")
        webui_re = re.compile(webui_pattern_str) if webui_pattern_str else None
        try:
            for line in iter(pipe.readline, ""):
                line = line.rstrip("\n\r")
                line = _STRIP_ANSI.sub("", line)
                if line:
                    proc_logger.info(line)
                    q.put(line)
                    if not url_parsed and webui_re is not None:
                        m = webui_re.search(line)
                        if m:
                            ps.webui_url = m.group(1)
                            url_parsed = True
                            self._emit_status()
        except (ValueError, IOError):
            pass
