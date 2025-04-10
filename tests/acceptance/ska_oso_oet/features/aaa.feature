Feature: Tests of the AAA on the API

    Scenario Outline: The Role of a user is used to authenticate requests to the Procedure domain
        Given a Mid OET deployment
        When a <method> request is sent to <resource>
        And the request token is for a user with <role>
        Then the response should be <status>

      Examples:
        | method  | resource          | role                    | status |
        | GET     | /procedures       | SW_ENGINEER             | 200    |
        | GET     | /procedures       | MID_TELESCOPE_OPERATOR  | 200    |
        | GET     | /procedures       | LOW_TELESCOPE_OPERATOR  | 403    |
        | GET     | /procedures       | ANY                     | 403    |