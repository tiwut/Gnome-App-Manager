import os
import shutil
import tempfile
import subprocess
from typing import List, Tuple, Callable, Optional
from gi.repository import GLib

from ..models.location_info import LeftoverItem
from .scanner import ResidualScanner


class LeftoverCleaner:
    @classmethod
    def clean_leftovers(
        cls,
        items: List[LeftoverItem],
        on_progress: Optional[Callable[[str, float], None]] = None,
        on_finished: Optional[Callable[[int, int, List[str]], None]] = None
    ):
        selected = [item for item in items if item.selected]
        if not selected:
            if on_finished:
                on_finished(0, 0, [])
            return

        total_bytes = 0
        removed_count = 0
        errors: List[str] = []

        user_items: List[LeftoverItem] = []
        root_items: List[LeftoverItem] = []

        for it in selected:
            if not ResidualScanner.is_safe_to_touch(it.path):
                errors.append(f"Skipped unsafe path: {it.path}")
                continue
            if it.requires_root:
                root_items.append(it)
            else:
                user_items.append(it)

        total_steps = len(user_items) + (1 if root_items else 0)
        current_step = 0

        for item in user_items:
            current_step += 1
            if on_progress:
                pct = current_step / max(total_steps, 1)
                on_progress(f"Removing user file: {os.path.basename(item.path)}", pct)

            if not os.path.exists(item.path):
                continue

            try:
                if item.is_directory or os.path.isdir(item.path):
                    shutil.rmtree(item.path, ignore_errors=False)
                else:
                    os.remove(item.path)
                total_bytes += item.size_bytes
                removed_count += 1
            except Exception as e:
                errors.append(f"Failed to remove {item.path}: {str(e)}")

        if root_items:
            current_step += 1
            if on_progress:
                pct = current_step / max(total_steps, 1)
                on_progress("Removing system files with administrator permissions...", pct)

            script_lines = [
                "#!/bin/bash",
                "set -e\n"
            ]
            for item in root_items:
                if not ResidualScanner.is_safe_to_touch(item.path):
                    continue
                escaped = item.path.replace('"', '\\"')
                script_lines.append(f'rm -rf "{escaped}"')

            tmp_fd, tmp_path = tempfile.mkstemp(prefix="gnome_app_manager_cleanup_", suffix=".sh")
            try:
                with os.fdopen(tmp_fd, "w") as f:
                    f.write("\n".join(script_lines) + "\n")
                os.chmod(tmp_path, 0o700)

                cmd = ["pkexec", "bash", tmp_path]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    for item in root_items:
                        total_bytes += item.size_bytes
                        removed_count += 1
                else:
                    err_msg = res.stderr.strip() or res.stdout.strip() or "Authorization cancelled or failed"
                    errors.append(f"System files removal failed: {err_msg}")
            except Exception as e:
                errors.append(f"System files cleanup error: {str(e)}")
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

        if on_finished:
            on_finished(total_bytes, removed_count, errors)
