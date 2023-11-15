"""
This module implements click-like decorators.

Note that because I do allow variable number of arguments for _all_
flags, it is not possible to design a system as modular as click.
In particular, it is not possible to run multiple subcommands at once,
or to run the maincommand and the subcommand at the same time. To get
these features, we would need to place the same constraints as click
(i.e., the number of arguments of each flag must be set in stone).

We may revisit this decision, but we should do it soon, because a change
will not be fully backward-compatible.
"""
__all__ = ['command']
import os
import sys
import yaml
from .cli_parse import schema2cli, yaml_insert, str2bool, find_help
from .cli_help import schema2help, COMMAND
from .yaml_validate import populate


def command(schema=None):
    """A decorator that transforms a function into a hybrid fuction/CLI

    There is one strong requirement: the function should taks a single
    argument, which is expected to be a dictionary.

    By default, the decorator looks for a yaml file located next to
    current file
    ```
    |-- folder
      |-- my_script.py
      |-- my_script.segment.yaml
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

    Subcommands can be added to a command like this:

    ```python
    @command
    def main(params):
        pass

    @main.command
    def segment(params):
        ...

    @main.command
    def register(params):
        ...

    print(main(['-h']))
    print(main(['segment', '-h']))
    ```
    """

    # This is the decorator that we expose in the doc because it nicely
    # handles multiple semantics:
    #
    # @command
    # def mycommand: ...
    #
    # @command()
    # def mycommand: ...
    #
    # @command(schema)
    # def mycommand: ...

    if callable(schema):
        function = schema
        schema = find_schema(function)
        return command(schema)(function)

    def make_wrapper(function):
        return Command(function, schema)

    return make_wrapper


def find_schema(function):
    ffile = getattr(function, '__file__', '.')
    fpath, ffile = os.path.dirname(ffile), os.path.basename(ffile)
    ffile = os.path.splitext(ffile)[0]
    fname = function.__name__
    schema = os.path.join(fpath, f'{ffile}.{fname}.yaml')
    if not os.path.exists(schema):
        schema = os.path.join(fpath, f'{ffile}.{fname}.yml')
        schema = None
    return schema


def default_parser(args, cmd=[]):
    args = list(args)
    obj = dict()
    key = None
    values = []

    def save(k, v):
        if len(v) == 1:
            v = v[0]
        elif len(v) == 0:
            v = None
        yaml_insert(obj, k, v)

    while args:
        if args[0].startswith('--'):
            if key is not None:
                save(key, values)
            key = args.pop(0)[2:].split('-')
            values = []
            continue
        val = args.pop(0)
        for converters in (int, float, str2bool):
            try:
                val = converters(val)
                break
            except ValueError:
                pass
        values.append(val)

    if key is not None:
        save(key, values)

    return obj


class Command:

    def __init__(self, function, schema=None):
        if isinstance(schema, str):
            with open(schema) as f:
                schema = yaml.safe_load(f)
        self.schema = schema
        self.function = function
        self.subcommands = {}
        self.__doc__ = function.__doc__

    def __call__(self, params=None):
        cmd = []
        if params is None:
            params = list(sys.argv)
            cmd = [params.pop(0)]
        if not isinstance(params, dict):
            params = self.parse(params, cmd)
        elif self.schema:
            params = populate(params, self.schema)
        return self.function(params)

    def make_help(self):
        if self.schema:
            help = schema2help(self.schema)
        else:
            help = COMMAND()
        help.commands.set_title('subcommands').set_description('Subcommands')
        for key, subcommand in self.subcommands.items():
            help.commands.append(subcommand.make_help().set_key(key))
        return help

    def make_parser(self):
        return schema2cli(self.schema) if self.schema else default_parser

    def parse(self, args, cmd=[]):
        if args and args[0] in self.subcommands:
            key, *args = args
            cmd = cmd + [key]
            return self.subcommands[key].parse(args, cmd)

        cmd = ' '.join(cmd)
        which_help, help_level = find_help(args)
        if which_help:
            help = self.make_help()
            if which_help == 'usage':
                print(help.renderusage(help_level, cmd=cmd))
            elif which_help == 'help':
                print(help.renderhelp(help_level, cmd=cmd))
            return
        return self.make_parser()(args, cmd)

    def command(self, schema=None):
        """
        Decorator that transforms a function into a subcommand of this
        command.
        """
        if callable(schema):
            function = schema
            schema = find_schema(function)
            return self.command(schema)(function)

        def make_wrapper(function):
            subcommand = Command(function, schema)
            self.subcommands[function.__name__] = subcommand
            return subcommand

        return make_wrapper
