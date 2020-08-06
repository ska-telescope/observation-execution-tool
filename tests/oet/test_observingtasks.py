"""
Unit tests for the oet.observingtasks module
"""
# import datetime
import unittest.mock as mock

import os
import pytest
import ska.cdm.messages.central_node.assign_resources as cdm_assign
import ska.cdm.messages.central_node.release_resources as cdm_release
import ska.cdm.messages.subarray_node.configure as cdm_configure
from astropy.coordinates import SkyCoord
from ska.cdm.messages.subarray_node.configure import ConfigureRequest
from ska.cdm.schemas import CODEC
from ska.cdm import schemas

import oet.command as command
import oet.domain as domain
import oet.observingtasks as observingtasks
from oet.observingtasks import ObsState, ObsStateError
from oet.domain import Dish, DishAllocation, ResourceAllocation, SKAMid, SubArray

SKA_MID_CENTRAL_NODE_FDQN = 'ska_mid/tm_central/central_node'
SKA_SUB_ARRAY_NODE_1_FDQN = 'ska_mid/tm_subarray_node/1'

# Messages used for comparison in tests
CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE = '{"dish": {"receptorIDList_success": ["0001", "0002"]}}'
CN_ASSIGN_RESOURCES_MALFORMED_RESPONSE = '{"foo": "bar"}'
CN_ASSIGN_RESOURCES_PARTIAL_ALLOCATION_RESPONSE = '{"dish": {"receptorIDList_success": ["0001"]}}'
VALID_ASSIGN_STARTSCAN_REQUEST = '{"id": 123}'


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


@pytest.mark.xfail(reason='AssignResourcesRequest requires SDP configuration '
                          'argument, but SDP domain objects have not been created yet')
def test_allocate_resources_forms_correct_request():
    """
    Verify that domain objects are converted correctly to CDM objects for a
    CentralNode.AllocateResources() instruction.
    """
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)

    # This request is going to require an SDP configuration
    request = observingtasks.get_allocate_resources_request(subarray, resources)

    cdm_dish_allocation = cdm_assign.DishAllocation(['0001', '0002'])
    cdm_sdp_allocation = cdm_assign.SDPConfiguration(
        sdp_id='sdp_id', max_length=10.0, scan_types=[], processing_blocks=[]
    )
    expected = cdm_assign.AssignResourcesRequest(1, cdm_dish_allocation, cdm_sdp_allocation)

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


@pytest.mark.xfail(reason='CDM AssignResourcesRequest requires SDP configuration argument,'
                          ' but SDP domain objects have not been created yet')
def test_allocate_resources_command():
    """
    Verify that an 'allocate resources to sub-array' Command is targeted and
    structured correctly.
    """
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    # Once we have the SDP domain objects, we should create the required
    # SDP configuration programmatically, e.g.,
    # sdp_config = SDPConfiguration()
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

    cdm_dish_allocation = cdm_release.DishAllocation(receptor_ids=['0001', '0002'])
    expected = cdm_release.ReleaseResourcesRequest(1, dish_allocation=cdm_dish_allocation)

    assert expected == request


def test_release_resources_forms_correct_request_for_release_all():
    """
    Verify that the JSON argument for a CentralNode.ReleaseResources command
    that releases all sub-array resources is correctly formatted.
    :return:
    """
    subarray = SubArray(1)
    request = observingtasks.get_release_resources_request(subarray, release_all=True)
    expected = cdm_release.ReleaseResourcesRequest(1, release_all=True)
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


@pytest.mark.xfail(reason='CDM AssignResourcesRequest requires SDP configuration'
                          ' argument, but SDP domain objects have not been created yet')
@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_allocate_resources_successful_allocation(mock_read_fn, mock_execute_fn):
    """
    Verify that domain objects representing the successfully allocated
    resources are returned from an allocate resources instruction.
    """
    mock_read_fn.side_effect = [
        ObsState.RESOURCING, ObsState.RESOURCING, ObsState.IDLE
    ]
    mock_execute_fn.return_value = CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE

    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    allocated = subarray.allocate(resources)

    assert resources == allocated

    # command is sent to CentralNode; obsState is read on SubArrayNode
    assert mock_execute_fn.call_args[0][0].device == SKA_MID_CENTRAL_NODE_FDQN
    assert mock_read_fn.call_args[0][0].device == SKA_SUB_ARRAY_NODE_1_FDQN

    mock_execute_fn.assert_called_once()
    assert mock_read_fn.call_count == 3


