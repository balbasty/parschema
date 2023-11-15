import os
import yaml
from parschema import command


@command
def main(param):
    pass


@main.command(os.path.join(os.path.dirname(__file__), 'vesselseg_schema.yaml'))
def segment(param):
    print(yaml.dump(param, sort_keys=False))


if __name__ == '__main__':
    main()
