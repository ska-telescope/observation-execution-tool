Scenario: File does not exist
    Given file <file> does not exist
    When the user runs oet create <file> command
    Then the script should be in state FAILED after initialisation is finished
    And oet describe should show stacktrace with strings <error_strings>

    Examples:
  | file                               | error_strings                        |
  | file:///FileNotFound.py            | FileNotFoundError, /FileNotFound.py  |