@pytest.mark.xfail(reason='CDM AssignResourcesRequest requires SDP configuration '
                          'argument, but SDP domain objects have not been created yet')
@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_allocate_resources_partial_allocation(mock_read_fn, mock_execute_fn):
    """
    Verify that the response to an allocation request that was only part
    successful is processed correctly.
    """
    mock_read_fn.side_effect = [
        ObsState.RESOURCING, ObsState.RESOURCING, ObsState.IDLE
    ]
    mock_execute_fn.return_value = CN_ASSIGN_RESOURCES_PARTIAL_ALLOCATION_RESPONSE

    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    allocated = subarray.allocate(resources)

    assert resources != allocated
    assert Dish(2) not in allocated.dishes

    mock_execute_fn.assert_called_once()
    assert mock_read_fn.call_count == 3


@pytest.mark.xfail(reason='CDM AssignResourcesRequest requires SDP configuration argument,'
                          ' but SDP domain objects have not been created yet')
@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_subarray_state_is_updated_when_resources_are_allocated(mock_read_fn, mock_execute_fn):
    """
    Verify that the SubArray resource allocation state is updated after
    resources are allocated to the sub-array.
    """
    mock_read_fn.side_effect = [
        ObsState.RESOURCING, ObsState.IDLE
    ]
    mock_execute_fn.return_value = CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE

    resources = ResourceAllocation(dishes=[Dish(1)])
    dish_allocation = resources.dishes

    subarray = SubArray(1)
    # the new sub-array should not contain the dishes we are about to allocate
    assert not subarray.resources.dishes >= dish_allocation  # pylint: disable=unneeded-not

    # the sub-array state should reflect the successfully allocated dishes
    allocated = subarray.allocate(resources)
    assert subarray.resources.dishes >= allocated.dishes

    mock_execute_fn.assert_called_once()
    assert mock_read_fn.call_count == 2


@pytest.mark.xfail(reason='CDM AssignResourcesRequest requires SDP configuration '
                          'argument, but SDP domain objects have not been created yet')
@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_allocate_resources_raises_exception_when_error_state_encountered(
        mock_read_fn, mock_execute_fn):
    """
    Verify that the response to an allocation request that was only part
    successful is processed correctly.
    """
    mock_read_fn.side_effect = [
        ObsState.RESOURCING, ObsState.RESOURCING, ObsState.FAULT
    ]

    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray = SubArray(1)
    with pytest.raises(ObsStateError):
        _ = subarray.allocate(resources)

    mock_execute_fn.assert_called_once()
    assert mock_read_fn.call_count == 3


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


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_deallocate_resources_raises_exception_when_error_state_encountered(
        mock_execute_fn, mock_read_fn):
    """
    Verify that the boolean release_all argument is required.
    """
    mock_read_fn.side_effect = [
        ObsState.RESOURCING, ObsState.RESOURCING, ObsState.FAULT
    ]

    subarray = SubArray(1)
    with pytest.raises(ObsStateError):
        _ = observingtasks.deallocate_resources(subarray, release_all=True)

    mock_execute_fn.assert_called_once()

    # command is sent to CentralNode; obsState is read on SubArrayNode
    assert mock_execute_fn.call_args[0][0].device == SKA_MID_CENTRAL_NODE_FDQN
    assert mock_read_fn.call_args[0][0].device == SKA_SUB_ARRAY_NODE_1_FDQN

    assert mock_read_fn.call_count == 3


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_release_resources_successful_default_deallocation(mock_execute_fn, mock_read_fn):
    """
    Verify that the ResourceAllocation state of a SubArray object is emptied
    when all sub-array resources are released.
    """
    mock_read_fn.side_effect = [
        ObsState.IDLE, ObsState.EMPTY
    ]
    subarray = SubArray(1)
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray.resources = resources

    subarray.deallocate()

    assert not subarray.resources.dishes

    mock_execute_fn.assert_called_once()

    # command is sent to CentralNode; obsState is read on SubArrayNode
    assert mock_execute_fn.call_args[0][0].device == SKA_MID_CENTRAL_NODE_FDQN
    assert mock_read_fn.call_args[0][0].device == SKA_SUB_ARRAY_NODE_1_FDQN

    # IDLE -> EMPTY = 2 reads
    assert mock_read_fn.call_count == 2


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_release_resources_successful_specified_deallocation(mock_execute_fn, mock_read_fn):
    """
    Verify that the ResourceAllocation state of a SubArray object is updated
    when resources are released from a sub-array.
    """
    mock_read_fn.side_effect = [
        ObsState.IDLE, ObsState.EMPTY
    ]
    subarray = SubArray(1)
    resources = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    subarray.resources = resources

    subarray.deallocate(resources)

    assert not subarray.resources.dishes

    mock_execute_fn.assert_called_once()
    assert mock_read_fn.call_count == 2


