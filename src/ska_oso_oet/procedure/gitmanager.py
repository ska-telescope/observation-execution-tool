"""
Static helper functions for cloning and working with a Git repository
"""
import os
from pydantic import BaseModel
from typing import Optional
from urllib.parse import urlparse

from git import Git, Repo


class GitArgs(BaseModel):
    """
    GitArgs captures information required to identify scripts
    located in git repositories.
    """

    git_repo: Optional[
        str
    ] = "https://gitlab.com/ska-telescope/oso/ska-oso-scripting.git"
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None

    def __post_init__(self):
        # We only want to set the default branch if the commit isn't set, as the user
        # might just give a commit hash from a feature branch
        if self.git_branch is None and self.git_commit is None:
            self.git_branch = "master"


class GitManager:
    base_dir = "/tmp/clones/"

    @staticmethod
    def clone_repo(git_args: GitArgs) -> str:
        """
        Clone a remote repository into the local filesystem, with the HEAD pointing to the revision
        defined in the input

        If a Git commit hash is not supplied, a shallow clone of the branch is done, minimising the
        data transferred over the network. If a Git commit hash is supplied, the full repo must be
        cloned and then the commit checked out, as Git doesn't allow a specific commit to be cloned

        :param git_args: Information about the repository and the required point in its history

        :return: Returns the location of the cloned project
        """
        git_commit = GitManager.get_commit_hash(git_args)
        clone_args = {}
        if not git_args.git_commit:
            clone_args["depth"] = 1
            clone_args["single_branch"] = True
            clone_args["branch"] = git_args.git_branch

        project_name = GitManager.get_project_name(git_args.git_repo)
        clone_dir = GitManager.base_dir + project_name + "/" + git_commit

        if os.path.exists(clone_dir):
            return clone_dir

        Repo.clone_from(git_args.git_repo, clone_dir, **clone_args)

        if not os.path.exists(clone_dir):
            raise IOError(
                "Something went wrong when cloning the project, directory"
                f" {clone_dir} does not exist"
            )

        if git_args.git_commit:
            GitManager._checkout_commit(clone_dir, git_args.git_commit)

        return clone_dir

    @staticmethod
    def get_commit_hash(git_args: GitArgs, short_hash=False) -> str:
        """
        Get a commit hash from a remote repository

        :param git_args: Arguments to point to git environment to get hash for
        :param short_hash: Return first 7 characters of the hash

        :return: The SHA for the specified commit.
            If a tag and a branch are both supplied, the tag takes precedence.
            If neither are supplied, the latest commit on the default branch is used
        """
        if git_args.git_commit:
            return git_args.git_commit

        if git_args.git_branch != "master":
            response = Git().ls_remote("-h", git_args.git_repo, git_args.git_branch)
        else:
            response = Git().ls_remote(git_args.git_repo, "HEAD")
        if short_hash:
            return response[:7]
        return response[:40]

    @staticmethod
    def get_project_name(git_repo: str):
        """Get the git project name including full folder tree to avoid project
        name clashes (e.g. name for project at http://gitlab.com/ska-telescope/oso/ska-oso-scripting
        is ska-telescope-oso-ska-oso-scripting)"""
        return urlparse(git_repo).path[1:].replace("/", "-").split(".")[0]

    @staticmethod
    def _checkout_commit(location: str, hexsha: str) -> None:
        """
        Checkout an existing repository to a specific commit

        :param location: The filepath location of the repository
        :param hexsha: The commit SHA to check out

        :return: None, but has the side effect changing the files
            inside the repository to the state they were in at the commit
        """
        path = os.path.abspath(location)
        Repo(path).git.checkout(hexsha)
