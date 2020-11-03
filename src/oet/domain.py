"""
The domain module contains code intended as a scientist-friendly front-end to
telescope control. It contains abstractions of telescope hardware and
concepts, allowing the telescope to be controlled using Python methods without
knowledge of the Tango control system.
"""
import collections
from typing import Optional, List
from datetime import timedelta

import operator
from astropy.coordinates import SkyCoord

__all__ = ['Dish', 'DishAllocation', 'DishConfiguration', 'PointingConfiguration',
           'ResourceAllocation', 'SKAMid', 'SubArray', 'SubArrayConfiguration']


class Dish:
    """
    Dish represents an SKA MID antenna. Dish instances are used as arguments
    for resource allocation and resource deallocation commands.

    Dishes have a positive numeric identifier, accessible as Dish.id, which
    corresponds to the dish leaf node of the same ID registered in the Tango
    database. Dishes with the same numeric ID are considered equal and
    represent the same physical hardware.
    """

    def __init__(self, identifier: int):
        """
        Create a new Dish instance.

        The Dish identifier must be specified as a positive number.

        :param identifier: the numeric dish identifier
        """
        # As a user-facing class, handle both strings and ints
        try:
            identifier = int(identifier)
        except ValueError:
            raise ValueError('Dish identifier must be a positive integer')
        if identifier <= 0:
            raise ValueError('Dish identifier must be a positive integer')
        self.id = identifier  # pylint: disable=invalid-name

    def __repr__(self):
        return '<Dish({})>'.format(self.id)

    def __eq__(self, other):
        if not isinstance(other, Dish):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


class ResourceAllocation:
    """
    The ResourceAllocation class represents a collection of resources that
    are, or can be, assigned to a sub-array.

    Resources can be assigned to a sub-array or unassigned and still belong
    to a ResourceAllocation. Adding a resource to a ResourceAllocation makes
    no statement on the allocation status of the added resource, and does
    not change the allocation state of the resource being added. A
    ResourceAllocation could contain a mixture of assigned and unassigned
    resources; it is up to the code that operate on ResourceAllocations to
    decide whether the ResourceAllocation is valid and if not, how to handle
    the situation.

    ResourceAllocations are considered equal if they hold the same set of
    resources.

    A ResourceAllocation comprises:

    - a DishAllocation: the set of dishes in this allocation

    ResourceAllocations can be added to one another, e.g.,

        ra = ResourceAllocation(dishes=[Dish(1),Dish(2)])
        ra += ResourceAllocation(dishes=[Dish(2),Dish(3)])

    In the example above, after the inplace addition operation the
    ResourceAllocation will hold dishes 1-3.

    Similarly, ResourceAllocations can be subtracted from one another, e.g.,

        ra = ResourceAllocation(dishes=[Dish(1),Dish(2)])
        ra -= ResourceAllocation(dishes=[Dish(2)])

    After inplace subtraction the ResourceAllocation will refer to dish 2.
    """

    def __init__(self, dishes: Optional[List[Dish]] = None):
        """
        Create a new ResourceAllocation.

        :param dishes: (optional) list of dishes to reference
        :type dishes: [Dish, Dish, ...]
        """
        self.dishes = DishAllocation(dishes=dishes)

    def __iadd__(self, other):
        if not isinstance(other, ResourceAllocation):
            self_cls = type(self).__name__
            msg = 'right operand in += must be {!r}'
            raise TypeError(msg.format(self_cls))
        self.dishes += other.dishes
        return self

    def __isub__(self, other):
        if not isinstance(other, ResourceAllocation):
            self_cls = type(self).__name__
            msg = 'right operand in += must be {!r}'
            raise TypeError(msg.format(self_cls))
        self.dishes -= other.dishes
        return self

    def __eq__(self, other):
        if not isinstance(other, ResourceAllocation):
            return False
        return self.dishes == other.dishes

    def __repr__(self):
        dishes_arg = list(self.dishes)
        return '<ResourceAllocation(dishes={!r})>'.format(dishes_arg)


