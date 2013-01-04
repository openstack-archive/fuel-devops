__author__ = 'vic'
#!/usr/bin/env python
import os, sys


def saved(args):
    c = getController()
    for saved_env in c.saved_environments:
        print(saved_env)


def resume(args):
    parser = argparse.ArgumentParser(prog='devops resume')
    parser.add_argument('environment')
    arguments = parser.parse_args(args)
    env = load(arguments.environment)
    import code

    code.InteractiveConsole(locals={'environment': env}).interact()

import sys
import argparse

parser = argparse.ArgumentParser(prog='devops')
parser.add_argument('command', choices=['saved', 'resume'])
parser.add_argument('command_args', nargs=argparse.REMAINDER)
arguments = parser.parse_args()

if arguments.command == 'saved':
    saved(arguments.command_args)
elif arguments.command == 'resume':
    resume(arguments.command_args)
else:
    help()
    sys.exit(1)


from src.devops.controller import Controller

class ControllerSingleton(Controller):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ControllerSingleton, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance


def getController():
    return ControllerSingleton(Libvirt())


def build(environment):
    getController().build_environment(environment)


def destroy(environment):
    getController().destroy_environment(environment)




if __name__ == "__main__":
    pass