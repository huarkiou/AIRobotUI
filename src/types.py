"""Shared type definitions for TrayForge."""

from typing import TypedDict


class ProcessConfig(TypedDict):
    name: str
    cwd: str
    cmd: str
    encoding: str
    singleton: bool
    autostart: bool
    webui_pattern: str | None
    delete_before_start: list[str]


class AppConfig(TypedDict):
    processes: list[ProcessConfig]
    output_refresh_ms: int
    poll_interval_ms: int
    autostart: bool
