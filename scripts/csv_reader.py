"""
Example of reading JSON from a file to create message objects.
created for ticket AT2-182
"""

import csv
import time
from ska.cdm import CODEC

# TODO Replace this with ConfigureScan once it has been defined in the cdm

from ska.cdm.schemas import AssignResourcesRequest
from pprint import pprint

pprint('AT2-182 using CDM shared library to read a Request or Response Object from a file')

with open('SubArrayNodeConfig.csv', 'rt') as csvfile:
    contents = csv.reader(csvfile, delimiter=",")
    for row in contents:
        filepath = row[0]
        delay = float(row[1])

        assign_resources_request = CODEC.load_from_file(AssignResourcesRequest, filepath)
        tuplevalue = (vars(assign_resources_request), delay)
        pprint(tuplevalue)

