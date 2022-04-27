"""
Static helper functions for cloning and working with a Git repository
"""
import dataclasses
import os
from typing import Optional

from git import Git, Repo


@dataclasses.dataclass
class GitArgs:
    """
    GitArgs captures information required to identify scripts
    located in git repositories.
    """

    git_repo: Optional[str] = "https://gitlab.com/ska-telescope/ska-oso-scripting.git"
    git_branch: Optional[str] = "master"
    git_commit: Optional[str] = None


def clone_repo(git_args: GitArgs, location: str) -> None:
    """
    Clone a remote repository into the local filesystem, with the HEAD pointing to the revision defined in the input

    :param git_args: Information about the repository and the required point in its history
    :param location: The filepath location to clone into. Can pass an absolute, relative or home directory path

    :return: None, but has the side effect of adding the repo to the location
        If a Git commit hash is not supplied, a shallow clone of the branch is done, minimising the data transferred over the network
        If a Git commit hash is supplied, the full repo must be cloned and then the commit checked out,
        as Git doesn't allow a specific commit to be cloned
    """
    clone_dir = os.path.abspath(os.path.expanduser(location))

    clone_args = {}
    if not git_args.git_commit:
        clone_args["depth"] = 1
        clone_args["single_branch"] = True
        clone_args["branch"] = git_args.git_branch

    Repo.clone_from(git_args.git_repo, clone_dir, **clone_args)

    if git_args.git_commit:
        _checkout_commit(clone_dir, git_args.git_commit)


def get_commit_hash(
    git_args: GitArgs, short_hash=False
) -> str:
    """
    Get a commit hash from a remote repository

    :param git_args: Arguments to point to git environment to get hash for

    :return: The SHA for the specified commit.
        If a tag and a branch are both supplied, the tag takes precedence.
        If neither are supplied, the latest commit on the default branch is used
    """
    if git_args.git_commit:
        return git_args.git_commit

    if git_args.git_branch is not "master":
        response = Git().ls_remote("-h", git_args.git_repo, git_args.git_branch)
    else:
        response = Git().ls_remote(git_args.git_repo, "HEAD")
    if short_hash:
        return response[:7]
    return response.split("\\")[0]


def _checkout_commit(location: str, hexsha: str) -> None:
    """
    Checkout an existing repository to a specific commit

    :param location: The filepath location of the repository
    :param hexsha: The commit SHA to checkout

    :return: None, but has the side effect changing the files
        inside the repository to the state they were in at the commit
    """
    path = os.path.abspath(os.path.expanduser(location))
    Repo(path).git.checkout(hexsha)
