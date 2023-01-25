Scenario: Run an Activity, with SB retrieval from the ODA
    Given an SBDefinition sbi-mvp01-20200325-00001 exists in the ODA with script file:///tmp/scripts/success_with_sb.py in the allocate activity
    When the OET CLI is used to run the allocate activity on the SBDefinition sbi-mvp01-20200325-00001
    Then the script should be in state COMPLETE after execution is finished
    And the activity should be in state TODO

Scenario: Run an Activity with the prepare_only flag, SB retrieval from the ODA
    Given an SBDefinition sbi-mvp01-20200325-00002 exists in the ODA with script file:///tmp/scripts/success_with_sb.py in the allocate activity
    When the OET CLI is used to run the allocate activity with the prepare_only flag on the SBDefinition sbi-mvp01-20200325-00002
    Then the script should be in state READY after execution is finished
    And the activity should be in state TODO