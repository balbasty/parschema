__all__ = ['command']
import os
import yaml
from functools import wraps
from .cli_parse import schema2cli


def command(schema=None):
    """A decorator that transforms a function into a hybrid fuction/CLI

    By default, the decorator looks for a yaml file located next to
    current file
    ```
    |-- folder
      |-- my_script.py
      |-- segment.yaml
    ```
    ```python
    @command
    def segment(params):
        # do something with `params`, which is a dictionary of parameters
        ....

    segment(['--do-something'])
    ```

    It is also possible to pass a schema explicitly:
    ```python
    @command('path/to/schema.yaml')
    def segment(params):
        # do something with `params`, which is a dictionary of parameters
        ....

    with open('path/to/schema.yaml') as f:
        schema = yaml.load(f)

    @command(schema)
    def register(params):
        # do something with `params`, which is a dictionary of parameters
        ...
    ```
    """
    if callable(schema):
        function = schema
        fpath = function.__file__
        fname = function.__name__
        schema = os.path.join(fpath, fname)
        if not os.path.exists(schema):
            raise ValueError(f'Could not find a schema for {function}')
        return command(schema)(function)

    if isinstance(schema, str):
        with open(schema) as f:
            schema = yaml.load(f)
    parser = schema2cli(schema)

    def decorator(function):

        @wraps(function)
        def wrapper(params):
            if not isinstance(params, dict):
                params = parser(params)
            return function(params)

        return wrapper

    return decorator
