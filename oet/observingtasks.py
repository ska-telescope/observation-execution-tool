"""
The observingtasks module contains code that controls SKA Tango devices,
translating from the Tango-free 'science domain' objects to the Tango-required
control system domain.

This module is intended to be maintained by someone familiar with Tango and
the API of the devices they are controlling.
"""
import enum
import logging
from datetime import timedelta
from typing import Optional, Any, NamedTuple, Iterable

import marshmallow
import ska.cdm.messages.central_node.assign_resources as cdm_assign
import ska.cdm.messages.central_node.release_resources as cdm_release
import ska.cdm.messages.subarray_node.configure as cdm_configure
import ska.cdm.messages.subarray_node.scan as cdm_scan
import ska.cdm.schemas as schemas

from . import domain
from .command import Attribute, Command, SCAN_ID_GENERATOR, TangoExecutor

LOGGER = logging.getLogger(__name__)

WAIT_FOR_STATE_SUCCESS_RESPONSE = 'SUCCESS'
WAIT_FOR_STATE_FAILURE_RESPONSE = 'FAILURE'


class ObsState(enum.Enum):
    """
    Represent the ObsState Tango enumeration
    """
    EMPTY = 0
    RESOURCING = 1
    IDLE = 2
    CONFIGURING = 3
    READY = 4
    SCANNING = 5
    ABORTING = 6
    ABORTED = 7
    RESETTING = 8
    FAULT = 9
    RESTARTING = 10

    def __str__(self):
        """
        Convert enum to string
        """
        # str(ObsState.IDLE) gives 'IDLE'
        return str(self.name)


class ObsStateResponse(NamedTuple):
    """
    Represent the status response from wait_for_obsstate() function
    """
    response_msg: str
    final_state: ObsState


class ObsStateError(Exception):
    """
    Represent the status response from wait_for_obsstate() function
    """
    def __init__(self, state, msg='Unexpected ObsState'):
        super().__init__(msg)
        self.msg = msg
        self.state = state

    def __str__(self):
        return f'{self.msg}: {self.state}'


class TangoRegistry:  # pylint: disable=too-few-public-methods
    """
    Registry used to look up Tango FQDNs.

    This is a simple class used to decouple TangoExecutor from Tango FQDNs.
    At some point, this class could change to do something more complicated,
    e.g., perform databaseds lookups, or perhaps the FQDNs might be specified
    on the domain classes, but for now a simple dict look-up is sufficient.
    """

    def __init__(self):
        self._fqdns = {
            domain.SKAMid: 'ska_mid/tm_central/central_node',
            domain.SubArray: 'ska_mid/tm_subarray_node'
        }

    def get_central_node(self, _):
        """
        Get the FQDN of the CentralNode appropriate to the object.
        """
        # TODO we need a way to distinguish between SKA MID and SKA LOW
        # sub-arrays. We might need a SubArray factory function in the global
        # namespace that sets a SubArray attribute or returns a specific
        # SubArray subclass depending on whether SKAMid or SKALow is set. Or
        # we could set SubArray as a class on the telescope, e.g.,
        # sa = SKAMid.Subarray(1).
        return self._fqdns[domain.SKAMid]

    def get_subarray_node(self, domain_object):
        """
        Get the FQDN of the Subarray appropriate to the object.
        """
        return '{}/{}'.format(self._fqdns[domain_object.__class__], domain_object.id)


# Used as a singleton to look up Tango device FQDNs
TANGO_REGISTRY = TangoRegistry()

# Used a a singleton to execute Tango commands. The object is kept as a
# module attribute so that tests can mock the executor's 'execute()'
# function.
EXECUTOR = TangoExecutor()


def convert_assign_resources_response(response: str) -> domain.ResourceAllocation:
    """
    Convert the Tango response from CentralNode.AssignResources() to an OET
    domain.ResourceAllocation containing the successfully allocated resources.

    :param response: the device response
    :return: the successfully allocated ResourceAllocation
    """
    response_cls = cdm_assign.AssignResourcesResponse
    try:
        unmarshalled = schemas.CODEC.loads(response_cls, response)
    except marshmallow.ValidationError:
        allocated_dishes = []
    else:
        try:
            allocated_dishes = [domain.Dish(i) for i in unmarshalled.dish.receptor_ids]
        except ValueError:
            LOGGER.warning('Dish ID(s) cannot be converted to integers (IDs: %s)',
                           unmarshalled.dish.receptor_ids)
            allocated_dishes = []
    return domain.ResourceAllocation(dishes=allocated_dishes)


