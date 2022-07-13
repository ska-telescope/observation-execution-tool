Scenario: Script creation on default environment fails when creating a script from git
    Given git repository /tmp/test_repo and script git://demo.py within the repository exist
    When the user runs oet create with arguments git://demo.py --git_repo=/tmp/test_repo
    Then the script should go to state FAILED
    And oet describe should show stacktrace with ModuleNotFoundError

Scenario: User creates a script with non-default dependencies from git using OET
    Given git repository /tmp/test_repo and script git://demo.py within the repository exist
    When the user runs oet create with arguments git://demo.py --git_repo=/tmp/test_repo --create_env=True
    Then the script should be in state READY after execution is finished

