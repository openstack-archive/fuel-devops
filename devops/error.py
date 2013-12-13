class DevopsError(Exception):
    message = "Devops Error"


class DevopsCalledProcessError(DevopsError):
    def __init__(self, command, returncode, output=None):
        self.returncode = returncode
        self.cmd = command
        self.output = output

    def __str__(self):
        message = "Command '%s' returned non-zero exit status %s" % (
            self.cmd, self.returncode)
        if self.output:
            message += "\n%s" % '\n'.join(self.output)
        return message


class DevopsEnvironmentError(DevopsError):
    def __init__(self, command):
        self.cmd = command

    def __str__(self):
        message = "Command '{0}' is not found".format(self.cmd)
        return message


class TimeoutError(DevopsError):
    pass


class AuthenticationError(DevopsError):
    pass
