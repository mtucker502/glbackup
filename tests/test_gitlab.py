"""Tests for GlabClient with mocked subprocess calls."""

import json
import subprocess

import pytest

from gitlabbackup.gitlab import GlabClient, GlabError


@pytest.fixture
def client():
    return GlabClient(host="gitlab.example.com")


def test_check_auth_success(client, mocker):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    ))
    assert client.check_auth() is True


def test_check_auth_failure(client, mocker):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="not authenticated"
    ))
    assert client.check_auth() is False


def test_check_auth_not_installed(client, mocker):
    mocker.patch("subprocess.run", side_effect=FileNotFoundError)
    assert client.check_auth() is False


def test_list_starred_projects(client, mocker, api_project_data):
    projects_json = json.dumps([api_project_data])
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout=projects_json, stderr=""
    ))
    projects = client.list_starred_projects()
    assert len(projects) == 1
    assert projects[0].id == 42
    assert projects[0].name == "myproject"


def test_get_group_by_path(client, mocker):
    group_data = {"id": 10, "name": "mygroup", "full_path": "org/mygroup"}
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout=json.dumps(group_data), stderr=""
    ))
    group = client.get_group_by_path("org/mygroup")
    assert group.id == 10
    assert group.full_path == "org/mygroup"


def test_api_error(client, mocker):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="404 not found"
    ))
    with pytest.raises(GlabError, match="404 not found"):
        client.list_starred_projects()


def test_empty_response(client, mocker):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    ))
    projects = client.list_starred_projects()
    assert projects == []
