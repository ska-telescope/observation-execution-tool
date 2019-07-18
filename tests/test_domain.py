"""
Unit tests for the oet.domain module.
"""
import unittest.mock as mock

import pytest

from oet.domain import Dish, DishAllocation, ResourceAllocation, SubArray, SKAMid


def test_dish_constructor_accepts_int():
    """
    Verify that Dish can be created with an integer dish ID.
    """
    dish = Dish(1)
    assert dish.id == 1


def test_dish_identifier_is_positive():
    """
    Verify that the dish ID must be positive.
    """
    with pytest.raises(ValueError):
        _ = Dish(-1)
    with pytest.raises(ValueError):
        _ = Dish(0)


def test_dish_constructor_accepts_integer_string():
    """
    Verify that a Dish can be constructed with an string numeric ID.
    """
    # type hints will flag this as an error, but it needs to be checked for the CLI
    dish = Dish('1')
    assert dish.id == 1


def test_dish_constructor_must_be_integer():
    """
    Verify that the dish constructor forbids non-numeric IDs.
    """
    with pytest.raises(ValueError):
        # type hints will flag this as an error, but it needs to be checked for the CLI
        _ = Dish('1a')


def test_dish_equals_dish():
    """
    Verify that dish instances with equal dish ID are considered equal.
    """
    assert Dish(1) == Dish(1)
    assert Dish(1) != Dish(2)
    assert Dish(1) != '1'


def test_dish_repr():
    """
    Verify that the Dish repr is formatted correctly.
    """
    dish = Dish(1)
    assert repr(dish) == '<Dish(1)>'


def test_add_dish_to_dish_allocation():
    """
    Verify that DishAllocation remembers which dishes are added to it.
    """
    dish_allocation = DishAllocation()
    dish1 = Dish(1)
    dish_allocation.add(dish1)
    dish2 = Dish(2)
    dish_allocation.add(dish2)
    assert dish1 in dish_allocation
    assert len(dish_allocation) == 2


def test_add_non_dish_to_dish_allocation():
    """
    Verify that DishAllocation only allows the addition of Dishes.
    """
    dish_allocation = DishAllocation()
    with pytest.raises(TypeError):
        dish_allocation.add(1)


def test_add_duplicate_dish_to_dish_allocation():
    """
    Verify that the addition of a Dish to a DishAllocation that already
    contains the Dish is a no-op.
    """
    dish_allocation = DishAllocation()
    dish_allocation.add(Dish(1))
    dish_allocation.add(Dish(1))
    assert len(dish_allocation) == 1


def test_remove_allocated_dish_from_dish_allocation():
    """
    Verify that DishAllocation updates its state when a Dish is removed.
    """
    dish_allocation = DishAllocation()
    dish_1 = Dish(1)
    dish_allocation.add(dish_1)
    assert len(dish_allocation) == 1
    dish_allocation.discard(dish_1)
    assert len(dish_allocation) == 0  # pylint: disable=len-as-condition


def test_remove_unallocated_dish_from_dish_allocation():
    """
    Verify that removing an unallocated Dish from a DishAllocation is a no-op.
    """
    dish_allocation = DishAllocation()
    dish_allocation.add(Dish(1))
    assert len(dish_allocation) == 1
    dish_allocation.discard(Dish(2))
    assert len(dish_allocation) == 1


def test_discard_wrong_type_from_dish_allocation():
    """
    Verify that only Dishes can be removed from a DishAllocation.
    """
    dish_allocation = DishAllocation()
    with pytest.raises(TypeError):
        dish_allocation.discard('1')


def test_infix_add_to_dish_allocation():
    """
    Verify that adding two DishAllocations gives a new DishAllocation
    containing the union of the dishes.
    """
    dish_1 = Dish(1)
    dish_allocation_1 = DishAllocation(dishes=[dish_1])
    dish_2 = Dish(2)
    dish_allocation_2 = DishAllocation(dishes=[dish_2])

    result = dish_allocation_1 + dish_allocation_2
    assert len(result.dishes) == 2
    assert dish_1 in result.dishes
    assert dish_2 in result.dishes


