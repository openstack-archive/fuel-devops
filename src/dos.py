import os

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "devops.settings")
    from devops.shell import Shell

    Shell().execute()
