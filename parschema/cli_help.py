__all__ = [
    'schema2help',
]
import textwrap


def schema2help(schema):
    """
    Convert a schema to a CLI help string

    Parameters
    ----------
    schema : object
        A YAML schema (e.g., read with `yaml.load`)

    Returns
    -------
    cmd : COMMAND
        A command help, that can be converted to a string using
        `cmd.tostring([level], [maxwidth])`.
    """

    def prop2help(properties, parent='', simpletag=False, parent_level=0):
        rows = []
        for prop, content in properties.items():
            description = content.get('description', '')
            level = content.get('x-help', parent_level)
            simpletag = content.get('x-simpletag', simpletag)
            tag = prop if simpletag else (parent + prop)
            typ = content.get('type', '')
            default = content.get('default', _NO_DEFAULT)

            if typ == 'object':
                rows += [GROUP(prop2help(
                    content.get('properties', {}), tag + '-', simpletag, level
                )).set_title(prop)
                  .set_description(description)
                  .set_level(level)]
                continue

            aliases = content.get('x-alias', [])
            if not isinstance(aliases, list):
                aliases = [aliases]
            if 'enum' in content:
                itemtype = ENUM(content['enum'])
                minitems = maxitems = 1
            elif 'array' in typ:
                if 'enum' in content.get('items', {}):
                    itemtype = ENUM(content['enum'])
                else:
                    itemtype = content.get('items', {}).get('type', '')
                minitems = content.get('minItems', 0)
                maxitems = content.get('maxItems', None)
            else:
                itemtype = typ
                if typ == 'boolean' and default is False:
                    minitems = maxitems = 0
                else:
                    minitems = maxitems = 1
            if not isinstance(itemtype, TYPE):
                itemtype = SCALAR(itemtype)
            rows += [OPTION(
                tags=aliases + ['--' + tag],
                type=itemtype,
                description=description,
                level=content.get('x-help', level),
                default=default,
                minmax=(minitems, maxitems)
            )]
        return rows

    simpletag = schema.get('x-simpletag', False)
    level = schema.get('x-help', 0)
    options = GROUP(prop2help(schema['properties'], '', simpletag, level))

    return COMMAND(
        schema.get('title', ''),
        schema.get('description', ''),
        level=level,
    ).set_options(options)


# --- implementation ---

_NO_DEFAULT = object()
DEFAULT_WIDTH = 80


class COMMAND:
    """
    Help for commands (or subcommands)
    """

    def __init__(self, title, description='', has_version=False, level=0):
        """
        Parameters
        ----------
        title : str
            The command title (i.e., a short description)
            (note that this if different from the command name)
        description : str
            A longer description of what the command achieves.
        has_version : bool
            Whether the command accepts the tags "-V" and "--version"
        level : int
            The help level of this (sub)command.
        """
        self.title = title
        self.description = description
        self.options = GROUP()
        self.has_version = has_version
        self.level = level

    def set_title(self, value=''):
        self.title = value
        return self

    def set_description(self, value=''):
        self.description = value
        return self

    def set_has_version(self, value=True):
        self.has_version = value
        return self

    def set_level(self, level=0):
        self.level = level
        return self

    def set_options(self, value=[]):
        if not isinstance(value, GROUP):
            value = GROUP(value)
        self.options = value
        return self

    def add_options(self, value=[]):
        self.options.extend(value)
        return self

    def add_option(self, value):
        self.options.append(value)
        return self

    def make_help_option(self):
        desc = 'Display this help.'
        maxlevel = self.options.get_max_level()
        if maxlevel:
            if maxlevel > 3:
                values = f'Values in 1..{maxlevel} show'
            elif maxlevel == 3:
                values = 'Values in {1, 2, 3} show'
            elif maxlevel == 2:
                values = 'Values in {1, 2}'
            else:
                values = 'Value 1 shows'
            desc += f' {values} more advanced options.'
        return GROUP([OPTION(
            ['-h', '--help'],
            SCALAR('boolean' if maxlevel == 0 else 'integer'),
            description=desc,
        )]).set_title('help').set_description('Display help')

    def make_help_version(self):
        return GROUP([OPTION(
            ['-V', '--version'],
            SCALAR('boolean'),
            description='Display the software version',
        )]).set_title('version').set_description('Display version')

    def tostring(self, level=0, maxwidth=DEFAULT_WIDTH):
        s = self.title + '\n'
        if self.description:
            description = textwrap.fill('\t' + self.description, maxwidth)
            s += description + '\n'

        rows = [self.options, self.make_help_option()]
        if self.has_version:
            rows += [self.make_version_option()]

        with get_colformat(rows, level, maxwidth):
            for row in rows:
                s += row.tostring(level, maxwidth)
        return s