class DishAllocation(collections.abc.MutableSet):
    """
    DishAllocation represents a collection of SKA MID antennas.

    In more detail, DishAllocation holds a collection of Dishes, corresponding
    to the physical antennas referenced by the DishAllocation.

    The Dishes in a DishAllocation can be in an assigned or unassigned state.
    Adding a Dish to a DishAllocation makes no statement on the sub-array
    allocation status of the Dish, and does not change the allocation state.
    A DishAllocation can contain a mixture of allocated and unallocated
    dishes; it is up to the code that operates on DishAllocations to decide
    whether the DishAllocation is valid and if not, how to handle the
    situation.

    Dishes can be added and removed from a DishAllocation using the add() and
    remove() operations respectively, e.g.,

      da = DishAllocation()
      da.add(Dish(1))
      da.add(Dish(2))
      da.discard(Dish(2))

    DishAllocations can be added to another DishAllocation, e.g.,

      da = DishAllocation()
      da += DishAllocation(dishes=[Dish(1), Dish(2)])

    In the example above, the final dish allocation holds antennas #1 and #2.

    Similarly, DishAllocations can be subtracted from each other, e.g.,

      da = DishAllocation(dishes=[Dish(1), Dish(2)])
      da -= DishAllocation(dishes=[Dish(1)])

    The final state after the operation above is a DishAllocation holding
    only antenna #2.
    """

    def __init__(self, dishes: Optional[List[Dish]] = None):
        """
        Create a new DishAllocation containing the specified Dishes.

        :param dishes: (optional) the Dishes to add to this allocation
        :type: list of Dish objects
        """
        if dishes is None:
            dishes = []
        self.dishes = set()
        for dish in dishes:
            self.add(dish)

    def __contains__(self, dish: Dish):
        return dish in self.dishes

    def __len__(self):
        return len(self.dishes)

    def __iter__(self):
        return iter(self.dishes)

    def add(self, dish):
        """
        Add a Dish to this DishAllocation.

        Adding a Dish that already belongs to this allocation is a no-op.

        :param dish: the Dish to add
        :return:
        """
        if not isinstance(dish, Dish):
            msg = ('Can only add a Dish to a DishAllocation. '
                   'Got {}'.format(dish.__class__.__name__))
            raise TypeError(msg)
        self.dishes.add(dish)

    def discard(self, dish):
        """
        Remove a Dish from this DishAllocation.

        Removing a Dish that does not belong to this DishAllocation is a
        no-op.

        :param dish: the Dish to remove
        :return:
        """
        if not isinstance(dish, Dish):
            msg = ('Can only discard Dishes from a DishAllocation. '
                   'Got {}'.format(dish.__class__.__name__))
            raise TypeError(msg)
        self.dishes.discard(dish)

    def __add__(self, other):
        if not isinstance(other, DishAllocation):
            self_cls = type(self).__name__
            msg = 'right operand in + must be {!r}'
            raise TypeError(msg.format(self_cls))
        return DishAllocation(dishes=self.dishes.union(other.dishes))

    def __repr__(self):
        # sort dishes by ID for stable ordering
        dishes_list = sorted(self.dishes, key=operator.attrgetter('id'))
        dishes_repr = repr(dishes_list)
        return '<DishAllocation(dishes={})>'.format(dishes_repr)


class SKAMid:
    """
    SKAMid represents the SKA Mid telescope.
    Operations on an SKAMid object affect the whole telescope.
    """

    def __init__(self):
        pass

    def __repr__(self):
        return '<SKAMid>'

    def start_up(self):
        """
        Power up all telescope devices.
        """
        observingtasks.telescope_start_up(self)

    def standby(self):
        """
        Instruct telescope hardware to power down to standby mode.
        """
        observingtasks.telescope_standby(self)


class SubArrayConfiguration:  # pylint: disable=too-few-public-methods
    """
    SubarrayConfiguration encapsulates PointingConfiguration and DishConfiguration
    """

    def __init__(self, coord, name, receiver_band):
        """
        Create a new SubArrayConfiguration

        :param coord: pointing configuration for the sub
        :param name:
        :param receiver_band:
        """
        self.pointing_config = PointingConfiguration(coord, name)
        self.dish_config = DishConfiguration(receiver_band)


class PointingConfiguration:  # pylint: disable=too-few-public-methods
    """
    PointingConfiguration specifies where the subarray receptors are going to
    point.
    """

    def __init__(self, coord: SkyCoord, name: str = ''):
        """
        Create a new PointingConfiguration.

        :param coord: the sub-array pointing target
        :param name: the name of the pointing target
        """
        self.coord = coord
        self.name = name

    def __eq__(self, other):
        if not isinstance(other, PointingConfiguration):
            return False
        return self.coord.ra == other.coord.ra \
               and self.coord.dec == other.coord.dec \
               and self.coord.frame.name == other.coord.frame.name \
               and self.name == other.name


class DishConfiguration:  # pylint: disable=too-few-public-methods
    """
    DishConfiguration specifies how SKA MID dishes in a sub-array should be
    configured. At the moment, this is limited to setting the receiver band.
    """

    def __init__(self, receiver_band):
        rx_str = str(receiver_band).lower()
        if rx_str not in ['1', '2', '5a', '5b']:
            raise ValueError('Invalid receiver band: {}'.format(receiver_band))
        self.receiver_band = rx_str

    def __eq__(self, other):
        if not isinstance(other, DishConfiguration):
            return False
        return self.receiver_band == other.receiver_band