def test_configure_subarray_forms_correct_request():
    """
    Verify that domain objects are converted correctly to CDM objects for a
    SubarrayNode.Configure() instruction.
    """
    scan_id = 12345
    coord = SkyCoord(ra=1, dec=1, frame='icrs', unit='rad')
    pointing_config = domain.PointingConfiguration(coord, 'name')
    dish_config = domain.DishConfiguration(receiver_band='5a')
    request = observingtasks.get_configure_subarray_request(scan_id,
                                                            pointing_config,
                                                            dish_config)

    pointing_config = cdm_configure.PointingConfiguration(
        cdm_configure.Target(1, 1, name='name', unit='rad'))
    dish_config = cdm_configure.DishConfiguration(receiver_band=cdm_configure.ReceiverBand.BAND_5A)
    expected = cdm_configure.ConfigureRequest(pointing=pointing_config, dish=dish_config)

    assert request == expected


def test_configure_subarray_forms_correct_command():
    """
    Verify that the configure_subarray task constructs the correct Command
    object.
    """
    subarray = SubArray(1)
    coord = SkyCoord(ra=1, dec=1, frame='icrs', unit='rad')
    config = domain.SubArrayConfiguration(coord, 'name', receiver_band=1)
    cmd = observingtasks.get_configure_subarray_command(subarray, config)

    assert cmd.device == SKA_SUB_ARRAY_NODE_1_FDQN
    assert cmd.command_name == 'Configure'
    assert len(cmd.args) == 1


@mock.patch.object(observingtasks.EXECUTOR, 'read')
def test_wait_for_obsstate_returns_target_state(mock_read_fn):
    """
    Verify wait_for_obsstate waits for the device obsState
    """
    mock_read_fn.side_effect = [
        ObsState.EMPTY, ObsState.RESOURCING, ObsState.IDLE, ObsState.IDLE
    ]

    attribute = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    target_state = ObsState.IDLE
    error_state = [ObsState.ABORTED, ObsState.FAULT]
    state_response = observingtasks.wait_for_obsstate(
        SKA_SUB_ARRAY_NODE_1_FDQN, target_state, error_state
    )

    mock_read_fn.assert_called_with(attribute)
    assert state_response.final_state == ObsState.IDLE
    assert mock_read_fn.call_count == 3


@mock.patch.object(observingtasks.EXECUTOR, 'read')
def test_wait_for_value_raises_type_error_for_non_matching_types(mock_read_fn):
    """
    Verify wait_for_value raises TypeError if attribute type and
    target type do not match
    """
    mock_read_fn.side_effect = [1, 2, 3, 4]

    attribute = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    target_states = [ObsState.ABORTED, ObsState.FAULT, ObsState.IDLE]

    with pytest.raises(TypeError):
        _ = observingtasks.wait_for_value(attribute, target_states)