def test_inplace_add_to_dish_allocation():
    """
    Test that adding a DishAllocation in-place updates the state of the target
    DishAllocation correctly.
    """
    dish_allocation = DishAllocation()
    dish_1 = Dish(1)
    assert dish_1 not in dish_allocation
    dish_allocation += DishAllocation(dishes=[dish_1])
    assert dish_1 in dish_allocation


def test_inplace_add_to_dish_allocation_must_be_of_correct_type():
    """
    Test that DishAllocation only adds another DishAllocation in-place.
    """
    dish_allocation = DishAllocation()
    with pytest.raises(TypeError):
        dish_allocation += 'a'


def test_inplace_sub_from_dish_allocation():
    """
    Test that in-place substraction of one DishAllocation from another updates
    the state of the target DishAllocation correctly.
    """
    dish_allocation = DishAllocation(dishes=[Dish(1), Dish(2)])
    dish_1 = Dish(1)
    assert dish_1 in dish_allocation
    dish_allocation -= DishAllocation(dishes=[dish_1])
    assert dish_1 not in dish_allocation


def test_inplace_sub_from_dish_allocation_must_be_of_correct_type():
    """
    Verify that DishAllocation can only in-place remove another
    DishAllocation.
    """
    dish_allocation = DishAllocation()
    with pytest.raises(TypeError):
        dish_allocation -= 'a'


def test_dish_allocation_repr():
    """
    Verify that the DishAllocation repr is formatted correctly.
    :return:
    """
    dish_allocation = DishAllocation(dishes=[Dish(1), Dish(2)])
    assert repr(dish_allocation) == '<DishAllocation(dishes=[<Dish(1)>, <Dish(2)>])>'


def test_dish_allocation_issuperset():
    """
    Verify that DishAllocation A including all items in DishAllocation B is
    detected as a superset.
    """
    dish_allocation = DishAllocation(dishes=[Dish(1), Dish(2)])
    assert dish_allocation >= DishAllocation(dishes=[Dish(1)])
    assert not dish_allocation >= DishAllocation(dishes=[Dish(4)])  # pylint: disable=unneeded-not


def test_add_dishes_to_resource_allocation():
    """
    Test that ResourceAllocation.dishes is updated when a Dish is added to the
    ResourceAllocation.
    """
    resource_allocation = ResourceAllocation()
    dish_1 = Dish(1)
    dish_allocation = DishAllocation(dishes=[dish_1])
    resource_allocation.dishes += dish_allocation
    assert dish_1 in resource_allocation.dishes


def test_resource_allocation_default_constructor():
    """
    Verify that a default ResourceAllocation is created empty.
    """
    resource_allocation = ResourceAllocation()
    assert not resource_allocation.dishes


def test_resource_allocation_value_constructor():
    """
    Verify that a ResourceAllocation created using constructor arguments is
    populated correctly.
    """
    dish_1 = Dish(1)
    dish_2 = Dish(2)
    resource_allocation = ResourceAllocation(dishes=[dish_1, dish_2])
    assert dish_1 in resource_allocation.dishes
    assert dish_2 in resource_allocation.dishes
    assert len(resource_allocation.dishes) == 2


def test_inplace_add_to_resource_allocation():
    """
    Verify that in-place addition of one ResourceAllocation to another updates
    the target ResourceAllocation correctly.
    """
    target_ra = ResourceAllocation()
    dish_1 = Dish(1)
    other_ra = ResourceAllocation(dishes=[dish_1])
    target_ra += other_ra
    assert dish_1 in target_ra.dishes


def test_resource_allocation_inplace_add_must_be_of_correct_type():
    """
    Verify that ResourceAllocation in-place addition forbids the addition of
    non-ResourceAllocations.
    """
    resource_allocation = ResourceAllocation()
    with pytest.raises(TypeError):
        resource_allocation += 3


