Scenario: Stop script execution
    Given script file:///tmp/tests/scripts/loop.py is running
    When the user runs oet stop command
    Then the script file:///tmp/tests/scripts/loop.py status is STOPPED

