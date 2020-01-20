#!/usr/bin/env python3

import fire
import requests


class RestClient(object):
    """A simple CLI REST client using python-fire for the option parsing"""
    
    def __init__(self):
        self.URL = "http://localhost:5000/api/v1.0/procedures"
        self.script_uri = "file:///path/to/observing_script.py"
        self.script_args = {}
        self.script_args['init'] = { 'kwargs' : { 'subarray' : 1, 'sb_uri': 'file:///path/to/scheduling_block_123.json'} }
        self.script_args['run'] = { 'kwargs' : { 'scan_duration' : 14 } }
        
    
    def _list(self, number=None):
        url = self.URL
        if number is not None:
            url = f'{url}/{number}'
        return requests.get(url)
    
    
    def list(self, number=None):
        response = self._list(number)
        print (f'Response is {response.json()}')
        
        
    def createProcess(self, init_args=None, silent=False):
        url = self.URL
        create_obj = { 
            'script_uri' : self.script_uri,
            'script_args' : {
                'init' : self.script_args['init'],
                },
            }
        response = requests.post(url, json=create_obj)
        response_obj = response.json()
        self.latest_uri = response_obj['procedure']['uri']
        if not silent:
            print (f'Create process response is {response_obj}')
            print(f'Latest function is {self.latest_uri}')
    
    
    def startExecution(self, number=None, run_args=None, script_uri=None, silent=False):
        if script_uri is not None:
            url = script_uri
        elif number is None:
            print('No number given - will use latest')
            response = self._list(None)
            response_obj = response.json()
            proc_obj = response_obj['procedures'][-1]
            url = proc_obj['uri']
        else:
            url = f'{self.URL}/{number}'
        run_obj = {
            'script_args' : {
                'run' : self.script_args['run'],
                },
            }
        response = requests.put(url, json=run_obj)
        response_obj = response.json()
        print (f'Start process response is {response_obj}')
    
    def createAndExecute(self, init_args=None, run_args=None):
        self.createProcess(init_args=init_args, silent=True)
        self.startExecution(run_args=run_args, script_uri=self.latest_uri)
        

if __name__ == '__main__':
    fire.Fire(RestClient)