def get_dish_resource_ids(allocation: domain.DishAllocation) -> list:
    """
    Convert a DishAllocation to a list of string receptor IDs suitable for
    use in a CentralNode AssignResources or ReleaseResources command.

    :param allocation: dish allocation to convert
    :return: list that can be converted to JSON
    """
    return ['{:0>4}'.format(dish.id) for dish in allocation]


def get_telescope_start_up_command(telescope: domain.SKAMid) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would call
    CentralNode.StartUpTelescope().

    :param telescope: the SKA telescope to control
    :return: the OET Command
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(telescope)
    return Command(central_node_fqdn, 'StartUpTelescope')


def get_telescope_standby_command(telescope: domain.SKAMid) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would call
    CentralNode.StandByTelescope().

    :param telescope: the SKA telescope to control
    :return: the OET Command
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(telescope)
    return Command(central_node_fqdn, 'StandByTelescope')


def get_allocate_resources_request(
        subarray: domain.SubArray,
        resources: domain.ResourceAllocation,
        template_request: Optional[cdm_assign.AssignResourcesRequest] = None
) -> cdm_assign.AssignResourcesRequest:
    """
    Return the JSON string that, when passed as argument to
    CentralNode.AssignResources, would allocate resources to a sub-array.

    This function can be given a template request. Values in the template
    request will be overwritten by values derived from the domain objects,
    where present.

    :param subarray: the sub-array to allocate resources to
    :param resources: the resources to allocate
    :param template_request: optional CDM template to use
    :return: CDM request for CentralNode.AssignResources
    """
    # get SDP config from template. We don't have a way to populate it from
    # the domain object yet.
    template_sdp_config = template_request.sdp_config

    # get dish allocation from template, overwriting with allocation specified
    # on the domain object if present
    if len(resources.dishes) > 0:
        receptor_ids = get_dish_resource_ids(resources.dishes)
        dish_allocation = cdm_assign.DishAllocation(receptor_ids=receptor_ids)
    else:
        dish_allocation = template_request.dish

    request = cdm_assign.AssignResourcesRequest(subarray_id=subarray.id,
                                                sdp_config=template_sdp_config,
                                                dish_allocation=dish_allocation)

    return request


def get_allocate_resources_command(
        subarray: domain.SubArray,
        resources: domain.ResourceAllocation,
        template_request: Optional[cdm_assign.AssignResourcesRequest] = None) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would allocate
    resources from a sub-array.

    :param subarray: the sub-array to control
    :param resources: the set of resources to allocate
    :param template_request: assign resources allocation template
    :return:
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(subarray)
    request = get_allocate_resources_request(subarray, resources, template_request)
    request_json = schemas.CODEC.dumps(request)
    return Command(central_node_fqdn, 'AssignResources', request_json)


def get_release_resources_request(
        subarray: domain.SubArray,
        release_all: bool,
        resources: Optional[domain.ResourceAllocation] = None
) -> cdm_release.ReleaseResourcesRequest:
    """
    Return an argument for a CentralNode.ReleaseResources command.

    :param subarray: the sub-array to control
    :param release_all: True to release all resources, False to release just
        the resources specified in the resources argument
    :param resources: the set of resources to release. Only required if
        release_all is False
    :return: a CDM request object for CentralNode.ReleaseResources
    """

    if release_all is True:
        return cdm_release.ReleaseResourcesRequest(subarray_id=subarray.id, release_all=True)

    # Not releasing all resources so must get args for specific resources to
    # release
    receptor_ids = get_dish_resource_ids(resources.dishes)
    dish_allocation = cdm_release.DishAllocation(receptor_ids=receptor_ids)

    return cdm_release.ReleaseResourcesRequest(subarray_id=subarray.id,
                                               dish_allocation=dish_allocation)


