# Configuration file for ipython.

import logging

import itango

config = get_config()
itango.load_config(config)

config.InteractiveShellApp.exec_lines = [
    'print("\\nWelcome to the SKA\\n")',
    'print("\\nImporting OET domain objects\\n")',
    'from astropy.coordinates import SkyCoord',
    'from oet.domain import *',
    'import oet.domain as oet_dom',
    'print("You can now use : ", [ob for ob in dir(oet_dom) if ob[0].isupper()])'
]

config.TerminalIPythonApp.display_banner = True

# Configure OET logging
oet_logger = logging.getLogger('oet')
oet_logger.setLevel(logging.INFO)

# create console handler and set level to debug
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# create formatter
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')

# add formatter to ch
console_handler.setFormatter(formatter)

# add ch to logger
oet_logger.addHandler(console_handler)
