"""Example of using the cdm methods directly based on the AssignResourcesRequest request """

from astropy.coordinates import SkyCoord
import oet.domain as domain
import oet.observingtasks as tasks
import ska.cdm.messages.subarray_node as subarray_node

if __name__ == '__main__':
    sky_coord = SkyCoord(ra=1, dec=3, unit='deg')
    sky_coord.info.name = 'NGC123'

    pointing_config = subarray_node.PointingConfiguration(sky_coord)
    dish_config = subarray_node.DishConfiguration('5a')
    subarray_config = subarray_node.SubarrayConfiguration(pointing_config, dish_config)

    subarray = domain.SubArray(1)
    command = tasks.get_configure_subarray_command(subarray, subarray_config)
    print(command)
