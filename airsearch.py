import os
import sys

if sys.version_info < (3, 7):
    sys.stdout.write("Sorry, requires Python 3.7 or higher\n")
    sys.exit(1)

from lib.controller import Controller
from lib.option import Option
from lib.output import Output

if __name__ == '__main__':
    script_path = os.path.dirname(os.path.realpath(__file__))
    option = Option(script_path)
    output = Output(option)

    output.show_banner()

    Controller(option, output)
