__all__ = [
    'ACTIONS',
    'has_action',
    'get_action',
    'register_action',
    'unregister_action',
    'Action',
]
import os
from parseman.exceptions import ActionError


# Dictionary holding all known actions
# This allows downstream users to register their own actions
ACTIONS = {}


def has_action(key_or_klass):
    """
    Checks if an action is registered

    Parameters
    ----------
    key_or_klass : str or type
        An action name, or its class
    """
    if isinstance(key_or_klass, str):
        return key_or_klass in ACTIONS
    else:
        for v in ACTIONS.values():
            if v is key_or_klass:
                return True
        return False


def get_action(key):
    """
    Get a registered action from its key.

    Parameters
    ----------
    key : str, optional
        The name of an action
    """
    if key not in ACTIONS:
        raise KeyError(f'No action with key "{key}".')
    return ACTIONS[key]


def register_action(klass, key=None):
    """
    Register an action.

    Parameters
    ----------
    klass : type
        A class whose instances are callable
    key : str, optional
        The name that allows triggering this action in a schema
    """
    key = key or klass.__name__
    if key in ACTIONS:
        raise KeyError('An action with this key is already registered. '
                       'Clear the existing action first.')
    ACTIONS[key] = klass


def unregister_action(key_or_klass):
    """
    Unregister an action

    Parameters
    ----------
    key_or_klass : str or type
        An action name, or its class
    """
    if isinstance(key_or_klass, str):
        ACTIONS.pop(key_or_klass)
    else:
        for k, v in ACTIONS.items():
            if v is key_or_klass:
                ACTIONS.pop(k)
                return


class Action:
    """Base class for actions"""
    Error = ActionError

    def __call__(self, value):
        return NotImplemented


class Convert(Action):
    """An action that converts a value to a different data type"""
    def __init__(self, dtype):
        super().__init__()
        self.dtype = dtype

    def __call__(self, value):
        if isinstance(value, (list, tuple)):
            return type(value)(
                self(v) for v in value
            )
        return self.dtype(value)


class SetValue(Action):
    """An action that assigns a value"""
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __call__(self, value):
        return self.value


class SetTrue(SetValue):
    """An action that assigns the value `True`"""
    def __init__(self):
        super().__init__(True)


class SetFalse(SetValue):
    """An action that assigns the value `False`"""
    def __init__(self):
        super().__init__(False)


class OpenFile(Action):
    """An action that opens a file"""
    def __init__(self, mode='r'):
        super().__init__()
        self.mode = mode

    def __call__(self, value):
        if isinstance(value, (list, tuple)):
            return type(value)(
                self(v) for v in value
            )
        try:
            with open(value, self.mode) as f:
                return f
        except Exception as e:
            raise self.Error(e)


class MakeDir(Action):
    """An action that makes a directory if it does not exist"""
    def __init__(self, mode=511, exist_ok=True):
        super().__init__()
        self.mode = mode
        self.exist_ok = exist_ok

    def __call__(self, value):
        if isinstance(value, (list, tuple)):
            return type(value)(
                self(v) for v in value
            )
        try:
            os.makedirs(value, mode=self.mode, exist_ok=self.exist_ok)
            return value
        except Exception as e:
            raise self.Error(e)


class MakeList(Action):
    def __init__(self):
        super().__init__()

    def __call__(self, value):
        if not isinstance(value, (list, tuple)):
            return [value]
        return list(value)


class MakeTuple(Action):
    def __init__(self):
        super().__init__()

    def __call__(self, value):
        if not isinstance(value, (list, tuple)):
            return (value,)
        return tuple(value)


class MakeDict(Action):
    def __init__(self, key=None):
        super().__init__()
        self.key = key

    def __call__(self, value):
        if not isinstance(value, dict):
            return {self.key: value}
        return value


# register all builtin actions defined in this file
for key, klass in locals().items():
    if issubclass(klass, Action) and klass is not Action:
        register_action(klass, key)
