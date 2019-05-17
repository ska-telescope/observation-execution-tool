# Configuration file for ipython.

import itango
config = get_config()
itango.load_config(config)

#c.InteractiveShellApp.code_to_run = 'from oet.domain import *'

config.InteractiveShellApp.exec_lines = [
    'print("\\nWelcome to the SKA\\n")',
    'print("\\nImporting OET domain objects\\n")',
    "from oet.domain import *",
    "import oet.domain as oet_dom",    
    'print("You can now use : ", [ob for ob in dir(oet_dom) if ob[0].isupper()])'
]

config.TerminalIPythonApp.display_banner = True
config.InteractiveShellApp.log_level = 20

#config.PromptManager.in_template  = 'SKA Mid: In [\#]: '
#config.PromptManager.in2_template = '   .\D.: '
#config.PromptManager.out_template = 'SKA Mid: Out[\#]: '