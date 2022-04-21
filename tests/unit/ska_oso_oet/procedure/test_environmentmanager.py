import datetime
import multiprocessing
import os.path
import subprocess
import unittest.mock as mock
import venv

from ska_oso_oet.procedure.domain import GitArgs
from ska_oso_oet.procedure.environment import Environment, EnvironmentManager

TEST_ENVIRONMENT = Environment(
    creating_condition=multiprocessing.Condition(),
    created_condition=multiprocessing.Condition(),
    env_id="69e93d57916f837ee93ca125f2785f0f6e21974d",
    created=datetime.datetime(2000, 1, 1),
    site_packages="/tmp/environments/69e93d57916f837ee93ca125f2785f0f6e21974d/venv/lib/python3.7/site-packages",
)


def test_environment_is_returned_when_hash_exists():
    environment_manager = EnvironmentManager()
    environment_manager._envs = {  # pylint: disable=protected-access
        "69e93d57916f837ee93ca125f2785f0f6e21974d": TEST_ENVIRONMENT
    }

    result = environment_manager.create_env(
        GitArgs(git_commit="69e93d57916f837ee93ca125f2785f0f6e21974d")
    )
    assert result == TEST_ENVIRONMENT


@mock.patch("ska_oso_oet.procedure.environment.get_commit_hash")
@mock.patch.object(venv, "create")
@mock.patch.object(subprocess, "run")
def test_environment_is_created_when_hash_is_new(
    mock_subprocess_fn, mock_venv_fn, mock_git_fn
):
    mock_git_fn.return_value = "69e93d57916f837ee93ca125f2785f0f6e21974d"
    mock_venv_fn.side_effect = None
    mock_subprocess_fn.return_value = subprocess.CompletedProcess(
        args="",
        returncode=1,
        stdout=bytes(
            "/tmp/environments/69e93d57916f837ee93ca125f2785f0f6e21974d/venv/lib/python3.7/site-packages",
            "utf-8",
        ),
    )
    environment_manager = EnvironmentManager()

    result = environment_manager.create_env(GitArgs())

    assert 1 == len(environment_manager._envs)  # pylint: disable=protected-access
    assert result.env_id == "69e93d57916f837ee93ca125f2785f0f6e21974d"
    assert (
        result.site_packages
        == "/tmp/environments/69e93d57916f837ee93ca125f2785f0f6e21974d/venv/lib/python3.7/site-packages"
    )


def test_delete_env():
    environment_manager = EnvironmentManager()
    environment_manager._envs = {  # pylint: disable=protected-access
        "69e93d57916f837ee93ca125f2785f0f6e21974d": TEST_ENVIRONMENT
    }
    venv.create(
        env_dir="/tmp/environments/69e93d57916f837ee93ca125f2785f0f6e21974d/venv",
        clear=True,
        system_site_packages=False,
        with_pip=False,
        symlinks=False,
    )

    environment_manager.delete_env("69e93d57916f837ee93ca125f2785f0f6e21974d")

    assert 0 == len(environment_manager._envs)  # pylint: disable=protected-access
    assert not os.path.exists(
        "/tmp/environments/69e93d57916f837ee93ca125f2785f0f6e21974d/"
    )
