.. _script-examples:

******************
Scripting Examples
******************

-----------------
Telescope Startup
-----------------

A script to be run by the OET will be expected to have 2 methods; 
prepare() and run(). This example script is intended to be run 
from an interactive session and so has main().

.. code-block:: python

   import logging
   import os

   from oet.domain import SKAMid


   # set up the logger
   LOG = logging.getLogger(__name__)
   FORMAT = '%(asctime)-15s %(message)s'

   logging.basicConfig(level=logging.INFO, format=FORMAT)


    def main(*args, **kwargs):
       """
       Start up telescope.
       """
       LOG.info(f'Running telescope start-up script in OS process {os.getpid()}')
 
        if args:
            LOG.warning('Got unexpected positional args: %s', args)
        if kwargs:
            LOG.warning('Got unexpected named args: %s', kwargs)

        # select SKAMid         
        telescope = SKAMid()

        LOG.info(f'Starting telescope...')
        telescope.start_up()

        LOG.info('Telescope start-up script complete')


------------------
Allocate Resources
------------------

A script to be run by the OET will be expected to have 2 methods; 
prepare() and run(). This example script is intended to be run 
from an interactive session and so has main().

.. code-block:: python

   import logging
   import os

   from ska.cdm.messages.central_node.assign_resources import AssignResourcesRequest
   from ska.cdm.messages.central_node.assign_resources import SDPConfiguration
   from ska.cdm.schemas import CODEC as cdm_CODEC
   from skuid.client import SkuidClient

   from oet import observingtasks

   LOG = logging.getLogger(__name__)
   FORMAT = '%(asctime)-15s %(message)s'

   logging.basicConfig(level=logging.INFO, format=FORMAT)


   def main(allocate_json, subarray_id=1, update_uids=True):
       """
       Allocate resources to a target sub-array.

       :param allocate_json: name of configuration file
       :param subarray_id: numeric subarray ID
       :param update_uids: True if UIDs should be updated
       :return:
       """
       LOG.info(f'Running allocate script in OS process {os.getpid()}')
       LOG.info(f'Called with main(configuration={allocate_json}, subarray_id={subarray_id}, update_uids={update_uids}')

       request: AssignResourcesRequest = cdm_CODEC.load_from_file(AssignResourcesRequest, allocate_json)

       # In order to rerun the same SBI multiple times, we must update the IDs
       # otherwise SDP complains about duplicate SBI ids being resourced.
       # The following workaround is a temporary measure. In production a new SBI
       # with new self-consistent UIDs would be created by another application so
       # no UIDS would be modified in the script itself.
       if update_uids:
           update_all_uids(request.sdp_config)

       response = observingtasks.assign_resources_from_cdm(subarray_id, request)
       LOG.info(f'Resources Allocated: {response}')

       LOG.info('Allocation script complete')


   def update_all_uids(sdp_config: SDPConfiguration):
       """
       Replace UIDs with fresh UIDs retrieved from the UID generator.
   
       This function modifies the SDPConfiguration in-place.

       :param sdp_config: SDP configuration to process
       :return:
       """
       LOG.info(f'Updating UIDs')
       uid_client = SkuidClient(os.environ['SKUID_URL'])

       # Create a mapping of old SB IDs to new IDs
       new_sbi_mapping = {sdp_config.sdp_id: uid_client.fetch_skuid('sbi')}
       for old_id, new_id in new_sbi_mapping.items():
           LOG.info(f'New SBI ID mapping: {old_id} -> {new_id}')

       # Create a mapping of old processing block IDs to new IDs
       new_pb_mapping = {pb.pb_id: uid_client.fetch_skuid('pb')
                         for pb in sdp_config.processing_blocks}
       for old_id, new_id in new_pb_mapping.items():
           LOG.info(f'New PB ID mapping: {old_id} -> {new_id}')

       # Trawl through the SDP configuration replacing old IDs with new
       sdp_config.sdp_id = new_sbi_mapping[sdp_config.sdp_id]
       for pb in sdp_config.processing_blocks:
           pb.pb_id = new_pb_mapping[pb.pb_id]
           if pb.dependencies:
               for dependency in pb.dependencies:
                   dependency.pb_id = new_pb_mapping[dependency.pb_id]


--------------------------
Observe a Scheduling Block
--------------------------

A script to be run by the OET will be expected to have 2 methods; 
prepare() and run(). This example script is intended to be run 
from an interactive session and so has main().

