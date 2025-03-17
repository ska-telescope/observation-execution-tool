from unittest import mock


def test_fastapi_endpoint(fastapi_client):
    """
    Verify that Messages containing structured data are streamed correctly.
    """
    with mock.patch(
        "ska_oso_oet.fastapi.call_and_respond_fastapi"
    ) as mock_call_and_respond_fastapi:
        mock_call_and_respond_fastapi.return_value = "mock summary"
        response = fastapi_client.get("/ska-oso-oet/oet/fastapi")

    # assert isinstance(response, flask.Response)
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World!", "summary": "mock summary"}
