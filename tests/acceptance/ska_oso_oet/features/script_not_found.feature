Scenario: File does not exist
    Given file <file> does not exist
    When the user runs oet create <file> command
    Then the OET returns an <error>

    Examples:
  | file                               | error                                       |
  | file:///FileNotFound.py            | No such file or directory: /FileNotFound.py |
