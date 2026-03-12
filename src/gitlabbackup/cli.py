"""CLI entry point — Click commands and wiring."""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .backup import BackupEngine
from .config import Config
from .discovery import RepoDiscovery
from .display import (
    console,
    show_backup_summary,
    show_dry_run,
    show_project_list,
    show_status,
    show_verify_results,
)
from .executor import BackupExecutor
from .gitlab import GlabClient, GlabError
from .manifest import ManifestManager
from .models import BackupStatus, GitLabProject

log = logging.getLogger("gitlabbackup")


def _setup_logging(backup_dir: Path, verbose: bool) -> None:
    """Configure logging to file and optionally to stderr."""
    log_dir = backup_dir / ".logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    log_file = log_dir / f"backup-{timestamp}.log"

    handlers: list[logging.Handler] = [logging.FileHandler(log_file)]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


# Shared options for backup commands
def backup_options(f):
    """Decorator for common backup command options."""
    f = click.option("--include-wiki", is_flag=True, help="Also backup wiki repos")(f)
    f = click.option("--include-lfs", is_flag=True, help="Fetch LFS objects")(f)
    f = click.option("--skip-forks", is_flag=True, help="Skip forked repositories")(f)
    f = click.option("--forks-only", is_flag=True, help="Back up only forked repositories")(f)
    f = click.option("--exclude", multiple=True, help="Exclude by fnmatch pattern (repeatable)")(f)
    f = click.option("--include", "include_pat", multiple=True, help="Include only matching (repeatable)")(f)
    f = click.option("--post-hook", default="", help="Shell command to run after backup")(f)
    f = click.option("--dry-run", is_flag=True, help="Show what would be backed up")(f)
    return f


def _apply_backup_options(config: Config, **kwargs) -> None:
    """Apply backup-specific CLI options to config."""
    if kwargs.get("include_wiki"):
        config.include_wiki = True
    if kwargs.get("include_lfs"):
        config.include_lfs = True
    if kwargs.get("skip_forks"):
        config.skip_forks = True
    if kwargs.get("forks_only"):
        config.forks_only = True
    if kwargs.get("exclude"):
        config.exclude_patterns = list(kwargs["exclude"])
    if kwargs.get("include_pat"):
        config.include_patterns = list(kwargs["include_pat"])
    if kwargs.get("post_hook"):
        config.post_hook = kwargs["post_hook"]
    if kwargs.get("dry_run"):
        config.dry_run = True


def _run_backup(config: Config, projects: list[GitLabProject], gitlab_host: str) -> None:
    """Common backup execution logic."""
    if config.dry_run:
        show_dry_run(projects, config.protocol)
        return

    if not projects:
        console.print("[yellow]No projects to back up.[/]")
        return

    engine = BackupEngine(config)
    executor = BackupExecutor(config, engine)
    results = executor.execute(projects)

    # Update manifest
    manifest_mgr = ManifestManager(config.backup_dir)
    manifest = manifest_mgr.load()
    manifest_mgr.update_from_results(manifest, results, gitlab_host)

    show_backup_summary(results)

    # Exit with error if any failures
    failed = sum(1 for r in results if r.status == BackupStatus.FAILED)
    if failed:
        raise SystemExit(1)


