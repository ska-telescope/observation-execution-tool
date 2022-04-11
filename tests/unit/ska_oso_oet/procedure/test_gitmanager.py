import os
import shutil
import unittest.mock as mock

import pytest
from git import Git, Repo

from ska_oso_oet.procedure.gitmanager import (
    checkout_commit,
    clone_repo,
    get_commit_hash,
)


# For the functionality which makes calls to a remote repo,
# mock the response/side effect of the call
@mock.patch.object(Repo, "clone_from")
def test_repo_is_cloned(mock_clone_fn):
    mock_clone_fn.side_effect = mock_clone_repo
    clone_repo(
        git_url="https://gitlab.com/ska-telescope/ska-oso-pdm.git",
        location="~/ska/tmp/ska-oso-pdm",
    )

    assert "initial-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/ska-oso-pdm"))


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


def mock_clone_repo(git_url: str, location: str):  # pylint: disable=unused-argument
    # Remove any existing repo and initialise a new one
    shutil.rmtree(location, ignore_errors=True)
    test_repo = Repo.init(location)

    # Commit changes to the main branch
    file = open(f"{location}/initial-file.txt", "x", encoding="utf-8")
    file.write("This is the first file.")
    file.close()
    test_repo.index.add(["initial-file.txt"])
    test_repo.index.commit("Initial commit! Directly to main branch")


# For the functionality which mutates the state of an existing repo,
# use a PyTest fixture to create a repo to test against
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


def test_checkout_commit(test_repo):
    checkout_commit(location="~/ska/tmp/test-repo", hexsha=test_repo[2])

    assert "initial-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/test-repo"))
    assert "feature-a-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/test-repo"))

    checkout_commit(location="~/ska/tmp/test-repo", hexsha=test_repo[0])

    assert "initial-file.txt" in os.listdir(os.path.expanduser("~/ska/tmp/test-repo"))
    assert "feature-a-file.txt" not in os.listdir(
        os.path.expanduser("~/ska/tmp/test-repo")
    )
