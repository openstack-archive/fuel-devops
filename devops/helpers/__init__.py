TEMPLATE_CMD_EXEC = u"Executing command: {!s}"
TEMPLATE_CMD_RESULT = u'{cmd!s}\nexecution results: Exit code: {code!s}'
TEMPLATE_CMD_UNEXPECTED_EXIT_CODE = (u"{append}Command '{cmd!s}' returned "
                                     u"exit code {code!s} while "
                                     u"expected {expected!s}\n")
TEMPLATE_CMD_UNEXPECTED_STDERR = (u"{append}Command '{cmd!s}' STDERR while "
                                  u"not expected\n"
                                  u"\texit code: {code!s}")
TEMPLATE_CMD_WAIT_ERROR = u'Wait for {0!s} during {1}s: no return code!'

