__all__ = [
    'schema2cli',
]
from .cli_help import schema2help
from .yaml_validate import populate


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

    def parser(args, cmd=''):
        which_help, help_level = find_help(args)
        if which_help == 'usage':
            print(schema2help(schema).renderusage(help_level, cmd=cmd))
            return
        elif which_help == 'help':
            print(schema2help(schema).renderhelp(help_level, cmd=cmd))
            return
        else:
            try:
                obj = args2yaml(args, schema)
                obj = populate(obj, schema)
                return obj
            except Exception as e:
                print(schema2help(schema).tostring())
                raise e

    return parser


# --- implementation ---

def find_help(args):
    if '--help' in args or '-h' in args or '--usage' in args:
        help_level = 0
        if '--help' in args:
            help_index = args.index('--help')
        elif '--usage' in args:
            help_index = args.index('--usage')
        elif '-h' in args:
            help_index = args.index('-h')
        if len(args) > help_index + 1:
            help_level = args[help_index+1]
            try:
                help_level = int(help_level)
            except ValueError:
                help_level = 0
        if '--usage' in args:
            return 'usage', help_level
        else:
            return 'help', help_level
    return '', 0


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


def str2bool(x):
    if x.lower()[0] in 'ty':
        return True
    elif x.lower()[0] in 'fn':
        return False
    else:
        return bool(int(x))


def schema2tagmap(schema):
    """
    Create a map from CLI tags to YAML hierarchy
    """
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
