"""Shared type definitions for TrayForge."""

from typing import TypedDict


class ProcessConfig(TypedDict):
    name: str
    cwd: str
    cmd: str
    encoding: str
    singleton: bool
    autostart: bool
    cleanup_cwd: bool
    webui_pattern: str | None
    delete_before_start: list[str]


class AppConfig(TypedDict):
    processes: list[ProcessConfig]
    output_refresh_ms: int
    poll_interval_ms: int
    autostart: bool


class ProcessStatus(TypedDict):
    name: str
    running: bool
    pid: int | None
    webui_url: str | None
    has_webui: bool
    restarts: int
    max_restarts: int
