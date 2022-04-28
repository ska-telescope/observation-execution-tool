import os
import shutil
import unittest.mock as mock

import pytest
from git import Git, Repo

from ska_oso_oet.procedure.gitmanager import GitArgs, GitManager


@pytest.fixture(scope="module")
def manager():
    """
    Pytest fixture to return a prepared ProcessManager
    """
    mgr = GitManager()
    mgr.base_dir = os.getcwd() + "/test_clones/"
    yield mgr
    shutil.rmtree(mgr.base_dir, ignore_errors=True)


def test_get_project_name():
    git_repo_with_git = "https://gitlab.com/ska-telescope/ska-oso-scripting.git"
    git_repo_no_git = "https://gitlab.com/ska-telescope/ska-oso-scripting"

    expected = "ska-telescope-ska-oso-scripting"

    name_with_git = GitManager._get_project_name(  # pylint: disable=protected-access
        git_repo_with_git
    )
    name_no_git = GitManager._get_project_name(  # pylint: disable=protected-access
        git_repo_no_git
    )

    assert name_with_git == expected
    assert name_no_git == expected


@mock.patch.object(Repo, "clone_from")
@mock.patch.object(GitManager, "get_commit_hash")
def test_clone_not_done_if_already_cloned(mock_commit_hash_fn, mock_clone_fn, manager):
    commit = "123abc"
    mock_commit_hash_fn.side_effect = [commit]

    # Add the commit to manager's list as if it has been previously cloned
    manager._clones["fake-repo-name"] = []  # pylint: disable=protected-access
    manager._clones["fake-repo-name"].append(commit)  # pylint: disable=protected-access

    manager.clone_repo(GitArgs(git_repo="https://test.com/fake-repo-name.git"))
    mock_clone_fn.assert_not_called()


@mock.patch.object(Repo, "clone_from")
@mock.patch.object(GitManager, "get_commit_hash")
def test_repo_is_shallow_cloned_from_main_when_defaults_given(
    mock_commit_hash_fn, mock_clone_fn, manager
):
    commit = "abcd123"
    mock_commit_hash_fn.side_effect = [commit]
    mock_clone_fn.side_effect = mock_clone_repo
    manager.clone_repo(
        GitArgs(),
    )

    expected_path = manager.base_dir + "ska-telescope-ska-oso-scripting/" + commit + "/"

    mock_clone_fn.assert_called_once_with(
        "https://gitlab.com/ska-telescope/ska-oso-scripting.git",
        expected_path,
        depth=1,
        single_branch=True,
        branch="master",
    )
    assert (
        commit
        in manager._clones[  # pylint: disable=protected-access
            "ska-telescope-ska-oso-scripting"
        ]
    )
    assert "initial-file.txt" in os.listdir(expected_path)


@mock.patch.object(Repo, "clone_from")
@mock.patch.object(GitManager, "get_commit_hash")
def test_repo_is_shallow_cloned_from_branch(
    mock_commit_hash_fn, mock_clone_fn, manager
):
    commit = "def456"
    mock_commit_hash_fn.side_effect = [commit]
    mock_clone_fn.side_effect = mock_clone_repo
    manager.clone_repo(
        GitArgs(git_branch="feature-branch"),
    )
    expected_path = manager.base_dir + "ska-telescope-ska-oso-scripting/" + commit + "/"

    mock_clone_fn.assert_called_once_with(
        "https://gitlab.com/ska-telescope/ska-oso-scripting.git",
        expected_path,
        depth=1,
        single_branch=True,
        branch="feature-branch",
    )

    assert (
        commit
        in manager._clones[  # pylint: disable=protected-access
            "ska-telescope-ska-oso-scripting"
        ]
    )
    assert "initial-file.txt" in os.listdir(expected_path)


