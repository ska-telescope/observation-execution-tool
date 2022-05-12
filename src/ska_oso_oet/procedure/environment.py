import dataclasses
import multiprocessing
import shutil
import subprocess
import venv

from ska_oso_oet.procedure.gitmanager import GitArgs, GitManager


@dataclasses.dataclass
class Environment:
    env_id: str
    creating: multiprocessing.Event  # Set when environment is being created
    created: multiprocessing.Event  # Set when environment is ready to be used
    location: str
    site_packages: str


class EnvironmentManager:
    def __init__(self):
        self._envs = {}
        self.base_dir = "/tmp/environments/"

    def create_env(self, git_args: GitArgs) -> Environment:
        if git_args.git_commit:
            git_commit = git_args.git_commit
        else:
            git_commit = GitManager.get_commit_hash(git_args)

        if git_commit in self._envs.keys():
            return self._envs.get(git_commit)

        project_name = GitManager.get_project_name(git_args.git_repo)

        # Create a new Python virtual environment and find its site packages directory
        venv_dir = f"{self.base_dir+project_name}/{git_commit}"
        venv.create(
            env_dir=venv_dir,
            clear=True,
            system_site_packages=True,
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
            env_id=git_commit,
            created=multiprocessing.Event(),
            creating=multiprocessing.Event(),
            location=venv_dir,
            site_packages=venv_site_pkgs,
        )
        self._envs[git_commit] = environment
        return self._envs[git_commit]

    def delete_env(self, env_id):
        env = self._envs[env_id]
        shutil.rmtree(env.location, ignore_errors=True)
        del self._envs[env_id]