@mock.patch.object(observingtasks.EXECUTOR, 'read')
def test_wait_for_obsstate_returns_error_state(mock_read_fn):
    """
    Verify wait_for_obsstate stops waiting for the device target obsState when
    error state is encountered
    """
    mock_read_fn.side_effect = [
        ObsState.IDLE, ObsState.CONFIGURING, ObsState.CONFIGURING, ObsState.FAULT,
        ObsState.RESTARTING
    ]

    attribute = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    target_state = ObsState.READY
    error_state = [ObsState.ABORTING, ObsState.FAULT]
    state_response = observingtasks.wait_for_obsstate(
        SKA_SUB_ARRAY_NODE_1_FDQN, target_state, error_state
    )

    mock_read_fn.assert_called_with(attribute)
    assert state_response.final_state == ObsState.FAULT
    assert mock_read_fn.call_count == 4


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_execute_configure_command_returns_when_obsstate_is_ready(mock_execute_fn, mock_read_fn):
    """
    Verify that execute_configure_command waits for the device obsState to
    transition back to READY before returning.
    """
    # obsState will be CONFIGURING for the first three reads, then READY
    mock_read_fn.side_effect = [
        ObsState.CONFIGURING, ObsState.CONFIGURING, ObsState.CONFIGURING, ObsState.READY
    ]

    cmd = command.Command(SKA_SUB_ARRAY_NODE_1_FDQN, 'Configure', 'configure JSON would go here')
    observingtasks.execute_configure_command(cmd)

    # Configure command gets big and complicated. I'm not going to verify the call argument here.
    mock_execute_fn.assert_called_with(mock.ANY)

    expected_attr = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    mock_read_fn.assert_called_with(expected_attr)

    # task should keep reading obsState until device is READY
    assert mock_read_fn.call_count == 4


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_execute_configure_command_raises_exception_when_error_state_encountered(
        mock_execute_fn, mock_read_fn):
    """
    Verify that execute_configure_command raises an Exception when ObsState
    transitions to an error state
    """
    mock_read_fn.side_effect = [
        ObsState.CONFIGURING, ObsState.CONFIGURING, ObsState.CONFIGURING, ObsState.ABORTING
    ]

    cmd = command.Command(SKA_SUB_ARRAY_NODE_1_FDQN, 'Configure', 'configure JSON would go here')
    with pytest.raises(ObsStateError):
        observingtasks.execute_configure_command(cmd)

    mock_execute_fn.assert_called_once()


@mock.patch.object(observingtasks, 'execute_configure_command')
def test_configure(mock_execute_fn):
    """
    Verify that configure executes a command and waits for the device obsState
    to transition back to READY before returning.
    """
    subarray = SubArray(1)
    coord = SkyCoord(ra=1, dec=1, frame='icrs', unit='rad')
    config = domain.SubArrayConfiguration(coord, 'name', receiver_band=1)
    observingtasks.configure(subarray, config)

    # The code that executes configure Commands has its own tests. We only
    # need to verify that the delegate function is called.
    mock_execute_fn.assert_called_with(mock.ANY)


@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_telescope_start_up_calls_tango_executor(mock_execute_fn):
    """
    Test that the 'start telescope devices' command calls the target Tango
    device once only.
    """
    telescope = SKAMid()
    observingtasks.telescope_start_up(telescope)
    cmd = observingtasks.get_telescope_start_up_command(telescope)
    mock_execute_fn.assert_called_once_with(cmd)


@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_telescope_stand_by_calls_tango_executor(mock_execute_fn):
    """
    Test that the 'telescope devices to standby' command calls the target
    Tango device once only.
    """
    telescope = SKAMid()
    observingtasks.telescope_standby(telescope)
    cmd = observingtasks.get_telescope_standby_command(telescope)
    mock_execute_fn.assert_called_once_with(cmd)


def test_scan_forms_correct_command():
    """
    Tests if get_scan_command generates correct Command
    """
    sub_array = SubArray(1)

    with mock.patch('oet.command.LocalScanIdGenerator.value', new_callable=mock.PropertyMock) \
            as mock_scan_id:
        mock_scan_id.return_value = 123
        generated = observingtasks.get_scan_command(sub_array)
    assert generated.device == SKA_SUB_ARRAY_NODE_1_FDQN
    assert generated.command_name == 'Scan'
    assert generated.args[0] == VALID_ASSIGN_STARTSCAN_REQUEST