class GROUP(list):
    """
    Help for group of options
    """

    def __init__(self, *args, **kwargs):
        """
        Parameters
        ----------
        list[GROUP or OPTIONS]
        """
        super().__init__(*args, **kwargs)
        self.title = ''
        self.description = ''
        self.level = 0

    def set_title(self, value=''):
        self.title = value
        return self

    def set_description(self, value=''):
        self.description = value
        return self

    def set_level(self, level=0):
        self.level = level
        return self

    def get_max_level(self):
        """Compute the maximum help level across all (nested) options"""
        maxlevel = self.level
        for row in self:
            if isinstance(row, OPTION):
                maxlevel = max(maxlevel, row.level)
            elif isinstance(row, GROUP):
                maxlevel = max(maxlevel, row.get_max_level())
            else:
                assert False, f"{type(row)}"
        return maxlevel

    def tostring(self, level=0, maxwidth=DEFAULT_WIDTH):
        # NOTE: this function makes use of the `ColumnFormat` context
        #       to format the list of options
        s = ''
        if self.level <= level:
            s += '\n'
            if self.description:
                description = textwrap.fill(self.description, maxwidth)
                s += description + ':\n'
        rows = []
        for row in self:
            row = row.tostring(level, maxwidth)
            if not row:
                continue
            rows.append(row)

        options = list(filter(lambda x: isinstance(x, list), rows))
        if any(options):
            # We know that a child is an option because its `tostring`
            # method returns a list (with the content of each column)
            # instead of a string. In that case, we use the column
            # formatter to generate a nicely aligned string instead.
            rows = [catcol(row, ColumnFormat.WIDTH, ColumnFormat.SEP)
                    if isinstance(row, list) else row
                    for row in rows]

        s += '\n'.join(rows)
        return s


class OPTION:
    """
    An individual option (i.e., a flag and zero, one or multiple values)
    """

    def __init__(self, tags=None, type=None, description='', level=0,
                 default=_NO_DEFAULT, minmax=(0, 1)):
        """
        Parameters
        ----------
        tags : list[str]
            The option flags. For example: `['-h', '--help']`.
            By convention, aliases should be listed first.
        type : string or TYPE
            The value type
        description : str
            A description of the option
        level : int
            Its help level
        default : object
            The default value used when this flag is not set by the use.
            By default, no default value and the flag is mandatory.
        minmax : (int, int)
            The minimum and maximum number of values following the flag.
            use `None` when there is no maximum. For example `(1, None)`
            means that one or more value is expected.
        """
        if not tags:
            tags = []
        elif isinstance(tags, str):
            tags = [tags]
        self.tags = tags
        self.type = type or SCALAR('string')
        self.description = description
        self.level = level
        self.default = default
        self.minmax = minmax

    def set_tag(self, value):
        if isinstance(value, str):
            value = [value]
        self.tags = value
        return self

    def set_description(self, value=''):
        self.description = value
        return self

    def set_level(self, level=0):
        self.level = level
        return self

    def set_default(self, value=_NO_DEFAULT):
        self.default = value
        return self

    def minmax(self, value=(0, 1)):
        self.minmax = value
        return self

    def tostring(self, level=0, maxwidth=DEFAULT_WIDTH):
        # NOTE: contrary to the other class, this `tostring` returns
        # a list of value, so that the calling function can properly
        # format columns
        if level < self.level:
            return []
        if self.tags:
            tags = ', '.join(self.tags)
        else:
            tags = ''
        mn, mx = self.minmax
        type = self.type.tostring()
        if mn == 0:
            type = f'[{type}]'
        if mx is None or mx > 1:
            type += ' ...'
            if mx:
                type += f' (< {mx})'
        description = ' '.join(self.description.split())
        if self.default is not _NO_DEFAULT:
            description += f' (default: {self.default})'
        return [tags, type, description]


