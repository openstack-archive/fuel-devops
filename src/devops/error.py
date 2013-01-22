class DevopsError(Exception):
    message = "Devops Error"

class DevopsCalledProcessError(DevopsError):
    def __init__(self, returncode, cmd, output=None):
        self.returncode = returncode
        self.cmd = cmd
        self.output = output
    def __str__(self):
        message = "Command '%s' returned non-zero exit status %d" % (self.cmd, self.returncode)
        if self.output:
            message+="\n%s" % '\n'.join(self.output)
        return message