Feature: Tests of the Procedure domain that runs scripts from Git

    Scenario: Script creation on default environment fails when creating a script from git
        Given git repository /tmp/tests/test_repo and script git://demo.py within the repository exist
        When the user runs oet create with arguments git://demo.py --git_repo=/tmp/tests/test_repo
        Then the script should be in FAILED after execution is finished
        And oet describe should show stacktrace with ModuleNotFoundError

    Scenario: User creates a script with non-default dependencies from git using OET
        Given git repository /tmp/tests/test_repo and script git://demo.py within the repository exist
        When the user runs oet create with arguments git://demo.py --git_repo=/tmp/tests/test_repo --create_env=True
        Then the script should be in READY after execution is finished

    Scenario: User runs a script with non-default dependencies from git using OET
        Given script git://demo.py has been created with arguments --git_repo=/tmp/tests/test_repo --create_env=True
        When the user runs oet start command to execute the script
        Then the script should be in COMPLETE after execution is finished

