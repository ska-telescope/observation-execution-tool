import os
import shutil
import unittest.mock as mock

import pytest
from git import Git, Repo

from ska_oso_oet.procedure.domain import GitArgs
from ska_oso_oet.procedure.gitmanager import (
    _checkout_commit,
    clone_repo,
    get_commit_hash,
)


@mock.patch.object(Repo, "clone_from")
def test_repo_is_shallow_cloned_from_main_when_defaults_given(mock_clone_fn):
    mock_clone_fn.side_effect = mock_clone_repo
    clone_repo(
        GitArgs(),
        location="~/ska/tmp/ska-oso-scripting",
    )

    mock_clone_fn.assert_called_once_with(
        "https://gitlab.com/ska-telescope/ska-oso-scripting.git",
        os.path.expanduser("~/ska/tmp/ska-oso-scripting"),
        depth=1,
        single_branch=True,
        branch="master",
    )
    assert "initial-file.txt" in os.listdir(
        os.path.expanduser("~/ska/tmp/ska-oso-scripting")
    )


@mock.patch.object(Repo, "clone_from")
def test_repo_is_shallow_cloned_from_branch(mock_clone_fn):
    mock_clone_fn.side_effect = mock_clone_repo
    clone_repo(
        GitArgs(git_branch="feature-branch"),
        location="~/ska/tmp/ska-oso-scripting",
    )

    mock_clone_fn.assert_called_once_with(
        "https://gitlab.com/ska-telescope/ska-oso-scripting.git",
        os.path.expanduser("~/ska/tmp/ska-oso-scripting"),
        depth=1,
        single_branch=True,
        branch="feature-branch",
    )
    assert "initial-file.txt" in os.listdir(
        os.path.expanduser("~/ska/tmp/ska-oso-scripting")
    )


@mock.patch.object(Repo, "clone_from")
def test_repo_is_full_cloned_and_commit_checked_out_when_hash_given(
    mock_clone_fn, test_repo
):
    # This test is cheating slightly as it is not the mocked function which creates the repo but the pytest fixture
    # To call the method with a hash, the repo needs to be created before the call.
    mock_clone_fn.return_value = None
    clone_repo(GitArgs(git_commit=test_repo[2]), location="~/ska/tmp/test-repo")

    mock_clone_fn.assert_called_once_with(
        "https://gitlab.com/ska-telescope/ska-oso-scripting.git",
        os.path.expanduser("~/ska/tmp/test-repo"),
    )
    assert "initial-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/test-repo"))
    assert "feature-a-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/test-repo"))


@mock.patch.object(Git, "_call_process")
def test_get_hash_when_tag_given(mock_ls_remote_fn):
    mock_ls_remote_fn.return_value = (
        "69e93d57916f837ee93ca125f2785f0f6e21974d\\refs/tags/1.3.2"
    )
    result = get_commit_hash(git_url="https://gitlab.com/", git_tag="1.3.2")

    assert mock_ls_remote_fn.call_args == mock.call(
        "ls_remote", "-t", "https://gitlab.com/", "1.3.2"
    )
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result


@mock.patch.object(Git, "_call_process")
def test_get_hash_when_branch_given(mock_ls_remote_fn):
    mock_ls_remote_fn.return_value = (
        "69e93d57916f837ee93ca125f2785f0f6e21974d\\feature_branch"
    )
    result = get_commit_hash(git_url="https://gitlab.com/", git_branch="feature_branch")

    assert mock_ls_remote_fn.call_args == mock.call(
        "ls_remote", "-h", "https://gitlab.com/", "feature_branch"
    )
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result


@mock.patch.object(Git, "_call_process")
def test_get_hash_from_main_branch_when_branch_or_tag_not_given(mock_ls_remote_fn):
    mock_ls_remote_fn.return_value = "69e93d57916f837ee93ca125f2785f0f6e21974d\\main"
    result = get_commit_hash(git_url="https://gitlab.com/")

    assert mock_ls_remote_fn.call_args == mock.call(
        "ls_remote", "https://gitlab.com/", "HEAD"
    )
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result


@mock.patch.object(Git, "_call_process")
def test_get_hash_tag_precedence_when_branch_also_given(mock_ls_remote_fn):
    mock_ls_remote_fn.return_value = (
        "69e93d57916f837ee93ca125f2785f0f6e21974d\\refs/tags/1.3.2"
    )
    result = get_commit_hash(git_url="https://gitlab.com/", git_tag="1.3.2")

    assert mock_ls_remote_fn.call_args == mock.call(
        "ls_remote", "-t", "https://gitlab.com/", "1.3.2"
    )
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result


def test_checkout_commit(test_repo):
    _checkout_commit(location="~/ska/tmp/test-repo", hexsha=test_repo[2])

    assert "initial-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/test-repo"))
    assert "feature-a-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/test-repo"))

    _checkout_commit(location="~/ska/tmp/test-repo", hexsha=test_repo[0])

    assert "initial-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/test-repo"))
    assert "feature-a-file.txt" not in os.listdir(
        os.path.expanduser("~/ska/tmp/test-repo")
    )


def mock_clone_repo(
    git_url: str, location: str, **kwargs
):  # pylint: disable=unused-argument
    # Remove any existing repo and initialise a new one
    shutil.rmtree(location, ignore_errors=True)
    test_repo = Repo.init(location)

    # Commit changes to the main branch
    file = open(f"{location}/initial-file.txt", "x", encoding="utf-8")
    file.write("This is the first file.")
    file.close()
    test_repo.index.add(["initial-file.txt"])
    first = test_repo.index.commit("Initial commit! Directly to main branch")
    return first.hexsha


@pytest.fixture
def test_repo():
    # Remove any existing repo and initialise a new one
    shutil.rmtree(os.path.expanduser("~/ska/tmp/test-repo"), ignore_errors=True)
    test_repo = Repo.init(os.path.expanduser("~/ska/tmp/test-repo"))

    # Commit changes to the main branch
    file = open(
        os.path.expanduser("~/ska/tmp/test-repo/initial-file.txt"),
        "x",
        encoding="utf-8",
    )
    file.write("This is the first file.")
    file.close()
    test_repo.index.add(["initial-file.txt"])
    first = test_repo.index.commit("Initial commit! Directly to main branch")

    file = open(
        os.path.expanduser("~/ska/tmp/test-repo/initial-file.txt"),
        "a",
        encoding="utf-8",
    )
    file.write("Adding to the first file.")
    file.close()
    test_repo.index.add(["initial-file.txt"])
    second = test_repo.index.commit("Some updates on the main branch")

    # Commit changes to a feature branch
    test_repo.git.checkout("-b", "feature_a")
    file = open(
        os.path.expanduser("~/ska/tmp/test-repo/feature-a-file.txt"),
        "x",
        encoding="utf-8",
    )
    file.write("This a file on the feature_a branch.")
    file.close()
    test_repo.index.add(["feature-a-file.txt"])
    third = test_repo.index.commit("First Feature A file")

    # As the hash depends on the time of the commit, it changes each time the test runs
    # We need to return the hashes from the test repo, so they can be asserted against
    return [first.hexsha, second.hexsha, third.hexsha]
