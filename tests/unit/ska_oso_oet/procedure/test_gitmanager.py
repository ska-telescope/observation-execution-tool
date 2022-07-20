import os
import shutil
import tempfile
import unittest.mock as mock

import pytest
from git import Git, Repo

from ska_oso_oet.procedure.gitmanager import GitArgs, GitManager


@pytest.fixture(name="base_dir", scope="module")
def fixture_base_dir():
    """
    Pytest fixture to return a base directory to clone repositories into during
    test execution. Anything cloned there will be cleaned up when module tests are
    completed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_get_project_name():
    git_repo_with_git = "https://gitlab.com/ska-telescope/ska-oso-scripting.git"
    git_repo_no_git = "https://gitlab.com/ska-telescope/ska-oso-scripting"

    expected = "ska-telescope-ska-oso-scripting"

    name_with_git = GitManager.get_project_name(git_repo_with_git)
    name_no_git = GitManager.get_project_name(git_repo_no_git)

    assert name_with_git == expected
    assert name_no_git == expected


@mock.patch.object(Repo, "clone_from")
@mock.patch.object(GitManager, "get_commit_hash")
def test_clone_not_done_if_already_cloned(mock_commit_hash_fn, mock_clone_fn):
    commit = "123abc"
    mock_commit_hash_fn.side_effect = [commit]

    with mock.patch("os.path.exists") as mock_exists:
        mock_exists.side_effect = [True]
        GitManager.clone_repo(GitArgs(git_repo="https://test.com/fake-repo-name.git"))
    mock_clone_fn.assert_not_called()


@mock.patch.object(Repo, "clone_from")
@mock.patch.object(GitManager, "get_commit_hash")
def test_repo_is_shallow_cloned_from_main_when_defaults_given(
    mock_commit_hash_fn, mock_clone_fn, base_dir
):
    GitManager.base_dir = base_dir
    commit = "abcd123"
    mock_commit_hash_fn.side_effect = [commit]
    mock_clone_fn.side_effect = mock_clone_repo
    GitManager.clone_repo(GitArgs())

    expected_path = base_dir + "ska-telescope-ska-oso-scripting/" + commit

    mock_clone_fn.assert_called_once_with(
        "https://gitlab.com/ska-telescope/ska-oso-scripting.git",
        expected_path,
        depth=1,
        single_branch=True,
        branch="master",
    )
    assert "initial-file.txt" in os.listdir(expected_path)


@mock.patch.object(Repo, "clone_from")
@mock.patch.object(GitManager, "get_commit_hash")
def test_repo_is_shallow_cloned_from_branch(
    mock_commit_hash_fn, mock_clone_fn, base_dir
):
    GitManager.base_dir = base_dir
    commit = "def456"
    mock_commit_hash_fn.side_effect = [commit]
    mock_clone_fn.side_effect = mock_clone_repo
    GitManager.clone_repo(
        GitArgs(git_branch="feature-branch"),
    )
    expected_path = base_dir + "ska-telescope-ska-oso-scripting/" + commit

    mock_clone_fn.assert_called_once_with(
        "https://gitlab.com/ska-telescope/ska-oso-scripting.git",
        expected_path,
        depth=1,
        single_branch=True,
        branch="feature-branch",
    )

    assert "initial-file.txt" in os.listdir(expected_path)


@mock.patch.object(GitManager, "get_commit_hash")
@mock.patch.object(GitManager, "get_project_name")
def test_repo_is_full_cloned_and_commit_checked_out_when_hash_given(
    mock_proj_name_fn, mock_commit_hash_fn, test_repo, base_dir
):
    GitManager.base_dir = base_dir
    commit = test_repo[2]
    mock_commit_hash_fn.side_effect = [commit]
    # Mock project name so that it doesn't include full test file structure in the name
    mock_proj_name_fn.side_effect = ["test-repo"]
    GitManager.clone_repo(
        GitArgs(git_repo=f"file://{base_dir}test-repo", git_commit=commit)
    )
    expected_path = base_dir + "test-repo/" + commit

    assert "initial-file.txt" in os.listdir(expected_path)
    assert "feature-a-file.txt" in os.listdir(expected_path)


@mock.patch.object(Repo, "clone_from")
@mock.patch.object(GitManager, "get_commit_hash")
def test_clone_raises_error_if_clone_dir_not_found(
    mock_commit_hash_fn, mock_clone_fn, base_dir  # pylint: disable=unused-argument
):
    GitManager.base_dir = base_dir
    commit = "ghi789"
    mock_commit_hash_fn.side_effect = [commit]

    with pytest.raises(IOError):
        GitManager.clone_repo(GitArgs())


@mock.patch.object(Git, "_call_process")
def test_get_hash_when_branch_given(mock_ls_remote_fn):
    mock_ls_remote_fn.side_effect = [
        "69e93d57916f837ee93ca125f2785f0f6e21974d\\feature_branch",
        "69e93d57916f837ee93ca125f2785f0f6e21974d\tfeature_branch",
    ]
    result1 = GitManager.get_commit_hash(
        GitArgs(git_repo="https://gitlab.com/", git_branch="feature_branch")
    )
    result2 = GitManager.get_commit_hash(
        GitArgs(git_repo="https://gitlab.com/", git_branch="feature_branch")
    )

    assert mock_ls_remote_fn.call_args == mock.call(
        "ls_remote", "-h", "https://gitlab.com/", "feature_branch"
    )
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result1
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result2


@mock.patch.object(Git, "_call_process")
def test_get_hash_from_main_branch_when_branch_not_given(mock_ls_remote_fn):
    mock_ls_remote_fn.return_value = "69e93d57916f837ee93ca125f2785f0f6e21974d\\main"
    result = GitManager.get_commit_hash(GitArgs(git_repo="https://gitlab.com/"))

    assert mock_ls_remote_fn.call_args == mock.call(
        "ls_remote", "https://gitlab.com/", "HEAD"
    )
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result


def test_checkout_commit(test_repo, base_dir):
    """Test that the _checkout_commit function checks out the given commit. Do this
    in the main test-repo instead of the repos for individual hashes."""
    test_repo_path = base_dir + "test-repo/"
    GitManager._checkout_commit(  # pylint: disable=protected-access
        location=test_repo_path, hexsha=test_repo[0]
    )

    assert "initial-file.txt" in os.listdir(test_repo_path)
    assert "feature-a-file.txt" not in os.listdir(test_repo_path)

    GitManager._checkout_commit(  # pylint: disable=protected-access
        location=test_repo_path, hexsha=test_repo[2]
    )

    assert "initial-file.txt" in os.listdir(test_repo_path)
    assert "feature-a-file.txt" in os.listdir(test_repo_path)


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


@pytest.fixture(name="test_repo", scope="module")
def fixture_test_repo(base_dir):
    """Creates a git repository, test-repo with two commits on main branch and one
    commit on a feature branch, feature_a."""
    # Remove any existing repo and initialise a new one
    repo_dir = base_dir + "test-repo/"
    shutil.rmtree(repo_dir, ignore_errors=True)
    test_repo = Repo.init(repo_dir)

    # Commit changes to the main branch
    file = open(repo_dir + "initial-file.txt", "x", encoding="utf-8")
    file.write("This is the first file.")
    file.close()
    test_repo.index.add(["initial-file.txt"])
    first = test_repo.index.commit("Initial commit! Directly to main branch")

    file = open(repo_dir + "initial-file.txt", "a", encoding="utf-8")
    file.write("Adding to the first file.")
    file.close()
    test_repo.index.add(["initial-file.txt"])
    second = test_repo.index.commit("Some updates on the main branch")

    # Commit changes to a feature branch
    test_repo.git.checkout("-b", "feature_a")
    file = open(repo_dir + "feature-a-file.txt", "x", encoding="utf-8")
    file.write("This a file on the feature_a branch.")
    file.close()
    test_repo.index.add(["feature-a-file.txt"])
    third = test_repo.index.commit("First Feature A file")

    # As the hash depends on the time of the commit, it changes each time the test runs
    # We need to return the hashes from the test repo, so they can be asserted against
    return [first.hexsha, second.hexsha, third.hexsha]