@click.group()
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None, help="Config file path")
@click.option("--backup-dir", type=click.Path(path_type=Path), default=None, help="Backup destination")
@click.option("--gitlab-host", default=None, help="GitLab hostname override")
@click.option("--protocol", type=click.Choice(["ssh", "http"]), default=None, help="Clone protocol")
@click.option("--workers", type=int, default=None, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be backed up")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx, config_path, backup_dir, gitlab_host, protocol, workers, dry_run, verbose):
    """Back up GitLab repositories to local disk via mirror clones."""
    config = Config.load(config_path)

    # Apply CLI overrides
    if backup_dir is not None:
        config.backup_dir = backup_dir
    if gitlab_host is not None:
        config.gitlab_host = gitlab_host
    if protocol is not None:
        config.protocol = protocol
    if workers is not None:
        config.workers = workers
    if dry_run:
        config.dry_run = True
    if verbose:
        config.verbose = True

    config.backup_dir.mkdir(parents=True, exist_ok=True)
    _setup_logging(config.backup_dir, config.verbose)

    ctx.ensure_object(dict)
    ctx.obj["config"] = config


def _get_client(config: Config) -> GlabClient:
    """Create and validate a GlabClient."""
    client = GlabClient(host=config.gitlab_host)
    if not client.check_auth():
        console.print("[red]glab is not installed or not authenticated.[/]")
        console.print("Install glab and run: glab auth login")
        raise SystemExit(1)
    return client


@cli.command()
@click.argument("group_path")
@click.option("--include-subgroups/--no-subgroups", default=True, help="Include subgroups")
@backup_options
@click.pass_context
def group(ctx, group_path, include_subgroups, **kwargs):
    """Back up all repos in a group."""
    config: Config = ctx.obj["config"]
    config.include_subgroups = include_subgroups
    _apply_backup_options(config, **kwargs)

    client = _get_client(config)
    discovery = RepoDiscovery(client, config)

    try:
        projects = discovery.discover_group(group_path)
    except GlabError as e:
        console.print(f"[red]Failed to discover group '{group_path}': {e}[/]")
        raise SystemExit(1)

    console.print(f"Found [bold]{len(projects)}[/] project(s) in [cyan]{group_path}[/]")
    _run_backup(config, projects, client.get_host())


@cli.command()
@backup_options
@click.pass_context
def starred(ctx, **kwargs):
    """Back up starred repositories."""
    config: Config = ctx.obj["config"]
    _apply_backup_options(config, **kwargs)

    client = _get_client(config)
    discovery = RepoDiscovery(client, config)
    projects = discovery.discover_starred()

    console.print(f"Found [bold]{len(projects)}[/] starred project(s)")
    _run_backup(config, projects, client.get_host())


@cli.command()
@backup_options
@click.pass_context
def member(ctx, **kwargs):
    """Back up repos user is a member of."""
    config: Config = ctx.obj["config"]
    _apply_backup_options(config, **kwargs)

    client = _get_client(config)
    discovery = RepoDiscovery(client, config)
    projects = discovery.discover_member()

    console.print(f"Found [bold]{len(projects)}[/] member project(s)")
    _run_backup(config, projects, client.get_host())


@cli.command(name="all")
@backup_options
@click.pass_context
def all_repos(ctx, **kwargs):
    """Back up all accessible repositories."""
    config: Config = ctx.obj["config"]
    _apply_backup_options(config, **kwargs)

    client = _get_client(config)
    discovery = RepoDiscovery(client, config)
    projects = discovery.discover_all()

    console.print(f"Found [bold]{len(projects)}[/] accessible project(s)")
    _run_backup(config, projects, client.get_host())


@cli.command()
@click.pass_context
def status(ctx):
    """Show backup status and statistics."""
    config: Config = ctx.obj["config"]
    manifest_mgr = ManifestManager(config.backup_dir)
    manifest = manifest_mgr.load()
    show_status(manifest)


@cli.command()
@click.pass_context
def verify(ctx):
    """Verify integrity of existing backups."""
    config: Config = ctx.obj["config"]
    manifest_mgr = ManifestManager(config.backup_dir)
    manifest = manifest_mgr.load()

    if not manifest.projects:
        console.print("[yellow]No backups found to verify.[/]")
        return

    results: list[tuple[str, bool, str]] = []
    for path, proj in sorted(manifest.projects.items()):
        repo_path = config.backup_dir / proj.backup_path
        if not repo_path.exists():
            results.append((path, False, "directory missing"))
            continue

        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "fsck", "--no-dangling"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                # Check HEAD SHA matches manifest
                head_result = subprocess.run(
                    ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
                    capture_output=True, text=True, timeout=30,
                )
                head_sha = head_result.stdout.strip()
                if proj.head_sha and head_sha != proj.head_sha:
                    results.append((path, False, f"HEAD mismatch: expected {proj.head_sha[:12]}, got {head_sha[:12]}"))
                else:
                    results.append((path, True, f"HEAD {head_sha[:12]}"))
            else:
                results.append((path, False, result.stderr.strip()[:100]))
        except subprocess.TimeoutExpired:
            results.append((path, False, "fsck timed out"))

    show_verify_results(results)


@cli.command(name="list")
@click.option("--group", "group_path", default=None, help="List repos in a group")
@click.option("--starred", "use_starred", is_flag=True, help="List starred repos")
@click.option("--member", "use_member", is_flag=True, help="List member repos")
@click.pass_context
def list_repos(ctx, group_path, use_starred, use_member):
    """List discovered repos without backing up."""
    config: Config = ctx.obj["config"]
    client = _get_client(config)
    discovery = RepoDiscovery(client, config)

    if group_path:
        try:
            projects = discovery.discover_group(group_path)
        except GlabError as e:
            console.print(f"[red]Failed to discover group '{group_path}': {e}[/]")
            raise SystemExit(1)
        show_project_list(projects, title=f"Projects in {group_path}")
    elif use_starred:
        projects = discovery.discover_starred()
        show_project_list(projects, title="Starred Projects")
    elif use_member:
        projects = discovery.discover_member()
        show_project_list(projects, title="Member Projects")
    else:
        projects = discovery.discover_all()
        show_project_list(projects, title="All Accessible Projects")
