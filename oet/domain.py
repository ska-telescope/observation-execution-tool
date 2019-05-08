"""
The domain module contains code intended as a scientist-friendly front-end to
telescope control. It contains abstractions of telescope hardware and
concepts, allowing the telescope to be controlled using Python methods without
knowledge of the Tango control system.
"""
import collections

import operator


class Dish:
    """
    Represents an SKA MID dish.
    """

    def __init__(self, identifier: int):
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
    Represents a collection of resources that are, or can be, assigned to a sub-array.
    """

    def __init__(self, dishes=None):
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
        dishes_arg = [d for d in self.dishes]
        return '<ResourceAllocation(dishes={!r})>'.format(dishes_arg)


class DishAllocation(collections.MutableSet):
    """
    Represents a collection of SKA MID dishes that are, or can be, assigned to a sub-array.
    """

    def __init__(self, dishes=None):
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


class SubArray:
    """
    Represents a sub-array.
    """

    def __init__(self, identifier: int):
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
        """
        allocated = observingtasks.allocate_resources(self, resources)
        return allocated

    def deallocate(self, resources: ResourceAllocation = None) -> ResourceAllocation:
        """
        Deallocate resources from a sub-array.

        Accepts an optional ResourceAllocation argument specifying the
        resources to release. Omit this argument to release all sub-array
        resources.

        The resource allocation state of the sub-array object will be updated
        to match the state of the sub-array after resource deallocation.

        :param resources: the resources to release (optional)
        :return: the resources deallocated from the sub-array.
        """
        if resources is None:
            deallocated = observingtasks.deallocate_resources(self, release_all=True)
        else:
            deallocated = observingtasks.deallocate_resources(self, resources=resources)
        return deallocated


class SKAMid:
    """
    Represents SKA Mid.
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


# this import needs to be here, at the end of the file, to work around a
# circular import. This is just a temporary measure; if we introduce command
# registration and a command executor (to allow simulation at the observing
# task level) then this module will depend on the executor module, not on
# the observing tasks directly.
from . import observingtasks  # pylint: disable=wrong-import-position
