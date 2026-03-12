"""Tests for repository discovery and filtering."""

from gitlabbackup.config import Config
from gitlabbackup.discovery import RepoDiscovery
from gitlabbackup.models import GitLabProject


class FakeClient:
    """Stub GlabClient for testing discovery filtering."""

    def __init__(self, projects: list[GitLabProject]):
        self._projects = projects

    def get_group_by_path(self, path):
        from gitlabbackup.models import GitLabGroup
        return GitLabGroup(id=1, name="group", full_path=path)

    def list_group_projects(self, group_id, *, include_subgroups=True):
        return list(self._projects)

    def list_starred_projects(self):
        return list(self._projects)

    def list_member_projects(self):
        return list(self._projects)

    def list_all_projects(self):
        return list(self._projects)


def test_deduplication(sample_projects):
    # Duplicate project id=1
    duped = sample_projects + [sample_projects[0]]
    config = Config()
    discovery = RepoDiscovery(FakeClient(duped), config)
    result = discovery.discover_starred()
    ids = [p.id for p in result]
    assert ids == sorted(set(ids))


def test_skip_forks(sample_projects):
    config = Config(skip_forks=True)
    discovery = RepoDiscovery(FakeClient(sample_projects), config)
    result = discovery.discover_starred()
    assert all(not p.is_fork for p in result)
    assert len(result) == 3  # alpha, gamma, delta


def test_forks_only(sample_projects):
    config = Config(forks_only=True)
    discovery = RepoDiscovery(FakeClient(sample_projects), config)
    result = discovery.discover_starred()
    assert all(p.is_fork for p in result)
    assert len(result) == 1  # beta only


def test_exclude_pattern(sample_projects):
    config = Config(exclude_patterns=["group/*"])
    discovery = RepoDiscovery(FakeClient(sample_projects), config)
    result = discovery.discover_starred()
    # "group/*" matches group/alpha, group/beta, and group/sub/gamma (fnmatch * matches /)
    paths = [p.path_with_namespace for p in result]
    assert "group/alpha" not in paths
    assert "group/beta" not in paths
    assert "other/delta" in paths


def test_exclude_pattern_specific(sample_projects):
    config = Config(exclude_patterns=["other/*"])
    discovery = RepoDiscovery(FakeClient(sample_projects), config)
    result = discovery.discover_starred()
    paths = [p.path_with_namespace for p in result]
    assert "other/delta" not in paths
    assert "group/alpha" in paths


def test_include_pattern(sample_projects):
    config = Config(include_patterns=["group/*"])
    discovery = RepoDiscovery(FakeClient(sample_projects), config)
    result = discovery.discover_starred()
    paths = [p.path_with_namespace for p in result]
    assert "group/alpha" in paths
    assert "group/beta" in paths
    assert "other/delta" not in paths


def test_sorted_output(sample_projects):
    config = Config()
    discovery = RepoDiscovery(FakeClient(sample_projects), config)
    result = discovery.discover_starred()
    paths = [p.path_with_namespace for p in result]
    assert paths == sorted(paths)
