Scenario: File does not exist
    Given file <file> does not exist
    When the user runs oet create <file> command
    Then the script should be in state FAILED after initialisation is finished
    And oet describe should show stacktrace with the <error>

    Examples:
  | file                               | error                                       |
  | file:///FileNotFound.py            | No such file or directory: /FileNotFound.py |
