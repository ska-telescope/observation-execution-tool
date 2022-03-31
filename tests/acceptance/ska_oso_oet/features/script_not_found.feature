Scenario: Invalid script filename on creation
    Given filename <file> is invalid
    When the user runs oet create <file> command
    Then the OET returns an <error>

    Examples:
  | file                               | error                                       |
  | file:///FileNotFound.py    | No such file or directory: /FileNotFound.py |
  | sdljfsdjkfhsd                      | Script URI type not handled: sdljfsdjkfhsd  |
