__all__ = [
    'CHECKS',
    'has_check',
    'get_check',
    'register_check',
    'unregister_check',
    'Check',
]
import os
from .exceptions import CheckError

# Dictionary holding all known actions
# This allows downstream users to register their own actions
CHECKS = {}


def has_check(key_or_klass):
    """
    Verify if a check is registered

    Parameters
    ----------
    key_or_klass : str or type
        A check name, or its class
    """
    if isinstance(key_or_klass, str):
        return key_or_klass in CHECKS
    else:
        for v in CHECKS.values():
            if v is key_or_klass:
                return True
        return False


def get_check(key):
    """
    Get a registered check from its key.

    Parameters
    ----------
    key : str, optional
        The name of an check
    """
    if key not in CHECKS:
        raise KeyError(f'No check with key "{key}".')
    return CHECKS[key]


def register_check(klass, key=None):
    """
    Register a check.

    Parameters
    ----------
    klass : type
        A class whose instances are callable
    key : str, optional
        The name that allows triggering this check in a schema
    """
    key = key or klass.__name__
    if key in CHECKS:
        raise KeyError('A check with this key is already registered. '
                       'Clear the existing check first.')
    CHECKS[key] = klass


def unregister_check(key_or_klass):
    """
    Unregister a check

    Parameters
    ----------
    key_or_klass : str or type
        A check name, or its class
    """
    if isinstance(key_or_klass, str):
        CHECKS.pop(key_or_klass)
    else:
        for k, v in CHECKS.items():
            if v is key_or_klass:
                CHECKS.pop(k)
                return


class Check:
    """Base class for checks"""
    Error = CheckError

    def __call__(self, value):
        return NotImplemented


class FileExists(Check):
    """Check that a file exists"""
    def __call__(self, value):
        if isinstance(value, (list, tuple)):
            return all(
                self(v) for v in value
            )
        if os.path.isfile(value):
            return True
        raise self.Error(f'File does not exist: {value}')


class DirExists(Check):
    """Check that a file exists"""
    def __call__(self, value):
        if isinstance(value, (list, tuple)):
            return all(
                self(v) for v in value
            )
        if os.path.isdir(value):
            return True
        raise self.Error(f'Directory does not exist: {value}')


class PathExists(Check):
    """Check that a file exists"""
    def __call__(self, value):
        if isinstance(value, (list, tuple)):
            return all(
                self(v) for v in value
            )
        if os.path.exists(value):
            return True
        raise self.Error(f'Path does not exist: {value}')


# register all builtin actions defined in this file
for key, klass in locals().items():
    if issubclass(klass, Check) and klass is not Check:
        register_check(klass, key)