def test_get_scan_request_populates_cdm_object_correctly():
    """
    Verify that a ScanRequest is populated correctly
    """
    with mock.patch('oet.command.LocalScanIdGenerator.value', new_callable=mock.PropertyMock) \
            as mock_value:
        mock_value.return_value = 123
        request = observingtasks.get_scan_request()
    assert request.scan_id == 123


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_subarray_scan_returns_when_obsstate_is_ready(mock_execute_fn, mock_read_fn):
    """
    Verify that the SubArray.configure command waits for the device obsstate
    to transition back to READY before returning.
    """
    # obsState will be SCANNING for the first three reads, then READY
    mock_read_fn.side_effect = [
        ObsState.SCANNING, ObsState.SCANNING, ObsState.SCANNING, ObsState.READY
    ]

    subarray = domain.SubArray(1)
    subarray.scan()

    mock_execute_fn.assert_called_with(mock.ANY)

    expected_attr = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    mock_read_fn.assert_called_with(expected_attr)

    # task should keep reading obsState until device is READY
    assert mock_read_fn.call_count == 4


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_subarray_scan_raises_exception_when_error_state_encountered(mock_execute_fn, mock_read_fn):
    """
    Verify that the SubArray.configure command waits for the device obsstate
    to transition back to READY before returning.
    """
    # obsState will be SCANNING for the first three reads, then READY
    mock_read_fn.side_effect = [
        ObsState.SCANNING, ObsState.SCANNING, ObsState.SCANNING, ObsState.FAULT
    ]

    subarray = domain.SubArray(1)
    with pytest.raises(ObsStateError):
        subarray.scan()

    expected_attr = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    mock_read_fn.assert_called_with(expected_attr)
    mock_execute_fn.assert_called_once()
    assert mock_read_fn.call_count == 4


def test_get_end_command():
    """
    Verify that a 'end SB' Command is targeted and structured correctly.
    """
    subarray = SubArray(1)
    cmd = observingtasks.get_end_command(subarray)
    assert cmd.device == SKA_SUB_ARRAY_NODE_1_FDQN
    assert cmd.command_name == 'End'
    assert not cmd.args
    assert not cmd.kwargs


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_end_calls_tango_executor(mock_execute_fn, mock_read_fn):
    """
    Test that the 'end SB' command calls the target Tango device once only.
    """
    # prime the obsState transitions, otherwise it will never end.
    mock_read_fn.side_effect = [
        ObsState.READY, ObsState.READY, ObsState.READY, ObsState.IDLE
    ]

    subarray = SubArray(1)
    observingtasks.end(subarray)
    cmd = observingtasks.get_end_command(subarray)
    mock_execute_fn.assert_called_once_with(cmd)


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_end_returns_when_obsstate_is_idle(mock_execute_fn, mock_read_fn):
    """
    Verify that the SubArray.end command waits for the device obsstate
    to transition back to IDLE before returning.
    """
    # obsState will be READY for the first three reads, then IDLE
    mock_read_fn.side_effect = [
        ObsState.READY, ObsState.READY, ObsState.READY, ObsState.IDLE
    ]

    subarray = domain.SubArray(1)
    observingtasks.end(subarray)

    # command arg validation is the subject of another test
    mock_execute_fn.assert_called_with(mock.ANY)

    expected_attr = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    mock_read_fn.assert_called_with(expected_attr)

    # task should keep reading obsState until device is READY
    assert mock_read_fn.call_count == 4


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_end_raises_exception_when_error_state_encountered(mock_execute_fn, mock_read_fn):
    """
    Verify that the SubArray.end raises an exception when obsState goes to error state
    """
    mock_read_fn.side_effect = [
        ObsState.READY, ObsState.READY, ObsState.READY, ObsState.FAULT
    ]

    subarray = domain.SubArray(1)
    with pytest.raises(ObsStateError):
        observingtasks.end(subarray)

    expected_attr = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    mock_read_fn.assert_called_with(expected_attr)
    mock_execute_fn.assert_called_once()

    # task should keep reading obsState until device goes to FAULT
    assert mock_read_fn.call_count == 4


