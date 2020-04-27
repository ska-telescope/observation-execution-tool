"""
The observingtasks module contains code that controls SKA Tango devices,
translating from the Tango-free 'science domain' objects to the Tango-required
control system domain.

This module is intended to be maintained by someone familiar with Tango and
the API of the devices they are controlling.
"""
import datetime
import logging
from typing import Optional

import marshmallow
import operator
import ska.cdm.messages.central_node.assign_resources as cdm_assign
import ska.cdm.messages.central_node.release_resources as cdm_release
import ska.cdm.messages.subarray_node.configure as cdm_configure
import ska.cdm.messages.subarray_node.scan as cdm_scan
import ska.cdm.schemas as schemas

from . import domain
from .command import Attribute, Command, SCAN_ID_GENERATOR, TangoExecutor

LOGGER = logging.getLogger(__name__)


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
        allocated_dishes = [domain.Dish(i) for i in unmarshalled.dish.receptor_ids]
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
        resources: domain.ResourceAllocation) -> cdm_assign.AssignResourcesRequest:
    """
    Return the JSON string that, when passed as argument to
    CentralNode.AssignResources, would allocate resources to a sub-array.

    :param subarray: the sub-array to allocate resources to
    :param resources: the resources to allocate
    :return: CDM request for CentralNode.AssignResources
    """
    receptor_ids = get_dish_resource_ids(resources.dishes)
    dish_allocation = cdm_assign.DishAllocation(receptor_ids=receptor_ids)
    request = cdm_assign.AssignResourcesRequest(subarray_id=subarray.id,
                                                dish_allocation=dish_allocation)
    return request


def get_allocate_resources_command(subarray: domain.SubArray,
                                   resources: domain.ResourceAllocation) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would allocate
    resources from a sub-array.

    :param subarray: the sub-array to control
    :param resources: the set of resources to allocate
    :return:
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(subarray)
    request = get_allocate_resources_request(subarray, resources)
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
    allocated = convert_assign_resources_response(response)
    subarray.resources += allocated
    return allocated


def allocate_resources_from_file(subarray: domain.SubArray, request_path) -> domain.ResourceAllocation:
    """
    Allocate resources to a sub-array using a JSON file.

    :param subarray: the sub-array to control
    :param request_path: JSON file path
    :return: the resources that were successfully allocated to the sub-array
    """

    request: cdm_assign.AssignResourcesRequest = schemas.CODEC.load_from_file((
        cdm_assign.AssignResourcesRequest,
        request_path
    ))

    #TODO add dish allocation

    command = get_allocate_resources_command(subarray, request)

    response = EXECUTOR.execute(command)
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


def wait_for_value(attribute: Attribute, target_value, key=lambda _: _):
    """
    Block until a Tango device attribute has reached a target value.

    If defined, the optional 'key' function will be used to process the device
    attribute value before comparison to the target value.

    :param attribute: attribute to query
    :param target_value: value to wait for
    :param key: function to process each attribute value before comparison
    :return:
    """
    LOGGER.info('Waiting for %s to transition to %s', attribute.name, target_value)
    while True:
        response = EXECUTOR.read(attribute)
        processed = key(response)
        if processed == target_value:
            break


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

    obsstate = Attribute(command.device, 'obsState')
    # obsState is a Python Enum, so compare desired state against enum.name
    name_getter = operator.attrgetter('name')

    #  wait for the sub-array obsState to transition from CONFIGURING to READY
    wait_for_value(obsstate, 'CONFIGURING', name_getter)
    wait_for_value(obsstate, 'READY', name_getter)


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


def configure_from_file(subarray: domain.SubArray, request_path, scan_duration: float,
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

    obsstate = Attribute(command.device, 'obsState')
    # obsState is a Python Enum, so compare desired state against enum.name
    name_getter = operator.attrgetter('name')

    #  wait for the sub-array obsState to transition from SCANNING to READY
    wait_for_value(obsstate, 'SCANNING', name_getter)
    wait_for_value(obsstate, 'READY', name_getter)


def end_sb(subarray: domain.SubArray):
    """
    Send the 'end SB' command to the SubArrayNode, marking the end of the
    current observation.
    :param subarray: the subarray to command
    """
    command = get_end_sb_command(subarray)
    _ = EXECUTOR.execute(command)

    obsstate = Attribute(command.device, 'obsState')
    # obsState is a Python Enum, so compare desired state against enum.name
    name_getter = operator.attrgetter('name')

    #  wait for the sub-array obsState to transition from READY to IDLE
    wait_for_value(obsstate, 'IDLE', name_getter)


def get_end_sb_command(subarray: domain.SubArray) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would call
    SubArrayNode.EndSB().

    :param subarray: the SubArray to control
    :return: the OET Command
    """
    subarray_node_fqdn = TANGO_REGISTRY.get_subarray_node(subarray)
    return Command(subarray_node_fqdn, 'EndSB')
