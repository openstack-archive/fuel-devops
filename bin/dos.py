#!/usr/bin/env python
from os import environ

if __name__ == "__main__":
    environ.setdefault("DJANGO_SETTINGS_MODULE", "devops.settings")
    from devops.shell import Shell

    Shell().execute()
