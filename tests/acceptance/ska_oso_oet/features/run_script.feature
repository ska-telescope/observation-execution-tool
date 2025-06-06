Feature: Tests of the Procedure domain that runs scripts from the filesystem

  Scenario Outline: User runs a script using OET
      Given script <script> has been created
      When the user runs oet start command
      Then the script should be in state <state> after execution is finished

      Examples:
    | script                              | state    |
    | file:///tmp/tests/scripts/success.py      | COMPLETE |
    | file:///tmp/tests/scripts/fail.py         | FAILED   |


  Scenario: OET stays responsive when script is running
      Given script file:///tmp/tests/scripts/loop.py has been created
      When script file:///tmp/tests/scripts/loop.py is running
      Then the oet list command response shows file:///tmp/tests/scripts/loop.py is running
