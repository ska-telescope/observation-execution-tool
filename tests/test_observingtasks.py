"""
Unit tests for the oet.observingtasks module
"""
from unittest.mock import patch

import pytest
import ska.cdm.messages.central_node as central_node

from oet import observingtasks
from oet.domain import Dish, ResourceAllocation, SubArray, DishAllocation, SKAMid

SKA_MID_CENTRAL_NODE_FDQN = 'ska_mid/tm_central/central_node'

# Messages used for comparison in tests
CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE = '{"dish": {"receptorIDList_success": ["0001", "0002"]}}'
CN_ASSIGN_RESOURCES_MALFORMED_RESPONSE = '{"foo": "bar"}'
CN_ASSIGN_RESOURCES_PARTIAL_ALLOCATION_RESPONSE = '{"dish": {"receptorIDList_success": ["0001"]}}'


def test_tango_registry_returns_correct_url_for_ska_mid():
    """
    registry should return correct URL for SKAMid telescope
    """
    telescope = SKAMid()
    fqdn = observingtasks.TANGO_REGISTRY.get_central_node(telescope)
    assert fqdn == SKA_MID_CENTRAL_NODE_FDQN


def test_get_start_telescope_command():
    """
    Verify that a 'start up telescope' Command is targeted and structured
    correctly.
    """
    telescope = SKAMid()
    cmd = observingtasks.get_telescope_start_up_command(telescope)
    assert cmd.device == SKA_MID_CENTRAL_NODE_FDQN
    assert cmd.command_name == 'StartUpTelescope'
    assert not cmd.args
    assert not cmd.kwargs


def test_get_telescope_standby_command():
    """
    Verify that an 'instruct telescope devices to stand by' Command is
    targeted and structured correctly.
    """
    telescope = SKAMid()
    cmd = observingtasks.get_telescope_standby_command(telescope)
    assert cmd.device == SKA_MID_CENTRAL_NODE_FDQN
    assert cmd.command_name == 'StandByTelescope'
    assert not cmd.args
    assert not cmd.kwargs


def test_get_dish_resource_ids():
    """
    Test that numeric Dish IDs are converted to correctly formatted string IDs
    """
    dish_allocation = DishAllocation(dishes=[Dish(1), Dish(2)])
    expected = ["0001", "0002"]
    assert observingtasks.get_dish_resource_ids(dish_allocation) == expected


def test_allocate_resources_forms_correct_request():
    """
    Verify that domain objects are converted correctly to CDM objects for a
    CentralNode.AllocateResources() instruction.
    """
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    request = observingtasks.get_allocate_resources_request(subarray, resources)

    cdm_dish_allocation = central_node.DishAllocation(['0001', '0002'])
    expected = central_node.AssignResourcesRequest(1, cdm_dish_allocation)

    assert request == expected


def test_convert_assign_resources_response():
    """
    Test that that CentralNode.AssignResources response is parsed and
    converted to domain objects correctly.
    """
    expected = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    actual = observingtasks.convert_assign_resources_response(CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE)
    assert actual == expected


def test_convert_malformed_assign_resources_response():
    """
    Test that that a malformed CentralNode.AssignResources response is parsed
    and handled correctly.
    """
    expected = ResourceAllocation()
    actual = observingtasks.convert_assign_resources_response(
        CN_ASSIGN_RESOURCES_MALFORMED_RESPONSE)
    assert actual == expected


def test_allocate_resources_command():
    """
    Verify that an 'allocate resources to sub-array' Command is targeted and
    structured correctly.
    """
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    cmd = observingtasks.get_allocate_resources_command(subarray, resources)
    assert cmd.device == SKA_MID_CENTRAL_NODE_FDQN
    assert cmd.command_name == 'AssignResources'
    assert len(cmd.args) == 1
    assert not cmd.kwargs


def test_release_resources_forms_correct_request():
    """
    Verify that domain objects are converted correctly to CDM object for a
    CentralNode.ReleaseResources() instruction.
    """
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    request = observingtasks.get_release_resources_request(subarray, release_all=False,
                                                           resources=resources)

    cdm_dish_allocation = central_node.DishAllocation(receptor_ids=['0001', '0002'])
    expected = central_node.ReleaseResourcesRequest(1, dish_allocation=cdm_dish_allocation)

    assert expected == request


def test_release_resources_forms_correct_request_for_release_all():
    """
    Verify that the JSON argument for a CentralNode.ReleaseResources command
    that releases all sub-array resources is correctly formatted.
    :return:
    """
    subarray = SubArray(1)
    request = observingtasks.get_release_resources_request(subarray, release_all=True)
    expected = central_node.ReleaseResourcesRequest(1, release_all=True)
    assert request == expected


def test_release_resources_command():
    """
    Verify that a command to release sub-array resources is targeted and
    structured correctly.
    """
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    cmd = observingtasks.get_release_resources_command(
        subarray, release_all=False, resources=resources
    )
    assert cmd.device == SKA_MID_CENTRAL_NODE_FDQN
    assert cmd.command_name == 'ReleaseResources'
    assert len(cmd.args) == 1
    assert not cmd.kwargs


