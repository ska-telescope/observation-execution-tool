"""
The observingtasks module contains code that controls SKA Tango devices,
translating from the Tango-free 'science domain' objects to the Tango-required
control system domain.

This module is intended to be maintained by someone familiar with Tango and
the API of the devices they are controlling.
"""
from typing import Optional

import marshmallow
import ska.cdm as cdm
import ska.cdm.messages.central_node as central_node

from .command import Command, TangoExecutor
from .domain import Dish, SubArray, ResourceAllocation, DishAllocation, SKAMid


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
            SKAMid: 'ska_mid/tm_central/central_node',
            SubArray: 'ska_mid/tm_central/central_node'
        }

    def get_central_node(self, domain_object):
        """
        Get the FQDN of the CentralNode appropriate to the object.
        """
        return self._fqdns[domain_object.__class__]


# Used as a singleton to look up Tango device FQDNs
TANGO_REGISTRY = TangoRegistry()

# Used a a singleton to execute Tango commands. The object is kept as a
# module attribute so that tests can mock the executor's 'execute()'
# function.
EXECUTOR = TangoExecutor()


def convert_assign_resources_response(response: str) -> ResourceAllocation:
    """
    Convert the Tango response from CentralNode.AssignResources() to an OET
    domain.ResourceAllocation containing the successfully allocated resources.

    :param response: the device response
    :return: the successfully allocated ResourceAllocation
    """
    try:
        unmarshalled = cdm.CODEC.loads(central_node.assign_resources.AssignResourcesResponse, response)
    except marshmallow.ValidationError:
        allocated_dishes = []
    else:
        allocated_dishes = [Dish(i) for i in unmarshalled.dish.receptor_ids]
    return ResourceAllocation(dishes=allocated_dishes)


def get_dish_resource_ids(allocation: DishAllocation) -> list:
    """
    Convert a DishAllocation to a list of string receptor IDs suitable for
    use in a CentralNode AssignResources or ReleaseResources command.

    :param allocation: dish allocation to convert
    :return: list that can be converted to JSON
    """
    return ['{:0>4}'.format(dish.id) for dish in allocation]


def get_telescope_start_up_command(telescope: SKAMid) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would call
    CentralNode.StartUpTelescope().

    :param telescope: the SKA telescope to control
    :return: the OET Command
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(telescope)
    return Command(central_node_fqdn, 'StartUpTelescope')


def get_telescope_standby_command(telescope: SKAMid) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would call
    CentralNode.StandByTelescope().

    :param telescope: the SKA telescope to control
    :return: the OET Command
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(telescope)
    return Command(central_node_fqdn, 'StandByTelescope')


def get_allocate_resources_arg(subarray: SubArray, resources: ResourceAllocation) -> str:
    """
    Return the JSON string that, when passed as argument to
    CentralNode.AssignResources, would allocate resources to a sub-array.

    :param subarray: the sub-array to allocate resources to
    :param resources: the resources to allocate
    :type: string argument for CentralNode.AssignResources
    """
    receptor_ids = get_dish_resource_ids(resources.dishes)
    dish_allocation = central_node.assign_resources.DishAllocation(receptor_ids=receptor_ids)
    request = central_node.assign_resources.AssignResourcesRequest(
        subarray_id=subarray.id,
        dish_allocation=dish_allocation
    )
    return cdm.CODEC.dumps(request)


def get_allocate_resources_command(subarray: SubArray, resources: ResourceAllocation) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would allocate
    resources from a sub-array.

    :param subarray: the sub-array to control
    :param resources: the set of resources to allocate
    :return:
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(subarray)
    arg = get_allocate_resources_arg(subarray, resources)
    return Command(central_node_fqdn, 'AssignResources', arg)


def get_release_resources_arg(subarray: SubArray, release_all: bool,
                              resources: Optional[ResourceAllocation] = None) -> str:
    """
    Return an argument for a CentralNode.ReleaseResources command.

    :param subarray: the sub-array to control
    :param release_all: True to release all resources, False to release just
        the resources specified in the resources argument
    :param resources: the set of resources to release. Only required if
        release_all is False
    :return: the
    """

    if release_all is True:
        request = central_node.release_resources.ReleaseResourcesRequest(
            subarray_id=subarray.id,
            release_all=True
        )
        return cdm.CODEC.dumps(request)

    # Not releasing all resources so must get args for specific resources to
    # release
    receptor_ids = get_dish_resource_ids(resources.dishes)
    dish_allocation = central_node.assign_resources.DishAllocation(receptor_ids=receptor_ids)

    request = central_node.release_resources.ReleaseResourcesRequest(
        subarray_id=subarray.id,
        dish_allocation=dish_allocation
    )

    return cdm.CODEC.dumps(request)


def get_release_resources_command(subarray: SubArray,
                                  release_all,
                                  resources: Optional[ResourceAllocation]) -> Command:
    """
    Return an OET Command that, when passed to a TangoExecutor, would release
    resources from a sub-array.

    :param subarray: the sub-array to control
    :param release_all: True to release all resources, False to release just
        the resources specified in the resources argument
    :param resources: the set of resources to release. Only required if
        release_all is False
    :return:
    """
    central_node_fqdn = TANGO_REGISTRY.get_central_node(subarray)
    arg = get_release_resources_arg(subarray, release_all=release_all, resources=resources)
    return Command(central_node_fqdn, 'ReleaseResources', arg)


def allocate_resources(subarray: SubArray, resources: ResourceAllocation) -> ResourceAllocation:
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


def deallocate_resources(subarray: SubArray,
                         release_all: bool = False,
                         resources: ResourceAllocation = None):
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
    released = ResourceAllocation(dishes=resources.dishes)
    subarray.resources -= released
    return released


def telescope_start_up(telescope: SKAMid):
    """
    Start up the telescope.

    This command powers up Dishes that are currently in standby.

    :param telescope: the telescope to control
    :return:
    """
    command = get_telescope_start_up_command(telescope)
    EXECUTOR.execute(command)


def telescope_standby(telescope: SKAMid):
    """
    Instruct telescope devices to switch to STANDBY mode.

    :param telescope: the telescope to control
    :return:
    """
    command = get_telescope_standby_command(telescope)
    EXECUTOR.execute(command)
