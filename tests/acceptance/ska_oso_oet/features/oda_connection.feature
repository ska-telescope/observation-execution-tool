Scenario: Activity driven execution of the OET, with SB retrieval from the ODA
    Given an SBDefinition exists in the ODA with a filesystem success.py script in the test activity
    When the OET CLI is used to run the allocate activity on the SBDefinition
    Then the script should be in state COMPLETE after execution is finished