.. code-block:: python
   
   import logging
   import os
   from datetime import timedelta

   from ska.cdm.messages.subarray_node.configure import ConfigureRequest
   from ska.cdm.messages.subarray_node.configure.csp import CSPConfiguration as cdm_CSPConfiguration
   from ska.cdm.messages.subarray_node.configure.csp import FSPConfiguration as cdm_FSPConfiguration
   from ska.cdm.messages.subarray_node.configure.csp import FSPFunctionMode as cdm_FSPFunctionMode
   from ska.cdm.messages.subarray_node.configure.core import ReceiverBand as cdm_ReceiverBand
   from ska.cdm.schemas import CODEC as cdm_CODEC
   from ska.pdm.entities.csp_configuration import CSPConfiguration as pdm_CSPConfiguration
   from ska.pdm.entities.csp_configuration import FSPConfiguration as pdm_FSPConfiguration
   from ska.pdm.entities.field_configuration import Target
   from ska.pdm.entities.sb_definition import SBDefinition
   from ska.pdm.schemas import CODEC as pdm_CODEC

   from oet import observingtasks
   from oet.command import SCAN_ID_GENERATOR
   from oet.domain import SubArray

   def main(sb_json, configure_json, subarray_id=1):
       """
       Observe using a Scheduling Block (SB) and template CDM file.

       :param sb_json: file containing SB in JSON format
       :param configure_json: configuration file in JSON format
       :param subarray_id: numeric subarray ID
       :return:
       """

       # Read SBDefinition and CDM configuration from file 
       sched_block: SBDefinition = pdm_CODEC.load_from_file(SBDefinition, sb_json)
       cdm_config: ConfigureRequest = cdm_CODEC.load_from_file(ConfigureRequest, configure_json)

       # Access the SubArray to be used 
       subarray = SubArray(subarray_id)

       LOG.info(f'Starting observing for scheduling block: {sched_block.id}')

       # Scan sequence is an ordered list of ScanDefinition identifiers. These
       # are string IDs, not the ScanDefinition instances themselves.
       # We need the ScanDefinition with matching ID. We could inspect each
       # ScanDefinition and return the one with matching ID, or we could do
       # as we do here, creating a look-up table and retrieving by key.
       # The advantage of this is that we can create the table outside of
       # the loop, therefore creating it once rather than once per iteration.
       scan_definitions = {scan_definition.id: scan_definition
                           for scan_definition in sched_block.scan_definitions}

       # Similarly we will need a look-up table for the FieldConfigurations as
       # the scan definitions contain only the FieldConfiguration IDs..
       field_configurations = {field_configuration.id: field_configuration
                               for field_configuration in sched_block.field_configurations}

       # ... same for dish configurations..
       dish_configurations = {dish_configuration.id: dish_configuration
                              for dish_configuration in sched_block.dish_configurations}

       # ... and for CSP configurations too.
       csp_configurations = {csp_configuration.csp_id: csp_configuration
                             for csp_configuration in sched_block.csp_configurations}

       for scan_definition_id in sched_block.scan_sequence:
           # Get the scan ID. This is only used for logging, not for any
           # business logic.
           scan_id = SCAN_ID_GENERATOR.value
           scan_definition = scan_definitions[scan_definition_id]
           LOG.info(f'Configuring for scan definition: {scan_definition.id}')

           # The Science Field Configuration is referenced by ID in the
           # scan definition
           field_configuration_id = scan_definition.field_configuration_id
           field_configuration = field_configurations[field_configuration_id]

           # Override the scan duration specified in the CDM with the scan
           # duration extracted from the SB. Note that the CDM library requires
           # scan durations to be timedelta instances, not floats.
           sb_scan_duration = scan_definition.scan_duration
           cdm_config.tmc.scan_duration = timedelta(seconds=sb_scan_duration)
           LOG.info(f'Setting scan duration: {sb_scan_duration} seconds')
        
           # Now override the pointing with that found in the SB target
           targets = field_configuration.targets

           # assume just using the first target for SKA MID. SKA LOW, with its
           # multiple beams, might be different.
           target: Target = targets[0]
           cdm_config.pointing.target.coord = target.coord
 
           # alternatively cdm_config.pointing.target.coord = targets[0].coord
           # Log the change
           LOG.info(f'Setting pointing information for {target.name} '
                    f'({target.coord.to_string(style="hmsdms")})')

           # PDM receiver band value. This should be specified in the dish
           # configuration for each scan.
           pdm_rx = None

           # The dish configuration is referenced by ID in the scan definition.
           # Get the dish configuration ID from the scan definition.
           if scan_definition.dish_configuration_id in dish_configurations:
               LOG.info(f'Setting dish configuration: {scan_definition.dish_configuration_id}')
               dish_configuration = dish_configurations[scan_definition.dish_configuration_id]

               # We must not set CDM values to PDM objects. Convert between the two.
               pdm_rx = dish_configuration.receiver_band
               # The CDM ReceiverBand value can now be set on the dishes
               LOG.info(f'Setting dish receiver band: {dish_configuration.receiver_band} ')
               cdm_config.dish.receiver_band = cdm_ReceiverBand(pdm_rx.value)

           # Override the CSP in the CDM with the one specified in the SB
           # scan definition.

           # This test checks both that the CSP ID is defined for the scan, and
           # that the CSP configuration was defined in the SB
           if scan_definition.csp_configuration_id in csp_configurations:
               LOG.info(f'Setting CSP configuration: {scan_definition.csp_configuration_id}')
               pdm_cspconfiguration = csp_configurations[scan_definition.csp_configuration_id]
               cdm_cspconfiguration = convert_cspconfiguration(pdm_cspconfiguration)
               cdm_config.csp = cdm_cspconfiguration

               # Complete the CSP configuration by setting the frequency band from
               # the dish configuration for this scan.
               cdm_config.csp.frequency_band = cdm_ReceiverBand(pdm_rx.value)

           # With the CDM modified, we can now issue the Configure instruction...
           LOG.info(f'Configuring subarray {subarray_id} for scan {scan_id}')
           observingtasks.configure_from_cdm(subarray_id, cdm_config)

           # .. and with configuration complete, we can begin the scan.
           LOG.info(f'Starting scan {scan_id}')
           subarray.scan()

       # All scans are complete. Observations are concluded with an 'end SB'
       # command.
       LOG.info(f'End scheduling block: {sched_block.id}')
       subarray.end()

       LOG.info('Observation script complete')


   def convert_cspconfiguration(pdm_config: pdm_CSPConfiguration) -> cdm_CSPConfiguration:
       """
       Convert a PDM CSPConfiguration to the equivalent CDM CSPConfiguration.
       """
       fsp_configs = [convert_fspconfiguration(o) for o in pdm_config.fsp_configs]

       return pdm_CSPConfiguration(
           csp_id=pdm_config.csp_id,
           fsp_configs=fsp_configs
       )


   def convert_fspconfiguration(pdm_config: pdm_FSPConfiguration) -> cdm_FSPConfiguration:
       """
       Convert a PDM FSPConfiguration to the equivalent CDM FSPConfiguration.
       """
       return cdm_FSPConfiguration(
           fsp_id=pdm_config.fsp_id,
           function_mode=cdm_FSPFunctionMode(pdm_config.function_mode.value),
           frequency_slice_id=pdm_config.frequency_slice_id,
           integration_time=pdm_config.integration_time,
           corr_bandwidth=pdm_config.corr_bandwidth,
           channel_averaging_map=pdm_config.channel_averaging_map,
           output_link_map=pdm_config.output_link_map,
           fsp_channel_offset=pdm_config.fsp_channel_offset,
           zoom_window_tuning=pdm_config.zoom_window_tuning
       )

