import multiprocessing
import os.path
import subprocess
import tempfile
import unittest.mock as mock
import venv

import pytest

from ska_oso_oet.procedure.environment import Environment, EnvironmentManager
from ska_oso_oet.procedure.gitmanager import GitArgs


@pytest.fixture(scope="module")
def env_manager():
    """
    Pytest fixture to return EnvironmentManager object. The fixture sets base directory on
    the manager object for the duration of the tests and cleans up any files in the directory
    when test run is complete.
    """
    with tempfile.TemporaryDirectory() as tempdir:
        yield EnvironmentManager(base_dir=tempdir)


@pytest.fixture()
def env_object(env_manager):
    """
    Pytest fixture to return EnvironmentManager object. The fixture sets base directory on
    the manager object for the duration of the tests and cleans up any files in the directory
    when test run is complete.
    """
    env = Environment(
        env_id="69e93d57916f837ee93ca125f2785f0f6e21974d",
        created=multiprocessing.Event(),
        creating=multiprocessing.Event(),
        location=f"{env_manager.base_dir}69e93d57916f837ee93ca125f2785f0f6e21974d",
        site_packages=f"{env_manager.base_dir}69e93d57916f837ee93ca125f2785f0f6e21974d/venv/lib/python3.7/site-packages",
    )
    return env


def test_environment_is_returned_when_hash_exists(env_manager, env_object):
    commit = "69e93d57916f837ee93ca125f2785f0f6e21974d"
    env_manager._envs = {  # pylint: disable=protected-access
        commit: env_object
    }

    result = env_manager.create_env(
        GitArgs(git_commit=commit)
    )
    assert result == env_object

    # Clean up after the test
    del env_manager._envs[commit]


@mock.patch("ska_oso_oet.procedure.environment.GitManager.get_commit_hash")
@mock.patch.object(venv, "create")
@mock.patch.object(subprocess, "run")
def test_environment_is_created_when_hash_is_new(
    mock_subprocess_fn, mock_venv_fn, mock_git_fn, env_manager
):
    commit = "69e93d57916f837ee93ca125f2785f0f6e21974d"
    mock_git_fn.return_value = commit
    mock_venv_fn.side_effect = None
    mock_subprocess_fn.return_value = subprocess.CompletedProcess(
        args="",
        returncode=1,
        stdout=bytes(
            f"{env_manager.base_dir}{commit}/venv/lib/python3.7/site-packages",
            "utf-8",
        ),
    )

    result = env_manager.create_env(GitArgs())

    assert 1 == len(env_manager._envs)  # pylint: disable=protected-access
    assert result.env_id == commit
    assert (
        result.site_packages
        == f"{env_manager.base_dir}{commit}/venv/lib/python3.7/site-packages"
    )
    del env_manager._envs[commit]


def test_delete_env(env_manager, env_object):
    env_manager._envs = {  # pylint: disable=protected-access
        "69e93d57916f837ee93ca125f2785f0f6e21974d": env_object
    }
    venv.create(
        env_dir=f"{env_manager.base_dir}69e93d57916f837ee93ca125f2785f0f6e21974d",
        clear=True,
        system_site_packages=False,
        with_pip=False,
        symlinks=False,
    )

    env_manager.delete_env("69e93d57916f837ee93ca125f2785f0f6e21974d")

    assert 0 == len(env_manager._envs)  # pylint: disable=protected-access
    assert not os.path.exists(
        f"{env_manager.base_dir}69e93d57916f837ee93ca125f2785f0f6e21974d/"
    )