def get_release_resources_command(subarray: domain.SubArray,
                                  release_all,
                                  resources: Optional[domain.ResourceAllocation]) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would release
    resources from a sub-array.

    :param subarray: the sub-array to control
    :param release_all: True to release all resources, False to release just
        the resources specified in the resources argument
    :param resources: the set of resources to release. Only required if
        release_all is False
    :return: OET Command to release sub-array resources
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(subarray)
    request_obj = get_release_resources_request(subarray, release_all=release_all,
                                                resources=resources)
    request_json = schemas.CODEC.dumps(request_obj)
    return Command(central_node_fqdn, 'ReleaseResources', request_json)


def allocate_resources(subarray: domain.SubArray,
                       resources: domain.ResourceAllocation) -> domain.ResourceAllocation:
    """
    Allocate resources to a sub-array.

    :param subarray: the sub-array to control
    :param resources: the resources to allocate to the sub-array
    :return: the resources that were successfully allocated to the sub-array
    """
    command = get_allocate_resources_command(subarray, resources)
    # requires variable annotations in Python > 3.5
    # response: List[int] = EXECUTOR.execute(command)
    response = EXECUTOR.execute(command)
    # wait for state
    state_response = wait_for_obsstate(
        command.device, target_state=ObsState.IDLE, error_states=[ObsState.FAULT]
    )
    if state_response.response_msg == WAIT_FOR_STATE_FAILURE_RESPONSE:
        raise ObsStateError(state_response.final_state)
    allocated = convert_assign_resources_response(response)
    subarray.resources += allocated
    return allocated


def allocate_resources_from_file(
        subarray: domain.SubArray,
        template_json_path: str,
        resources: Optional[domain.ResourceAllocation] = None) \
        -> domain.ResourceAllocation:
    """
    Allocate resources to a sub-array using a JSON file as a template.

    Resources specified in the optional ResourceAllocation argument will
    override those in the template.

    :param subarray: the sub-array to control
    :param template_json_path: JSON file path
    :param resources: a optional parameter that permits to overwrite dish
        allocation defined in the JSON
    :return: the resources that were successfully allocated to the sub-array
    """
    if resources is None:
        resources = domain.ResourceAllocation()

    template_request: cdm_assign.AssignResourcesRequest = schemas.CODEC.load_from_file(
        cdm_assign.AssignResourcesRequest,
        template_json_path
    )

    command = get_allocate_resources_command(subarray, resources, template_request)
    response = EXECUTOR.execute(command)

    # Wait for obsState transition to signify success or failure. A resource
    # allocation command cannot be reset or aborted, hence we wait only for
    # FAULT.
    state_response = wait_for_obsstate(
        command.device, target_state=ObsState.IDLE, error_states=[ObsState.FAULT]
    )
    if state_response.response_msg == WAIT_FOR_STATE_FAILURE_RESPONSE:
        raise ObsStateError(state_response.final_state)
    allocated = convert_assign_resources_response(response)
    subarray.resources += allocated
    return allocated


def assign_resources_from_cdm(
        subarray_id: int,
        request: cdm_assign.AssignResourcesRequest) -> domain.ResourceAllocation:
    """
    Allocate resources to a sub-array using a CDM object.

    :param subarray_id: the id of the sub-array to allocate the resources
    :param request: the CDM AssignResourcesRequest object
    retun: the resources that were successfully allocated to the sub-array
    """
    subarray = domain.SubArray(subarray_id)
    resources = domain.ResourceAllocation()

    command = get_allocate_resources_command(subarray, resources, request)
    response = EXECUTOR.execute(command)

    # Wait for obsState transition to signify success or failure. A resource
    # allocation command cannot be reset or aborted, hence we wait only for
    # FAULT.
    state_response = wait_for_obsstate(
        command.device, target_state=ObsState.IDLE, error_states=[ObsState.FAULT]
    )
    if state_response.response_msg == WAIT_FOR_STATE_FAILURE_RESPONSE:
        # Allocation failed. Raise an exception and let the client decide how
        # to handle the failure (retry, abort, reset, etc.).
        raise ObsStateError(state_response.final_state)

    allocated = convert_assign_resources_response(response)
    subarray.resources += allocated
    return allocated