@mock.patch.object(Repo, "clone_from")
@mock.patch.object(GitManager, "get_commit_hash")
def test_repo_is_full_cloned_and_commit_checked_out_when_hash_given(
    mock_commit_hash_fn, mock_clone_fn, test_repo, manager
):
    commit = test_repo[2]
    mock_commit_hash_fn.side_effect = [commit]
    # This test is cheating slightly as it is not the mocked function which creates the repo but the pytest fixture
    # To call the method with a hash, the repo needs to be created before the call.
    mock_clone_fn.return_value = None
    manager.clone_repo(
        GitArgs(git_repo="http://gitlab.com/test-repo", git_commit=commit)
    )
    expected_path = manager.base_dir + "test-repo/" + commit + "/"

    mock_clone_fn.assert_called_once_with(
        "http://gitlab.com/test-repo",
        expected_path,
    )

    assert commit in manager._clones["test-repo"]  # pylint: disable=protected-access
    assert "initial-file.txt" in os.listdir(expected_path)
    assert "feature-a-file.txt" in os.listdir(expected_path)


@mock.patch.object(Git, "_call_process")
def test_get_hash_when_branch_given(mock_ls_remote_fn, manager):
    mock_ls_remote_fn.return_value = (
        "69e93d57916f837ee93ca125f2785f0f6e21974d\\feature_branch"
    )
    result = manager.get_commit_hash(
        GitArgs(git_repo="https://gitlab.com/", git_branch="feature_branch")
    )

    assert mock_ls_remote_fn.call_args == mock.call(
        "ls_remote", "-h", "https://gitlab.com/", "feature_branch"
    )
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result


@mock.patch.object(Git, "_call_process")
def test_get_hash_from_main_branch_when_branch_not_given(mock_ls_remote_fn, manager):
    mock_ls_remote_fn.return_value = "69e93d57916f837ee93ca125f2785f0f6e21974d\\main"
    result = manager.get_commit_hash(GitArgs(git_repo="https://gitlab.com/"))

    assert mock_ls_remote_fn.call_args == mock.call(
        "ls_remote", "https://gitlab.com/", "HEAD"
    )
    assert "69e93d57916f837ee93ca125f2785f0f6e21974d" == result


def test_checkout_commit(test_repo, manager):
    """Test that the _checkout_commit function checks out the given commit. Do this
    in the main test-repo instead of the repos for individual hashes."""
    test_repo_path = manager.base_dir + "test-repo/"
    manager._checkout_commit(  # pylint: disable=protected-access
        location=test_repo_path, hexsha=test_repo[0]
    )

    assert "initial-file.txt" in os.listdir(test_repo_path)
    assert "feature-a-file.txt" not in os.listdir(test_repo_path)

    manager._checkout_commit(  # pylint: disable=protected-access
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


@pytest.fixture(scope="module")
def test_repo(manager):
    """Creates a git repository, test-repo with two commits on main branch and one
    commit on a feature branch, feature_a. Creates a separate sub-folder for each commit
    and clones the repository state at that commit into the sub-folder, this is to mock
    the way GitManager would do cloning (path is manager.base_dir/project_name/commit)"""
    # Remove any existing repo and initialise a new one
    repo_dir = manager.base_dir + "test-repo/"
    shutil.rmtree(repo_dir, ignore_errors=True)
    test_repo = Repo.init(repo_dir)

    # Commit changes to the main branch
    file = open(repo_dir + "initial-file.txt", "x", encoding="utf-8")
    file.write("This is the first file.")
    file.close()
    test_repo.index.add(["initial-file.txt"])
    first = test_repo.index.commit("Initial commit! Directly to main branch")
    _ = Repo.clone_from(repo_dir, repo_dir + first.hexsha)

    file = open(repo_dir + "initial-file.txt", "a", encoding="utf-8")
    file.write("Adding to the first file.")
    file.close()
    test_repo.index.add(["initial-file.txt"])
    second = test_repo.index.commit("Some updates on the main branch")
    _ = Repo.clone_from(repo_dir, repo_dir + second.hexsha)

    # Commit changes to a feature branch
    test_repo.git.checkout("-b", "feature_a")
    file = open(repo_dir + "feature-a-file.txt", "x", encoding="utf-8")
    file.write("This a file on the feature_a branch.")
    file.close()
    test_repo.index.add(["feature-a-file.txt"])
    third = test_repo.index.commit("First Feature A file")
    _ = Repo.clone_from(repo_dir, repo_dir + third.hexsha, branch="feature_a")

    # As the hash depends on the time of the commit, it changes each time the test runs
    # We need to return the hashes from the test repo, so they can be asserted against
    return [first.hexsha, second.hexsha, third.hexsha]
