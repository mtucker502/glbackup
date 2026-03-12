"""Manifest management — JSON state tracking for backup runs."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from .models import BackupManifest, BackupResult, BackupStatus, ManifestProject

log = logging.getLogger(__name__)


class ManifestManager:
    """Manages the .manifest.json file for tracking backup state."""

    def __init__(self, backup_dir: Path) -> None:
        self.path = backup_dir / ".manifest.json"

    def load(self) -> BackupManifest:
        """Load manifest from disk, or return empty manifest."""
        if not self.path.exists():
            return BackupManifest()
        try:
            data = json.loads(self.path.read_text())
            return BackupManifest.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("Failed to parse manifest: %s", e)
            return BackupManifest()

    def save(self, manifest: BackupManifest) -> None:
        """Atomically write manifest to disk."""
        data = json.dumps(manifest.to_dict(), indent=2, sort_keys=True)
        # Atomic write: write to temp file then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".manifest-"
        )
        try:
            with open(fd, "w") as f:
                f.write(data)
                f.write("\n")
            Path(tmp_path).replace(self.path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def update_from_results(
        self, manifest: BackupManifest, results: list[BackupResult], gitlab_host: str
    ) -> BackupManifest:
        """Update manifest with backup results and save."""
        manifest.last_run = BackupManifest.now_iso()
        manifest.gitlab_host = gitlab_host

        for result in results:
            if result.status == BackupStatus.FAILED:
                # Keep existing entry if present, don't overwrite with failure
                continue
            path_key = result.project.path_with_namespace
            manifest.projects[path_key] = ManifestProject(
                project_id=result.project.id,
                last_backup=manifest.last_run,
                backup_path=result.backup_path,
                status=result.status.value,
                head_sha=result.head_sha,
                size_bytes=result.size_bytes,
            )

        self.save(manifest)
        return manifest
