"""Rich display helpers — tables, summaries, and formatting."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .models import BackupManifest, BackupResult, BackupStatus, GitLabProject

console = Console()


def show_project_list(projects: list[GitLabProject], *, title: str = "Discovered Projects") -> None:
    """Display a table of discovered projects."""
    table = Table(title=title)
    table.add_column("Path", style="cyan")
    table.add_column("Fork", justify="center")
    table.add_column("Archived", justify="center")
    table.add_column("Wiki", justify="center")

    for p in projects:
        table.add_row(
            p.path_with_namespace,
            "yes" if p.is_fork else "",
            "yes" if p.archived else "",
            "yes" if p.wiki_enabled else "",
        )

    console.print(table)
    console.print(f"\n[bold]{len(projects)}[/bold] project(s) found")


def show_dry_run(projects: list[GitLabProject], protocol: str) -> None:
    """Display what would be backed up in dry-run mode."""
    table = Table(title="Dry Run — Would Back Up")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Path", style="cyan")
    table.add_column("Clone URL", style="dim")

    for i, p in enumerate(projects, 1):
        url = p.ssh_url if protocol == "ssh" else p.http_url
        table.add_row(str(i), p.path_with_namespace, url)

    console.print(table)
    console.print(f"\n[bold]{len(projects)}[/bold] project(s) would be backed up")


def show_backup_summary(results: list[BackupResult]) -> None:
    """Display a summary of backup results."""
    cloned = sum(1 for r in results if r.status == BackupStatus.CLONED)
    updated = sum(1 for r in results if r.status == BackupStatus.UPDATED)
    unchanged = sum(1 for r in results if r.status == BackupStatus.UNCHANGED)
    failed = sum(1 for r in results if r.status == BackupStatus.FAILED)

    console.print()
    console.print("[bold]Backup Summary[/bold]")
    console.print(f"  Cloned:    [green]{cloned}[/]")
    console.print(f"  Updated:   [cyan]{updated}[/]")
    console.print(f"  Unchanged: [dim]{unchanged}[/]")
    if failed:
        console.print(f"  Failed:    [red]{failed}[/]")
    console.print(f"  Total:     [bold]{len(results)}[/]")

    # Show failures
    failures = [r for r in results if r.status == BackupStatus.FAILED]
    if failures:
        console.print()
        console.print("[red bold]Failed:[/]")
        for r in failures:
            console.print(f"  [red]{r.project.path_with_namespace}[/]: {r.error}")


def show_status(manifest: BackupManifest) -> None:
    """Display backup status from manifest."""
    if not manifest.projects:
        console.print("[yellow]No backups found in manifest.[/]")
        return

    table = Table(title=f"Backup Status — {manifest.gitlab_host}")
    table.add_column("Path", style="cyan")
    table.add_column("Status")
    table.add_column("Last Backup", style="dim")
    table.add_column("HEAD", style="dim", max_width=12)
    table.add_column("Size", justify="right")

    for path, proj in sorted(manifest.projects.items()):
        status_style = {
            "cloned": "green",
            "updated": "cyan",
            "unchanged": "dim",
        }.get(proj.status, "white")
        size = _human_size(proj.size_bytes) if proj.size_bytes else ""
        table.add_row(
            path,
            f"[{status_style}]{proj.status}[/]",
            proj.last_backup,
            proj.head_sha[:12] if proj.head_sha else "",
            size,
        )

    console.print(table)
    console.print(f"\nLast run: {manifest.last_run}")
    console.print(f"Total projects: [bold]{len(manifest.projects)}[/]")
    total_size = sum(p.size_bytes for p in manifest.projects.values())
    if total_size:
        console.print(f"Total size: [bold]{_human_size(total_size)}[/]")


def show_verify_results(results: list[tuple[str, bool, str]]) -> None:
    """Display verification results: list of (path, passed, message)."""
    table = Table(title="Verification Results")
    table.add_column("Path", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    passed = 0
    for path, ok, msg in results:
        if ok:
            passed += 1
            table.add_row(path, "[green]OK[/]", msg)
        else:
            table.add_row(path, "[red]FAIL[/]", msg)

    console.print(table)
    console.print(f"\n{passed}/{len(results)} repositories passed verification")


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