def deallocate_resources(subarray: domain.SubArray,
                         release_all: bool = False,
                         resources: domain.ResourceAllocation = None):
    """
    De-allocate sub-array resources.

    :param subarray: the sub-array to control
    :param release_all: True to release all sub-array resources, False to
        release just those resources specified in the resources argument
    :param resources: the set of sub-array resources to release. Only required
        if release_all is False
    :return: the resources that were released
    """
    if not isinstance(release_all, bool):
        raise ValueError('release_all must be a boolean')
    if release_all is False and resources is None:
        raise ValueError('Either release_all or resources must be defined')

    command = get_release_resources_command(subarray, release_all, resources)
    EXECUTOR.execute(command)

    # Wait for obsState transition to signify success or failure. A resource
    # release command cannot be reset or aborted, hence we wait only for FAULT
    state_response = wait_for_obsstate(
        command.device, target_state=ObsState.EMPTY, error_states=[ObsState.FAULT]
    )
    if state_response.response_msg == WAIT_FOR_STATE_FAILURE_RESPONSE:
        raise ObsStateError(state_response.final_state)

    if release_all:
        resources = subarray.resources
    released = domain.ResourceAllocation(dishes=resources.dishes)
    subarray.resources -= released
    return released


def get_configure_subarray_request(
        scan_id: int,
        pointing_config: domain.PointingConfiguration,
        dish_config: domain.DishConfiguration) -> cdm_configure.ConfigureRequest:
    """
    Return the JSON string that, when passed as an argument to
    SubarrayNode.Configure, would configure the sub-array.

    :param scan_id: integer scan ID
    :param pointing_config: desired sub-array pointing configuration
    :param dish_config: desired sub-array dish configuration
    :return: a CDM request object for SubArrayNode.Configure
    """
    coord = pointing_config.coord
    cdm_target = cdm_configure.Target(coord.ra.value,
                                      coord.dec.value,
                                      name=pointing_config.name,
                                      frame=coord.frame.name,
                                      unit=coord.ra.unit.name)
    cdm_pointing_config = cdm_configure.PointingConfiguration(cdm_target)

    cdm_receiver_band = cdm_configure.ReceiverBand(dish_config.receiver_band)
    cdm_dish_config = cdm_configure.DishConfiguration(receiver_band=cdm_receiver_band)

    return cdm_configure.ConfigureRequest(pointing=cdm_pointing_config, dish=cdm_dish_config)


