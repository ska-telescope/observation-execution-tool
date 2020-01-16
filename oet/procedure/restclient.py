import requests

create_payload = {
    "script_uri": "file:///path/to/observing_script.py",
    "script_args": {
        "init": {
            "kwargs": {
                "subarray": 1,
                "sb_uri": "file:///path/to/scheduling_block_123.json"
            }
        }
    }
}

start_payload = {
    "script_args": {
        "run": {
            "kwargs": {
                "scan_duration": 14
            }
        }
    },
    "state": "RUNNING"
}

# URL of REST service
url = 'http://localhost:5000/api/v1.0/procedures'

#
# Create procedure.
#
# This POSTs JSON to the /api/v1.0/procedures resource. The server returns
# a summary of the created Procedure, including - importantly - its URI.
# We'll need this for the subsequent 'start procedure' request.
response = requests.post(url, json=create_payload)
# get JSON response payload as dict
process_summary = response.json()
print(f'Create process response: {process_summary}')

# must access created process via its specific URI
procedure_uri = process_summary['procedure']['uri']
response = requests.put(procedure_uri, json=start_payload)
process_summary = response.json()
print(f'Run process response: {process_summary}')