def test_inplace_sub_from_resource_allocation():
    """
    Verify that ResourceAllocation in-place subtraction updates the subject
    correctly.
    """
    target_ra = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    dish_1 = Dish(1)
    other_ra = ResourceAllocation(dishes=[Dish(1)])
    assert dish_1 in target_ra.dishes
    target_ra -= other_ra
    assert dish_1 not in target_ra.dishes


def test_resource_allocation_inplace_sub_must_be_of_correct_type():
    """
    Verify that ResourceAllocation in-place subtraction forbids the
    subtraction of non-ResourceAllocations.
    """
    resource_allocation = ResourceAllocation()
    with pytest.raises(TypeError):
        resource_allocation -= 3


def test_resource_allocation_eq():
    """
    Verify that two ResourceAllocations with the same allocated resources are
    considered equal.
    """
    resource_allocation = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    assert resource_allocation == ResourceAllocation(dishes=[Dish(1), Dish(2)])
    assert resource_allocation != ResourceAllocation(dishes=[Dish(1)])
    assert resource_allocation != ResourceAllocation(dishes=[Dish(1), Dish(3)])


def test_resource_allocation_eq_with_other_objects():
    """
    Verify that a ResourceAllocation is considered unequal to
    non-ResourceAllocation objects.
    """
    resource_allocation = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    assert resource_allocation != 1
    assert resource_allocation != object()


def test_resource_allocation_repr():
    """
    Verify that ResourceAllocation repr is formatted correctly.
    """
    resource_allocation = ResourceAllocation(dishes=[Dish(1), Dish(2)])
    assert repr(resource_allocation) == '<ResourceAllocation(dishes=[<Dish(1)>, <Dish(2)>])>'


def test_subarray_constructor_accepts_int():
    """
    Check that the SubArray constructor accepts integer IDs.
    """
    sub_array = SubArray(1)
    assert sub_array.id == 1


def test_subarray_identifier_is_positive():
    """
    Verify that the SubArray constructor requires IDs to be positive.
    """
    with pytest.raises(ValueError):
        _ = SubArray(-1)
    with pytest.raises(ValueError):
        _ = SubArray(0)


def test_subarray_constructor_accepts_integer_string():
    """
    Verify that the SubArray constructor accepts numeric strings as
    identifiers.
    """
    # type hints will flag this as an error, but it needs to be checked for the CLI
    sub_array = SubArray('1')
    assert sub_array.id == 1


def test_subarray_constructor_must_be_integer():
    """
    Confirm that the SubArray constructor forbids non-numeric constructor IDs.
    :return:
    """
    with pytest.raises(ValueError):
        # type hints will flag this as an error, but it needs to be checked for the CLI
        _ = SubArray('1a')


def test_subarray_repr():
    """
    Verify that the SubArray repr is formatted correctly.
    """
    sub_array = SubArray(1)
    assert repr(sub_array) == '<SubArray(1)>'


def test_skamid_repr():
    """
    Verify that the SKAMid repr is formatted correctly.
    """
    telescope = SKAMid()
    assert repr(telescope) == '<SKAMid>'


def test_telescope_start_up_calls_correct_observing_task():
    """
    Confirm that the 'start telescope devices' command calls the correct
    observing task exactly once.
    """
    telescope = SKAMid()
    with mock.patch('oet.domain.observingtasks') as mock_module:
        telescope.start_up()
    mock_module.telescope_start_up.assert_called_once_with(telescope)


def test_telescope_stand_by_calls_correct_observing_task():
    """
    Confirm that the 'telescope devices to standby' command calls the correct
    observing task exactly once.
    """
    telescope = SKAMid()
    with mock.patch('oet.domain.observingtasks') as mock_module:
        telescope.standby()
    mock_module.telescope_standby.assert_called_once_with(telescope)
