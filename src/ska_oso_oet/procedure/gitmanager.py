"""
Static helper functions for cloning and working with a Git repository
"""
import os

from git import Git, Repo


def clone_repo(git_url: str, location: str) -> None:
    """
    Clone a remote repository into the local filesystem

    :param git_url: URL of the repository to clone
    :param location: The filepath location to clone into. Can pass an absolute, relative or home directory path

    :return: None, but has the side effect of adding the repo to the location
    """
    clone_dir = os.path.abspath(os.path.expanduser(location))
    Repo.clone_from(git_url, clone_dir)


def get_commit_hash(git_url: str, git_tag: str = None, git_branch: str = None) -> str:
    """
    Get a commit hash from a remote repository

    :param git_url: URL of the repository
    :param git_tag: The Git tag to find the corresponding commit hash for
    :param git_branch: The Git branch to find the corresponding latest commit hash for

    :return: The SHA for the specified commit.
        If a tag and a branch are both supplied, the tag takes precedence.
        If neither are supplied, the latest commit on the default branch is used
    """
    if git_tag:
        response = Git().ls_remote("-t", git_url, git_tag)
    elif git_branch:
        response = Git().ls_remote("-h", git_url, git_branch)
    else:
        response = Git().ls_remote(git_url, "HEAD")

    return response.split("\\")[0]


def checkout_commit(location: str, hexsha: str) -> None:
    """
    Checkout an existing repository to a specific commit

    :param location: The filepath location of the repository
    :param hexsha: The commit SHA to checkout

    :return: None, but has the side effect changing the files
        inside the repository to the state they were in at the commit
    """
    path = os.path.abspath(os.path.expanduser(location))
    Repo(path).git.checkout(hexsha)