@pytest.mark.skip('TBC: ProcessingBlock ID updates are no longer required')
@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_configure_from_file_updates_processing_block_id(mock_execute_fn, mock_read_fn):
    """
    configure_from_file with process_json=True should update both the scan ID
    and processing block ID. This tests that the PB ID is updated.
    """
    mock_read_fn.side_effect = [
        ObsState.CONFIGURING, ObsState.READY
    ]

    cwd, _ = os.path.split(__file__)
    test_path = os.path.join(cwd, 'testfile_sample_configure.json')

    original: ConfigureRequest = CODEC.load_from_file(ConfigureRequest, test_path)

    original_scan_id = original.scan_id
    original_pb_ids = {pb_config.sb_id for pb_config in original.sdp.configure}

    subarray = SubArray(1)
    observingtasks.configure_from_file(subarray, test_path, 14.0, with_processing=True)
    command = mock_execute_fn.call_args[0][0]
    processed: ConfigureRequest = CODEC.loads(ConfigureRequest, command.args[0])
    processed_scan_id = processed.scan_id
    processed_pb_ids = {pb_config.sb_id for pb_config in processed.sdp.configure}

    assert processed_scan_id != original_scan_id
    assert not processed_pb_ids.intersection(original_pb_ids)


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_get_allocate_resources_generates_correct_command(mock_execute_fn, mock_read_fn):
    """
    Test if the function allocate_from_file generate the expected command
    using or not the overwrite of the Resources
    """
    mock_read_fn.side_effect = [
        ObsState.EMPTY, ObsState.RESOURCING, ObsState.IDLE, ObsState.IDLE
    ]
    # to update with the last json expected
    mock_execute_fn.return_value = CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE
    cwd, _ = os.path.split(__file__)
    json_path = os.path.join(cwd, 'testfile_sample_assign.json')

    subarray = domain.SubArray(1)

    request: cdm_assign.AssignResourcesRequest = schemas.CODEC.load_from_file(
        cdm_assign.AssignResourcesRequest,
        json_path
    )

    resources = domain.ResourceAllocation(
        dishes=[domain.Dish(i) for i in request.dish.receptor_ids]
    )

    command_expected = observingtasks.get_allocate_resources_command(subarray, resources, request)

    subarray.allocate_from_file(json_path)
    command_returned = mock_execute_fn.call_args[0][0]

    assert command_returned == command_expected

    resources = domain.ResourceAllocation(
        dishes=[Dish('0002'), Dish('0003')]  # Resource different from the JSON
    )
    command_expected = observingtasks.get_allocate_resources_command(subarray, resources, request)

    assert command_returned != command_expected

    subarray.allocate_from_file(json_path, resources)
    command_returned = mock_execute_fn.call_args[0][0]

    assert command_returned == command_expected


@mock.patch.object(observingtasks, 'execute_configure_command')
def test_configure_from_cdm(mock_execute_fn):
    """
       Verify  configure_from_cdm  with test cdm configureRequest obj
    """
    # The test to populate CDM object from example JSON on disk,
    # execute the configure_from_cdm() function using that CDM object, then we
    # can test that the Command executed is contains the CDM JSON we expect.

    # Load the CDM configure request object from the test JSON file
    # on disk
    cwd, _ = os.path.split(__file__)
    test_path = os.path.join(cwd, 'testfile_sample_configure.json')

    request: cdm_configure.ConfigureRequest = schemas.CODEC.load_from_file(
        cdm_configure.ConfigureRequest,
        test_path)

    # Set the sub-array ID for this test session.
    subarray_id = 1

    # convert CDM configure request object into json string
    request_json = schemas.CODEC.dumps(request)

    # create the command
    command_expected = command.Command(SKA_SUB_ARRAY_NODE_1_FDQN, 'Configure', request_json)

    # ... then call the function under test
    observingtasks.configure_from_cdm(subarray_id, request)

    # ... get the Command that was sent for execution by configure_from_cdm
    command_returned = mock_execute_fn.call_args[0][0]

    # verify the Command is as expected. This assertion checks both
    # command type and JSON
    assert command_returned == command_expected


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_assign_resources_from_cdm(mock_execute_fn, mock_read_fn):
    """
    Verify that assign_resources_from_cdm requests resource allocation as
    expected.
    """
    #
    # If allocate_from_cdm works correctly, it should be formulating an
    # 'allocate resources' Command containing CDM JSON equal to the CDM object
    # passed as an argument. There are two things to test:
    #
    #    1. an 'allocate resources' command is sent, not 'configure', not
    #       'scan', etc.;
    #    2. the CDM JSON should not be modified in any way;
    #
    # The test strategy is to populate CDM object from example JSON on disk,
    # execute the allocate_from_cdm() function using that CDM object, then we
    # can test that the Command executed is an allocation request that
    # contains the CDM JSON we expect.
    #

    # Load the CDM resource assignment request object from the test JSON file
    # on disk
    mock_read_fn.side_effect = [
        ObsState.EMPTY, ObsState.RESOURCING, ObsState.IDLE, ObsState.IDLE
    ]

    cwd, _ = os.path.split(__file__)
    json_path = os.path.join(cwd, 'testfile_sample_assign.json')
    request: cdm_assign.AssignResourcesRequest = schemas.CODEC.load_from_file(
        cdm_assign.AssignResourcesRequest,
        json_path
    )

    # Set the sub-array ID for this test session.
    subarray_id = 1

    # Create the Command we expect to be issued by assign_resources_from_cdm
    # We use an empty Resources Allocation in order to create the allocation
    # exactly as defined in the JSON.
    subarray = domain.SubArray(subarray_id)
    resources = ResourceAllocation()
    command_expected = observingtasks.get_allocate_resources_command(subarray, resources, request)

    # Tell the mock executor to return a 'resources successfully assigned'
    # response when called...
    mock_execute_fn.return_value = CN_ASSIGN_RESOURCES_SUCCESS_RESPONSE

    # ... then call the function under test
    observingtasks.assign_resources_from_cdm(subarray_id, request)

    # ... get the Command that was sent for execution by assign_resources_from_cdm
    command_returned = mock_execute_fn.call_args[0][0]

    # ... and verify the Command is as expected. This assertion checks both
    # command type and JSON, validating 1. and 2.
    assert command_returned == command_expected

    # command is sent to CentralNode; obsState is read on SubArrayNode
    assert mock_execute_fn.call_args[0][0].device == SKA_MID_CENTRAL_NODE_FDQN
    assert mock_read_fn.call_args[0][0].device == SKA_SUB_ARRAY_NODE_1_FDQN