def get_configure_subarray_command(subarray: domain.SubArray,
                                   subarray_config: domain.SubArrayConfiguration) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would configure a sub-array.

    :param subarray: the SubArray to configure
    :param subarray_config: the sub-array configuration to set
    :return: OET Command to configure the sub-array as requested
    """
    scan_id = SCAN_ID_GENERATOR.value
    subarray_node_fqdn = TANGO_REGISTRY.get_subarray_node(subarray)
    request = get_configure_subarray_request(scan_id,
                                             subarray_config.pointing_config,
                                             subarray_config.dish_config)
    request_json = schemas.CODEC.dumps(request)

    return Command(subarray_node_fqdn, 'Configure', request_json)


def wait_for_value(attribute: Attribute, target_values: Iterable[Any], key=lambda _: _) -> Any:
    """
    Block until a Tango device attribute has reached one of target values.

    If defined, the optional 'key' function will be used to process the device
    attribute value before comparison to the target value.

    :param attribute: device to query
    :param target_values: target ObsState to wait for
    :param key: function to process each attribute value before comparison
    :return: Attribute value read from device (one of target_values)
    """
    while True:
        response = EXECUTOR.read(attribute)
        processed = key(response)
        if processed in target_values:
            return processed


# TODO: 1. implement timeout functionality 2. return value to use Either pattern
def wait_for_obsstate(
        device: str,
        target_state: ObsState,
        error_states: Iterable[ObsState]) -> ObsStateResponse:
    #   timeout) -> Either[Left,Right]
    """
    Block until a Tango device attribute obsState has reached a target state or
    one of the error states.

    If defined, the optional 'key' function will be used to process the device
    attribute value before comparison to the target value.

    :param device: device to query
    :param target_state: target ObsState to wait for
    :param error_states: list of possible error ObsStates
    :param key: function to process each attribute value before comparison
    :return: ObsState of the device (either target state or error state)
    """
    attribute = Attribute(device, 'obsState')
    LOGGER.info('Waiting for %s to transition to %s', attribute.name, target_state)

    # wait_for_value should block until obsState transitions to any happy path
    # or sad path state. This list holds the union of obsStates.
    obstates_union = list(error_states)
    obstates_union.append(target_state)
    # obsState values do not need processing so the optional 'key' argument to
    # wait_for_value is left unset
    final_state = wait_for_value(attribute, obstates_union)

    if final_state != target_state:
        LOGGER.warning('%s state expected to go to %s but instead went to %s',
                       attribute.name, target_state, final_state)
        return ObsStateResponse(WAIT_FOR_STATE_FAILURE_RESPONSE, final_state)

    LOGGER.info('%s reached target state %s', attribute.name, target_state)
    return ObsStateResponse(WAIT_FOR_STATE_SUCCESS_RESPONSE, final_state)


def execute_configure_command(command: Command):
    """
    Execute a prepared 'configure' Command and wait for the device obsState to
    transition to READY.

    This function contains the functionality common to configuring a sub-array
    via the domain objects and via a CDM file. It assumes the command passed
    as an argument is fully prepared and ready for execution, leaving this
    function with responsibility to execute the command and wait for the
    obsState to transition through the state model.

    :param command: Command to execute
    :return:
    """
    # Python convention is to label unused variables as _
    _ = EXECUTOR.execute(command)

    # In the ADR-8 state model, sub-array configuration completes via one of
    # three paths:
    #
    #   1. Successful configuration: obsState transitions to READY
    #   2. Operation aborted (behind our back!): obsState transitions to
    #      ABORTING. We don't know how long the SubArrayNode will remain in
    #      the transient ABORTING state so we also wait for ABORTED.
    #   3. Operation failed: obsState transitions to FAULT.
    obsstate_response = wait_for_obsstate(
        command.device,
        target_state=ObsState.READY,
        error_states=[ObsState.FAULT, ObsState.ABORTING, ObsState.ABORTED]
    )
    if obsstate_response.response_msg == WAIT_FOR_STATE_FAILURE_RESPONSE:
        raise ObsStateError(obsstate_response.final_state)


def configure(subarray: domain.SubArray, subarray_config: domain.SubArrayConfiguration):
    """
    Configure a sub-array using the given domain SubArrayConfiguration.

    This function blocks until the sub-array is configured and has an obsState
    of READY.

    :param subarray: the sub-array to configure
    :param subarray_config: the sub-array configuration to set
    :return:
    """
    command = get_configure_subarray_command(subarray, subarray_config)
    # the functionality common to executing SubArrayNode.Configure from a CDM
    # file and from oet.domain configuration object is extracted to a shared
    # function.
    execute_configure_command(command)


def configure_from_file(subarray: domain.SubArray, request_path, scan_duration: timedelta,
                        with_processing):
    """
    Load a CDM ConfigureRequest from disk and use it to perform sub-array
    configuration.

    This function blocks until the sub-array is configured and has an obsState
    of READY.

    JSON processing is disabled when with_processing is set to False.

    :param subarray: the sub-array to configure
    :param request_path: path to CDM file
    :param scan_duration: duration of the scan
    :param with_processing: False if JSON should be passed through to
       to SubArrayNode directly without any validation or processing
    :return:
    """
    if with_processing:
        request: cdm_configure.ConfigureRequest = schemas.CODEC.load_from_file(
            cdm_configure.ConfigureRequest,
            request_path
        )

        # Update scan ID with current scan ID, leaving the rest of the configuration
        # unchanged
        # request = request.copy_with_scan_id(SCAN_ID_GENERATOR.value)

        request.tmc.scan_duration = scan_duration

        request_json = schemas.CODEC.dumps(request)

    else:
        LOGGER.warning('Loading JSON from {request_path}')
        # load from file. No processing
        with open(request_path, 'r') as json_file:
            request_json = ''.join(json_file.readlines())

    subarray_node_fqdn = TANGO_REGISTRY.get_subarray_node(subarray)
    command = Command(subarray_node_fqdn, 'Configure', request_json)

    execute_configure_command(command)


def configure_from_cdm(subarray_id: int, request: cdm_configure.ConfigureRequest):
    """
    Configure a sub-array using the supplied CDM configuration.

    This method does not make any changes to the configuration. It is the
    responsibility of the caller to ensure that all IDs, etc. are consistent.

    :param subarray_id: the ID of the sub-array to configure
    :param request: the CDM configuration to set
    :return:
    """
    subarray = domain.SubArray(subarray_id)
    request_json = schemas.CODEC.dumps(request)
    subarray_node_fqdn = TANGO_REGISTRY.get_subarray_node(subarray)
    command = Command(subarray_node_fqdn, 'Configure', request_json)
    execute_configure_command(command)


def telescope_start_up(telescope: domain.SKAMid):
    """
    Start up the telescope.

    This command powers up Dishes that are currently in standby.

    :param telescope: the telescope to control
    :return:
    """
    command = get_telescope_start_up_command(telescope)
    EXECUTOR.execute(command)


def telescope_standby(telescope: domain.SKAMid):
    """
    Instruct telescope devices to switch to STANDBY mode.

    :param telescope: the telescope to control
    :return:
    """
    command = get_telescope_standby_command(telescope)
    EXECUTOR.execute(command)


def get_scan_request() -> cdm_scan.ScanRequest:
    """
    Return a ScanRequest that would execute a scan, assigning the current scan
    ID from the scan ID generator.

    :return: ScanRequest CDM object
    """
    return cdm_scan.ScanRequest(scan_id=SCAN_ID_GENERATOR.value)


def get_scan_command(subarray: domain.SubArray) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would start a
    scan.

    :param subarray: the sub-array to control
    :return: OET command ready to start a scan
    """
    subarray_node_fqdn = TANGO_REGISTRY.get_subarray_node(subarray)
    request = get_scan_request()
    request_json = schemas.CODEC.dumps(request)
    return Command(subarray_node_fqdn, 'Scan', request_json)