class SubArray:
    """
    SubArray represents an SKA telescope sub-array.

    SubArrays have a positive numeric identifier, accessible as SubArray.id,
    whicih corresponds to the SubArrayNode of the same ID. SubArray objects
    with the same numeric ID are considered equal.

    SubArrays are used to allocate and deallocate resources to and from a
    telescope sub-array.
    """

    def __init__(self, identifier: int):
        """
        Create a new SubArray object.

        :param identifier: the numeric sub-array ID
        """
        # As a user-facing class, handle both strings and ints
        try:
            identifier = int(identifier)
        except ValueError:
            raise ValueError('SubArray identifier must be a positive integer')
        if identifier < 1:
            raise ValueError('SubArray identifier must be a positive integer')
        self.id = identifier  # pylint: disable=invalid-name
        self.resources = ResourceAllocation()

    def __repr__(self):
        return '<SubArray({})>'.format(self.id)

    def allocate(self, resources: ResourceAllocation) -> ResourceAllocation:
        """
        Allocate resources to a sub-array.

        The resource allocation state of the sub-array object will be updated
        to match the state of the sub-array after resource allocation.

        :param resources: the resources to allocate
        :return: the successfully allocated resources.
        :rtype: ResourceAllocation
        """
        allocated = observingtasks.allocate_resources(self, resources)
        return allocated

    def allocate_from_file(self, cdm_file: str,
                           resources: Optional[ResourceAllocation] = None) -> ResourceAllocation:
        """
        Allocate resources to a sub-array using a JSON file.

        The resource allocation state of the sub-array object will be updated
        to match the state of the sub-array after resource allocation.

        :param cdm_file: JSON file
        :param resources: the resources to overwrite to the resources defined in the JSON file
        :return: the successfully allocated resources.
        :rtype: ResourceAllocation
        """
        allocated = observingtasks.allocate_resources_from_file(self, cdm_file, resources)
        return allocated

    def deallocate(self, resources: Optional[ResourceAllocation] = None) -> ResourceAllocation:
        """
        Deallocate resources from a sub-array.

        Accepts an optional ResourceAllocation argument specifying the
        resources to release. Omit this argument to release all sub-array
        resources.

        The resource allocation state of the sub-array object will be updated
        to match the state of the sub-array after resource deallocation.

        :param resources: the resources to release (optional)
        :return: the resources deallocated from the sub-array.
        :rtype: ResourceAllocation
        """
        if resources is None:
            deallocated = observingtasks.deallocate_resources(self, release_all=True)
        else:
            deallocated = observingtasks.deallocate_resources(self, resources=resources)
        return deallocated

    def configure(self, subarray_config: SubArrayConfiguration):
        """
        Configure subarray using the given sub-array configuration.

        :param subarray_config: the sub-array configuration to set
        """
        observingtasks.configure(self, subarray_config)

    def configure_from_file(self, cdm_file: str, scan_duration: float, with_processing=True):
        """
        Configure a sub-array using an exported Configuration Data Model
        located on disk.

        In normal operations the OET validates and processes the JSON
        before sending it downstream. JSON processing can be bypassed by
        setting the with_processing argument to False.


        :param cdm_file: path of the exported CDM
        :param scan_duration: duration of the scan in seconds
        :param with_processing: False if JSON should be passed through
           to SubArrayNode directly without any validation or processing
        :return:
        """
        scan_duration_timedelta = timedelta(seconds=scan_duration)
        observingtasks.configure_from_file(self, cdm_file, scan_duration_timedelta,
                                           with_processing=with_processing)

    def scan(self):
        """
        Start a scan.

        All scan configuration and scan duration should be configured before
        this command is called.
        """
        observingtasks.scan(self)

    def end(self):
        """
        End Scheduling Block, marking the end of the active observing
        sequence.
        """
        observingtasks.end(self)

    def abort(self):
        """
        Abort sub-array activity
        """
        observingtasks.abort(self)

    def reset(self):
        """
        Reset the SubArray from ABORTED or FAULT state to IDLE.
        """
        observingtasks.obsreset(self)

    def restart(self):
        """
        Reset the SubArray from ABORTED or FAULT state to EMPTY.
        """
        observingtasks.restart(self)


# this import needs to be here, at the end of the file, to work around a
# circular import. This is just a temporary measure; if we introduce command
# registration and a command executor (to allow simulation at the observing
# task level) then this module will depend on the executor module, not on
# the observing tasks directly.
from . import observingtasks  # pylint: disable=wrong-import-position