def test_get_obsreset_command():
    """
    Verify that a 'ObsReset' Command is targeted and structured correctly.
    """
    subarray = SubArray(1)
    cmd = observingtasks.get_obsreset_command(subarray)
    assert cmd.device == SKA_SUB_ARRAY_NODE_1_FDQN
    assert cmd.command_name == 'ObsReset'
    assert not cmd.args
    assert not cmd.kwargs


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_obsreset_calls_tango_executor(mock_execute_fn, mock_read_fn):
    """
    Test that the 'ObsReset' command calls the target Tango device once only.
    """
    # prime the obsState transitions, otherwise it will never end.
    mock_read_fn.side_effect = [
        ObsState.READY, ObsState.READY, ObsState.IDLE
    ]

    subarray = SubArray(1)
    observingtasks.obsreset(subarray)
    cmd = observingtasks.get_obsreset_command(subarray)
    mock_execute_fn.assert_called_once_with(cmd)


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_obsreset_returns_when_obsstate_is_idle(mock_execute_fn, mock_read_fn):
    """
    Verify that obsreset command waits for the device obsstate
    to transition back to IDLE before returning.
    """
    # obsState will be READY for the first three reads, then IDLE
    mock_read_fn.side_effect = [
        ObsState.RESETTING, ObsState.RESETTING, ObsState.IDLE, ObsState.RESETTING
    ]

    subarray = domain.SubArray(1)
    observingtasks.obsreset(subarray)

    # command arg validation is the subject of another test
    mock_execute_fn.assert_called_with(mock.ANY)

    expected_attr = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    mock_read_fn.assert_called_with(expected_attr)

    # task should keep reading obsState until device is IDLE
    assert mock_read_fn.call_count == 3


@mock.patch.object(observingtasks.EXECUTOR, 'read')
@mock.patch.object(observingtasks.EXECUTOR, 'execute')
def test_obsreset_raises_exception_when_error_state_encountered(mock_execute_fn, mock_read_fn):
    """
    Verify that the SubArray.end raises an exception when obsState goes to error state
    """
    mock_read_fn.side_effect = [
        ObsState.RESETTING, ObsState.RESETTING, ObsState.ABORTING, ObsState.ABORTED
    ]

    subarray = domain.SubArray(1)
    with pytest.raises(ObsStateError):
        observingtasks.end(subarray)

    expected_attr = command.Attribute(SKA_SUB_ARRAY_NODE_1_FDQN, 'obsState')
    mock_read_fn.assert_called_with(expected_attr)
    mock_execute_fn.assert_called_once()

    # task should keep reading obsState until device goes to ABORTING
    assert mock_read_fn.call_count == 3