--------------------
Deallocate Resources
--------------------

A script to be run by the OET will be expected to have 2 methods; 
prepare() and run(). This example script is intended to be run 
from an interactive session and so has main().

.. code-block:: python

   import logging
   import os

   from oet.domain import SubArray

   # get logger
   LOG = logging.getLogger(__name__)
   FORMAT = '%(asctime)-15s %(message)s'

   logging.basicConfig(level=logging.INFO, format=FORMAT)


   def main(subarray_id=1):
       """
       Deallocate sub-array resources.

       :param subarray_id: numeric subarray ID
       :return:
       """
       LOG.info(f'Running deallocate script in OS process {os.getpid()}')
       LOG.info(f'Called with main(subarray_id={subarray_id}')

       # get the subarray object
       subarray = SubArray(subarray_id)

       # and deallocate its resources
       LOG.info(f'Deallocating resources...')
       subarray.deallocate()

       LOG.info('Deallocation script complete')


------------------
Allocate Resources
------------------

A script to be run by the OET will be expected to have 2 methods; 
prepare() and run(). This example script is intended to be run 
from an interactive session and so has main().

.. code-block:: python

   import logging
   import os

   from oet.domain import SKAMid

   # get a logger
   LOG = logging.getLogger(__name__)
   FORMAT = '%(asctime)-15s %(message)s'

   logging.basicConfig(level=logging.INFO, format=FORMAT)


   def main(*args, **kwargs):
       """
       Telescope standby.
       """
       LOG.info(f'Running telescope standby script in OS process {os.getpid()}')

       if args:
           LOG.warning('Got unexpected positional args: %s', args)
       if kwargs:
           LOG.warning('Got unexpected named args: %s', kwargs)

       # get SKAMid and command it to standby
       LOG.info(f'Executing telescope standby...')
       telescope = SKAMid()
       telescope.standby()

       LOG.info('Telescope standby script complete')

