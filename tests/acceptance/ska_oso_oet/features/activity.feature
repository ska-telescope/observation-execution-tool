Feature: Tests of the Activity domain

    Scenario: Run an Activity, with SB retrieval from the ODA
        Given an SBDefinition sbd-mvp01-20200325-00011 exists in the ODA with script file:///tmp/tests/scripts/success_with_sb.py in the allocate activity
        When the OET CLI is used to run the allocate activity on the SBDefinition sbd-mvp01-20200325-00011
        Then the script should be in state COMPLETE after execution is finished
        And the activity should be in state TODO
        And an SBInstance exists in the ODA linked to sbd-mvp01-20200325-00011

    Scenario: Run an Activity with the prepare_only flag, SB retrieval from the ODA
        Given an SBDefinition sbd-mvp01-20200325-00012 exists in the ODA with script file:///tmp/tests/scripts/success_with_sb.py in the allocate activity
        When the OET CLI is used to run the allocate activity with the prepare_only flag on the SBDefinition sbd-mvp01-20200325-00012
        Then the script should be in state READY after execution is finished
        And the activity should be in state TODO
        And an SBInstance exists in the ODA linked to sbd-mvp01-20200325-00012

    Scenario: Run an Activity, with script args that cause an error
        Given an SBDefinition sbd-mvp01-20200325-00013 exists in the ODA with script file:///tmp/tests/scripts/success_with_sb.py in the allocate activity
        When the OET CLI is used to run the allocate activity with raise_msg=fail on the SBDefinition sbd-mvp01-20200325-00013
        Then the script should be in state FAILED after execution is finished
        And the activity should be in state TODO
        And an SBInstance exists in the ODA linked to sbd-mvp01-20200325-00013