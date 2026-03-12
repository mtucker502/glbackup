"""Backup executor — parallel backup with progress reporting."""

from __future__ import annotations

import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .backup import BackupEngine
from .config import Config
from .models import BackupResult, BackupStatus, GitLabProject

log = logging.getLogger(__name__)


class BackupExecutor:
    """Runs backup operations in parallel with Rich progress display."""

    def __init__(self, config: Config, engine: BackupEngine) -> None:
        self.config = config
        self.engine = engine

    def execute(self, projects: list[GitLabProject]) -> list[BackupResult]:
        """Back up all projects in parallel, showing progress."""
        results: list[BackupResult] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("Backing up", total=len(projects))

            with ThreadPoolExecutor(max_workers=self.config.workers) as pool:
                futures = {
                    pool.submit(self.engine.backup_project, proj): proj
                    for proj in projects
                }
                for future in as_completed(futures):
                    proj = futures[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        log.error("Unexpected error backing up %s: %s", proj.path_with_namespace, e)
                        result = BackupResult(
                            project=proj,
                            status=BackupStatus.FAILED,
                            error=str(e),
                        )
                    results.append(result)
                    status_icon = {
                        BackupStatus.CLONED: "[green]cloned[/]",
                        BackupStatus.UPDATED: "[cyan]updated[/]",
                        BackupStatus.UNCHANGED: "[dim]unchanged[/]",
                        BackupStatus.FAILED: "[red]FAILED[/]",
                    }.get(result.status, result.status.value)
                    progress.console.print(
                        f"  {status_icon} {proj.path_with_namespace}"
                    )
                    progress.advance(task)

        self._run_post_hook(results)
        return results

    def _run_post_hook(self, results: list[BackupResult]) -> None:
        """Run post-backup hook command if configured."""
        if not self.config.post_hook:
            return
        failed = sum(1 for r in results if r.status == BackupStatus.FAILED)
        env = {
            **os.environ,
            "GLBACKUP_DIR": str(self.config.backup_dir),
            "GLBACKUP_COUNT": str(len(results)),
            "GLBACKUP_FAILED": str(failed),
            "GLBACKUP_MANIFEST": str(self.config.backup_dir / ".manifest.json"),
        }
        log.info("Running post-hook: %s", self.config.post_hook)
        try:
            subprocess.run(
                self.config.post_hook, shell=True, env=env,
                capture_output=True, text=True, timeout=300,
            )
        except Exception as e:
            log.error("Post-hook failed: %s", e)
