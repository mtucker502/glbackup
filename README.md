# glbackup

mirror-clone GitLab repositories to local disk. uses `glab` CLI for API access (auth, pagination, tokens handled for you).

## install

```
uv tool install git+https://github.com/mtucker502/glbackup.git
```

or run directly without installing:

```
uvx --from git+https://github.com/mtucker502/glbackup.git glbackup
```

requires [glab](https://gitlab.com/gitlab-org/cli) authenticated (`glab auth login`).

## usage

```bash
# back up all repos in a group
glbackup group my-org/my-group

# starred repos only
glbackup starred

# repos you're a member of
glbackup member

# everything you can see
glbackup all

# preview what would be backed up
glbackup group my-org/my-group --dry-run

# list repos without backing up
glbackup list --group my-org/my-group
```

## options

```
--backup-dir PATH       destination (default: cwd)
--protocol [ssh|http]   clone protocol (default: ssh)
--workers N             parallel clones (default: 4)
--dry-run               show what would be backed up
--include-wiki          also back up wiki repos
--include-lfs           fetch LFS objects
--skip-forks            skip forked repos
--forks-only            only forked repos
--exclude PATTERN       exclude by fnmatch (repeatable)
--include PATTERN       include only matching (repeatable)
--post-hook COMMAND     run after backup completes
```

## backup layout

```
./
  .manifest.json
  group-name/
    subgroup/
      project-name.git/          # bare mirror
      project-name.wiki.git/     # wiki (optional)
```

## working with backups

backups are bare repos (`git clone --mirror`) — no working tree, all branches/tags/refs preserved. to browse or build code from a backup:

```bash
# add a worktree (keeps the bare repo intact)
git worktree add ../my-working-copy main

# or convert to a regular repo
cd project-name.git
git config --bool core.bare false
git checkout main
```

## other commands

```bash
glbackup status    # show backup state from manifest
glbackup verify    # git fsck on all mirrors
```

## config

optional TOML config at `~/.config/gitlabbackup/config.toml`:

```toml
backup_dir = "~/gitlab-backups"
protocol = "ssh"
workers = 8
gitlab_host = "gitlab.example.com"
exclude_patterns = ["archive/*"]
```

env vars: `GLBACKUP_DIR`, `GLBACKUP_HOST`, `GLBACKUP_PROTOCOL`, `GLBACKUP_WORKERS`
