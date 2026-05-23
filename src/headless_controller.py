"""Headless mode — run ProcessManager + HTTP server without tkinter GUI."""

import os
import queue
import re
import threading
import time
from config import get_data_dir, load_config
from http_server import create_server, QueueHandler
from logger import get_main_logger, get_process_logger

# Match ANSI stripping pattern from process_mgr._reader
_STRIP_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def run_headless() -> None:
    """Entry point for --headless mode. Blocks until KeyboardInterrupt."""
    logger = get_main_logger()
    logger.info("Starting TrayForge in headless mode")

    config = load_config()
    if config is None:
        from config import get_default_config, save_config

        config = get_default_config()
        save_config(config)

    from process_mgr import ProcessManager

    server = None
    pm = None
    port_file = None

    try:
        pm = ProcessManager(config)

        action_queue: queue.Queue = queue.Queue()

        # HTTP server with QueueHandler
        reload_fn = _make_reload_fn(config, pm)
        server = create_server(pm, None, reload_fn, handler_cls=QueueHandler)
        QueueHandler.action_queue = action_queue
        port = server.server_address[1]

        threading.Thread(
            target=server.serve_forever,
            daemon=True,
            name="http-server",
        ).start()

        # Write port file
        port_file = os.path.join(get_data_dir(), "cli_port.txt")
        with open(port_file, "w") as f:
            f.write(str(port))
        logger.info("HTTP server listening on 127.0.0.1:%d", port)

        # Autostart processes
        for proc in config.get("processes", []):
            if proc.get("autostart"):
                logger.info("Autostart: %s", proc["name"])
                pm.start(proc["name"])

        last_poll = 0.0
        poll_interval = config.get("poll_interval_ms", 2000) / 1000.0

        while True:
            # Drain action queue
            try:
                while True:
                    fn = action_queue.get_nowait()
                    fn()
            except queue.Empty:
                pass

            # Poll crashes
            now = time.monotonic()
            if now - last_poll >= poll_interval:
                last_poll = now
                pm.poll_crashes()

            # Drain output to process log files
            for name in pm.process_names():
                proc_logger = get_process_logger(name)
                for line in pm.drain(name):
                    line = _STRIP_ANSI.sub("", line)
                    if line:
                        proc_logger.info(line)

            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down")
    finally:
        if server is not None:
            logger.info("Stopping HTTP server")
            server.shutdown()
        if port_file is not None:
            try:
                os.remove(port_file)
            except OSError:
                pass
        if pm is not None:
            pm.shutdown()
        logger.info("Headless mode exited")


def _make_reload_fn(config, pm):
    """Create a reload callback for the headless controller."""
    from logger import get_main_logger
    from config import load_config

    logger = get_main_logger()

    def reload_config() -> bool:
        new_config = load_config()
        if new_config:
            pm.update_config(new_config)
            logger.info("Config reloaded from disk")
            return True
        logger.error("Failed to reload config")
        return False

    return reload_config
