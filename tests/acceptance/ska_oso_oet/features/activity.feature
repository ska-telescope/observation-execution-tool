Scenario: Activity driven execution of the OET, with SB retrieval from the ODA
    Given an SBDefinition sbi-mvp01-20200325-00001 exists in the ODA with a filesystem success.py script in the allocate activity
    When the OET CLI is used to run the allocate activity on the SBDefinition sbi-mvp01-20200325-00001
    Then the script should be in state COMPLETE after execution is finished
    And the activity should be in state REQUESTED