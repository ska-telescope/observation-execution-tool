.. _observingtasks-guide:

.. todo::
   - The following are a subset of the functions in the observingtasks module, 
     those that look more intended for use by the public. The method 
     *get_end_command* does not look very public but is left in place of
     an *end* method which appears missing?

******************
oet.observingtasks
******************
.. automodule:: oet.observingtasks
    :members: ObsState, allocate_resources, allocate_resources_from_file,
              assign_resources_from_cdm, deallocate_resources, configure,
              configure_from_file, configure_from_cdm, telescope_start_up,
              telescope_standby, scan, get_end_command
