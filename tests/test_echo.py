"""
Unit tests for echo module.
"""
from oet import echo


def test_echo():
    """
    Test that echo function returns input value.
    """
    echo_input = 'hello world!'
    echo_output = echo.echo(echo_input)
    assert echo_input == echo_output
