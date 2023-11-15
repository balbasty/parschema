__all__ = [
    'schema2cli',
    'command',
]
import os
import yaml
from functools import wraps
from .cli_help import schema2help
from .yaml_validate import populate


def command(schema=None):
    """A decorator that transforms a function a hybrid fuction/CLI

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


def schema2cli(schema):
    """
    Return a CLI parser from a YAML schema

    Parameters
    ----------
    schema : object
        A YAML schema (e.g., read with `yaml.load`)

    Returns
    -------
    parser : callable(list[str]) -> object
        A CLI parser that takes a list of arguments and returned
        a YAML object that follows the schema.
    """

    def parser(args):

        if '--help' in args or '-h' in args:
            help_level = 0
            if '--help' in args:
                help_index = args.index('--help')
            else:
                help_index = args.index('-h')
            if len(args) > help_index + 1:
                help_level = args[help_index+1]
                try:
                    help_level = int(help_level)
                except ValueError:
                    help_level = 0
            print(schema2help(schema).tostring(help_level))
            return

        try:
            obj = args2yaml(args, schema)
            obj = populate(obj, schema)
            return obj
        except Exception as e:
            print(schema2help(schema).tostring())
            raise e

    return parser


# --- implementation ---

def args2yaml(args, schema):
    """
    Convert commandline arguments into a YAML object that can be
    validated and populated
    """
    tagmap = schema2tagmap(schema)
    yaml = {}
    while args:
        tag = args.pop(0)
        mapper = tagmap[tag]
        values = []
        while args and args[0] not in tagmap:
            values.append(mapper.itemtype(args.pop(0)))
        if not mapper.is_array:
            assert len(values) <= 1
            values = values.pop(0) if values else True
        yaml_insert(yaml, mapper.path, values)
    return yaml


def yaml_insert(yaml, path, value):
    for path1 in path[:-1]:
        yaml.setdefault(path1, {})
        yaml = yaml[path1]
    yaml[path[-1]] = value


class ArgMapper:
    def __init__(self, path, itemtype, is_array=False):
        self.path = path
        self.itemtype = itemtype
        self.is_array = is_array


def schema2tagmap(schema):
    """
    Create a map from CLI tags to YAML hierarchy
    """

    def str2bool(x):
        if x.lower()[0] in 'ty':
            return True
        elif x.lower()[0] in 'fn':
            return False
        else:
            return bool(int(x))

    typemap = {
        '': str,
        'string': str,
        'number': float,
        'integer': int,
        'boolean': str2bool,
    }

    def parseprop(properties, tagmap,
                  yamlparent='', tagparent='', simpletag=False):

        for prop, content in properties.items():
            type = content.get('type', '')
            yamlcurrent = (yamlparent + ':' + prop) if yamlparent else prop

            simpletag = content.get('x-simpletag', simpletag)
            tag = prop if simpletag else (tagparent + prop)

            if type == 'object':
                parseprop(content.get('properties', {}),
                          tagmap, yamlcurrent, tag + '-', simpletag)
                continue

            aliases = content.get('x-alias', [])
            if not isinstance(aliases, list):
                aliases = [aliases]
            aliases += ['--' + tag]

            is_array = 'array' in type
            if 'enum' in content:
                itemtype = str
            elif 'array' in type:
                if 'enum' in content.get('items', {}):
                    itemtype = str
                else:
                    itemtype = content.get('items', {}).get('type', '')
            else:
                itemtype = type
            itemtype = typemap.get(itemtype, itemtype)

            mapper = ArgMapper(yamlcurrent.split(':'), itemtype, is_array)
            for tag in aliases:
                tagmap[tag] = mapper

    tagmap = {}
    simpletag = schema.get('x-simpletag', False)
    parseprop(schema['properties'], tagmap, simpletag=simpletag)
    return tagmap