def scan(subarray: domain.SubArray):
    """
    Execute a scan.

    :param subarray: the sub-array to control
    :return: the response from sending the command to configure sub-array
    """
    command = get_scan_command(subarray)

    # increment scan ID
    SCAN_ID_GENERATOR.next()

    _ = EXECUTOR.execute(command)

    # In the ADR-8 state model, scanning is signified by the SubArrayNode
    # obsState transitioning from READY to SCANNING, and then back to READY.
    # At the time of writing, the SubArrayNode.scan() call returns before the
    # obsState has transitioned to SCANNING, hence we need a two-phase process
    # that can distinguish between a start READY state and an end READY state.
    # Checking whether the device has transitioned through SCANNING is
    # sufficient to distinguish the two.
    #
    # ADR-8 also allows for two possible sad paths:
    #
    #   1. Operation aborted (behind our back!): obsState transitions to
    #      ABORTING. We don't know how long the SubArrayNode will remain in
    #      the transient ABORTING state so we also wait for ABORTED.
    #   2. Operation failed: obsState transitions to FAULT.

    state_response_1 = wait_for_obsstate(
        command.device,
        target_state=ObsState.SCANNING,
        error_states=[ObsState.FAULT, ObsState.ABORTING, ObsState.ABORTED]
    )
    if state_response_1.response_msg == WAIT_FOR_STATE_FAILURE_RESPONSE:
        raise ObsStateError(state_response_1.final_state)

    state_response_2 = wait_for_obsstate(
        command.device,
        target_state=ObsState.READY,
        error_states=[ObsState.FAULT, ObsState.ABORTING, ObsState.ABORTED]
    )
    if state_response_2.response_msg == WAIT_FOR_STATE_FAILURE_RESPONSE:
        raise ObsStateError(state_response_2.final_state)


def end_sb(subarray: domain.SubArray):
    """
    Send the 'end SB' command to the SubArrayNode, marking the end of the
    current observation.
    :param subarray: the subarray to command
    """
    command = get_end_sb_command(subarray)
    _ = EXECUTOR.execute(command)

    state_response = wait_for_obsstate(
        command.device,
        target_state=ObsState.IDLE,
        error_states=[ObsState.FAULT, ObsState.ABORTING, ObsState.ABORTED]
    )
    if state_response.response_msg == WAIT_FOR_STATE_FAILURE_RESPONSE:
        raise ObsStateError(state_response.final_state)


def get_end_sb_command(subarray: domain.SubArray) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would call
    SubArrayNode.EndSB().

    :param subarray: the SubArray to control
    :return: the OET Command
    """
    subarray_node_fqdn = TANGO_REGISTRY.get_subarray_node(subarray)
    return Command(subarray_node_fqdn, 'EndSB')