class TYPE:
    """Base class for value types"""
    pass


class ENUM(TYPE):
    """A defined list of possible values"""

    def __init__(self, values):
        self.values = values

    def tostring(self):
        return '{' + ', '.join(self.values) + '}'


class SCALAR(TYPE):
    """A scalar type (string, float, integer, boolean)"""

    type2repr = {
        'number': 'float',
        'integer': 'int',
        'string': 'str',
        'boolean': 'bool',
        '': 'any',
    }

    def __init__(self, types='string'):
        """
        Parameters
        ----------
        types : str or list[str]
            Acceptable value types.
        """
        self.types = types

    def tostring(self):
        if isinstance(self.types, (list, tuple)):
            return '|'.join(
                map(lambda x: self.type2repr.get(x, x), self.types)
            )
        else:
            return self.type2repr.get(self.types, self.types)


# --- implementation details ---


class ColumnFormat:
    """
    A context manager that specifies how to format columns in a help

    ```
    with ColumnFormat(width, sep):
        # do something that uses ColumnFormat.WIDTH and ColumnFormat.SEP
        ...
    ```
    """

    WIDTH = tuple()
    SEP = 1

    def __init__(self, width, sep=1):
        self.width = width
        self.sep = sep

    def __enter__(self):
        ColumnFormat.WIDTH = self.width
        ColumnFormat.SEP = self.sep
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        ColumnFormat.WIDTH = tuple()
        ColumnFormat.SEP = 1


def get_all_options(options):
    """
    Unpack all options from nested groups of options.
    This is useful to compute a column format that is compatible with
    all the options that will be displayed.

    Parameters
    ----------
    options : GROUP or list[GROUP or OPTION]
        Nested groups of options

    Returns
    -------
    options : list[OPTION]
        A flat list of options
    """
    alloptions = []
    for option in options:
        if isinstance(option, OPTION):
            alloptions.append(option)
        elif isinstance(option, GROUP):
            alloptions.extend(get_all_options(option))
    return alloptions


def get_colformat(options, level, maxwidth):
    """
    Return a `ColumnFormat` context that is compatible with a
    list of options.

    Parameters
    ----------
    options : GROUP or list[GROUP or OPTION]
        Nested groups of options
    level : int
        The requested help level. Only options whose help level is lower
        than this will be displayed
    maxwidth : int
        The maximum number of characters in a line

    Returns
    -------
    context : ColumnFormat
        A `ColumnFormat` context
    """
    alloptions = get_all_options(options)
    alloptions = [opt.tostring(level) for opt in alloptions]
    alloptions = [opt for opt in alloptions if opt]
    sep, width = compute_colwidths(alloptions, maxwidth)
    return ColumnFormat(width, sep)


def compute_colwidths(options, maxwidth=DEFAULT_WIDTH, minwidth=40):
    width = []
    for option in options:
        width += [0 for _ in range(max(0, len(option) - len(width)))]
        for n, col in enumerate(option):
            width[n] = max(width[n], len(col))
    if sum(width) + len(width) - 1 > maxwidth:
        width[-1] = maxwidth - (sum(width[:-1]) + len(width) - 1)
        width[-1] = max(minwidth, width[-1])
    sep = maxwidth - sum(width)
    sep = max(1, sep // (len(width) - 1))
    return sep, width


def catcol(columns, colwidth, sep=1):
    columns = [textwrap.wrap(col, width, break_long_words=False)
               for col, width in zip(columns, colwidth)]
    nbrows = max([len(col) for col in columns])
    s = []
    for n in range(nbrows):
        row = []
        for col, width in zip(columns, colwidth):
            if len(col) > n:
                minirow = col[n]
            else:
                minirow = ''
            row += [minirow + ' ' * max(0, (width - len(minirow)))]
        row = (' ' * sep).join(row)
        s += [row]
    s = '\n'.join(s)
    return s
