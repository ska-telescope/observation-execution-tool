"""Example of using the cdm methods directly based on the AssignResourcesRequest request """

from astropy.coordinates import SkyCoord
import oet.domain as domain
import oet.observingtasks as tasks

if __name__ == '__main__':
    sky_coord = SkyCoord(ra=1, dec=3, unit='deg')
    sky_coord.info.name = 'NGC123'

    pointing_config = domain.PointingConfiguration(sky_coord)
    dish_config = domain.DishConfiguration('5a')
    subarray_config = domain.SubarrayConfiguration(pointing_config, dish_config)

    subarray = domain.SubArray(1)
    command = tasks.get_configure_subarray_command(subarray, subarray_config)
    print(command)