@patch.object(observingtasks.EXECUTOR, 'execute')
def test_allocate_resources_successful_allocation(mock_execute_fn):
    """
    Verify that domain objects representing the successfully allocated
    resources are returned from an allocate resources instruction.
    """
    mock_execute_fn.return_value = CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE

    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    allocated = subarray.allocate(resources)

    assert resources == allocated


@patch.object(observingtasks.EXECUTOR, 'execute')
def test_allocate_resources_partial_allocation(mock_execute_fn):
    """
    Verify that the response to an allocation request that was only part
    successful is processed correctly.
    """
    mock_execute_fn.return_value = CN_ASSIGN_RESOURCES_PARTIAL_ALLOCATION_RESPONSE

    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    allocated = subarray.allocate(resources)

    assert resources != allocated
    assert Dish(2) not in allocated.dishes


@patch.object(observingtasks.EXECUTOR, 'execute')
def test_subarray_state_is_updated_when_resources_are_allocated(mock_execute_fn):
    """
    Verify that the SubArray resource allocation state is updated after
    resources are allocated to the sub-array.
    """
    mock_execute_fn.return_value = CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE

    resources = ResourceAllocation(dishes=[Dish(1)])
    dish_allocation = resources.dishes

    subarray = SubArray(1)
    # the new sub-array should not contain the dishes we are about to allocate
    assert not subarray.resources.dishes >= dish_allocation  # pylint: disable=unneeded-not

    # the sub-array state should reflect the successfully allocated dishes
    allocated = subarray.allocate(resources)
    assert subarray.resources.dishes >= allocated.dishes


def test_deallocate_resources_must_define_resources_argument_if_not_releasing_all():
    """
    Verify that the resources argument is defined if the command is not a
    command to release all sub-array resources.
    """
    subarray = SubArray(1)
    with pytest.raises(ValueError):
        _ = observingtasks.deallocate_resources(subarray, release_all=False)


def test_deallocate_resources_enforces_boolean_release_all_argument():
    """
    Verify that the boolean release_all argument is required.
    """
    subarray = SubArray(1)
    with pytest.raises(ValueError):
        _ = observingtasks.deallocate_resources(subarray, release_all=1)

    resources = ResourceAllocation(dishes=[Dish(1)])
    with pytest.raises(ValueError):
        _ = observingtasks.deallocate_resources(subarray, release_all=1, resources=resources)


@patch.object(observingtasks.EXECUTOR, 'execute')
def test_release_resources_successful_default_deallocation(_):
    """
    Verify that the ResourceAllocation state of a SubArray object is emptied
    when all sub-array resources are released.
    """
    subarray = SubArray(1)
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray.resources = resources

    subarray.deallocate()
    assert not subarray.resources.dishes


@patch.object(observingtasks.EXECUTOR, 'execute')
def test_release_resources_successful_specified_deallocation(_):
    """
    Verify that the ResourceAllocation state of a SubArray object is updated
    when resources are released from a sub-array.
    """
    subarray = SubArray(1)
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray.resources = resources

    subarray.deallocate(resources)
    assert not subarray.resources.dishes

@patch.object(observingtasks.EXECUTOR, 'read')
@patch.object(observingtasks.EXECUTOR, 'execute')
def test_subarray_configure_successful_command(mock_execute_fn, mock_read_fn):
    """
    Verify that configuration command is changing obsState to CONFIGURING
    """
    configure_json = '{"pointing":{\
        "target":{\
        "RA": "1.0", \
        "dec": "2.0",\
        "system":"ICRS", \
        "name": "NGC6251" \
        }}, \
        "dish": { \
        "receiver_band": "1"}}'
    attribute_read = 'obsState'
    mock_execute_fn.return_value = 'Foo'
    mock_read_fn.return_value = 'CONFIGURING'
    subarray = SubArray(1)
    configure_rsp = subarray.configure(subarray,configure_json, attribute_read)

    assert configure_rsp == 'CONFIGURING'


@patch.object(observingtasks.EXECUTOR, 'execute')
def test_telescope_start_up_calls_tango_executor(mock_execute_fn):
    """
    Test that the 'start telescope devices' command calls the target Tango
    device once only.
    """
    telescope = SKAMid()
    observingtasks.telescope_start_up(telescope)
    command = observingtasks.get_telescope_start_up_command(telescope)
    mock_execute_fn.assert_called_once_with(command)


@patch.object(observingtasks.EXECUTOR, 'execute')
def test_telescope_stand_by_calls_tango_executor(mock_execute_fn):
    """
    Test that the 'telescope devices to standby' command calls the target
    Tango device once only.
    """
    telescope = SKAMid()
    observingtasks.telescope_standby(telescope)
    command = observingtasks.get_telescope_standby_command(telescope)
    mock_execute_fn.assert_called_once_with(command)
