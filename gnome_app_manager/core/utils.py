import os
import re
import shlex
import subprocess
import threading
from typing import Dict, Tuple, Optional, Callable, List

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk


def format_bytes(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    val = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if val < 1024.0:
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} PB"


def get_path_size_and_count(path: str) -> Tuple[int, int]:
    total_size = 0
    count = 0
    if not os.path.exists(path):
        return 0, 0

    try:
        if os.path.islink(path):
            return 0, 1
        if os.path.isfile(path):
            return os.path.getsize(path), 1
        
        for root, dirs, files in os.walk(path, followlinks=False):
            count += len(dirs) + len(files)
            for f in files:
                fp = os.path.join(root, f)
                if not os.path.islink(fp):
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass
    except OSError:
        pass

    return total_size, count


def is_root_needed(path: str) -> bool:
    curr = os.path.abspath(os.path.expanduser(path))
    if os.path.exists(curr):
        return not os.access(curr, os.W_OK)
    
    while curr and curr != "/":
        curr = os.path.dirname(curr)
        if os.path.exists(curr):
            return not os.access(curr, os.W_OK)
    return True


def parse_desktop_file(file_path: str) -> Dict[str, str]:
    data = {}
    if not os.path.isfile(file_path):
        return data

    in_desktop_entry = False
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_desktop_entry = (line == "[Desktop Entry]")
                    continue
                if in_desktop_entry and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key not in data:
                        data[key] = val
    except Exception:
        pass
    return data


def execute_process_with_callback(
    cmd: List[str],
    on_output: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int], None]] = None
):
    def worker():
        exit_code = 1
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            if proc.stdout:
                for line in iter(proc.stdout.readline, ''):
                    if not line:
                        break
                    line_clean = line.rstrip()
                    if on_output:
                        GLib.idle_add(on_output, line_clean)
            proc.wait()
            exit_code = proc.returncode
        except Exception as e:
            if on_output:
                GLib.idle_add(on_output, f"[Error executing command]: {str(e)}")
            exit_code = -1

        if on_complete:
            GLib.idle_add(on_complete, exit_code)

    threading.Thread(target=worker, daemon=True).start()
