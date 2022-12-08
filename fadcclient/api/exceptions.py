class FortinetApiException(Exception):
    pass

class AuthenticationFailed(FortinetApiException):
    pass

class UnknownApiException(FortinetApiException):
    pass


class DuplicateEntry(FortinetApiException):
    pass

class EntryDoesNotExist(FortinetApiException):
    pass

class EntryNotFound(FortinetApiException):
    pass


FORTIADC_ERROR_CODES_MAP = {
    '-1': EntryDoesNotExist,
    '-13': EntryDoesNotExist,
    '-15': DuplicateEntry
}