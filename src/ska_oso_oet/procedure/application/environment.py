import dataclasses
import datetime
import multiprocessing
import subprocess
import venv

from ska_oso_oet.procedure.application.gitmanager import get_commit_hash
from ska_oso_oet.procedure.domain import GitArgs


@dataclasses.dataclass
class Environment:
    creating_condition: multiprocessing.Condition  # Set when environment is being created
    created_condition: multiprocessing.Condition  # Set when environment is ready to be used
    env_id: str
    created: datetime
    site_packages: []


class EnvironmentManager:
    def __init__(self):
        self._envs = {}

    def create_env(self, git_args: GitArgs, src_dir: str) -> Environment:
        if git_args.git_commit:
            git_commit = git_args.git_commit
        else:
            git_commit = get_commit_hash(
                git_args.git_repo, git_branch=git_args.git_branch
            )

        if git_commit in self._envs.keys():
            return self._envs.get(git_commit)

        # Create a new Python virtual environment and find its site packages directory
        venv_dir = f"{src_dir}/venv"
        venv.create(
            env_dir=venv_dir,
            clear=True,
            system_site_packages=False,
            with_pip=True,
            symlinks=True,
        )
        site_pkgs_call = subprocess.run(
            [
                f"{venv_dir}/bin/python",
                "-c",
                "import site; print(site.getsitepackages()[0])",
            ],
            capture_output=True,
            check=True,
        )
        venv_site_pkgs = site_pkgs_call.stdout.decode("utf-8").strip()

        environment = Environment(
            creating_condition=multiprocessing.Condition(),  # TODO
            created_condition=multiprocessing.Condition(),
            env_id=git_commit,
            created=datetime.datetime.now(),
            site_packages=venv_site_pkgs,
        )

        self._envs[git_commit] = environment
        return environment

    def delete_env(self, env_id):
        # TODO need to remove the venv, not sure how to do it with the current
        #  Environment as it doesnt contain the location
        del self._envs[env_id]
