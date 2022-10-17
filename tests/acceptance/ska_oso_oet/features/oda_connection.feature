Scenario: OET can connect with a deployment of the ODA
    Given the ODA REST API is running and is connected to an empty Postgres instance
    Then a request to get SBDefinition with sbd_id sbd-123 returns a valid Not Found response
