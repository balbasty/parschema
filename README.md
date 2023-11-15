# parseman

A parser for typed parameters (command line arguments, yaml files, json files, etc)

**Under very early development**


The specificity of this argument parser is that it relies entirely on
**YAML schemas** (or more exactly, on JSON schemas written in YAML).

This design means that one may provide arguments in the form of a
YAML config file _or_ as command-line arguments.

While there are similarities with
[**hydra**](https://github.com/facebookresearch/hydra), our difference
is that the command-line utility built by our framework follows
conventions typically used in unix commands (and by python CLI parsers
such as [**argparse**](https://docs.python.org/3/library/argparse.html) or
[**click**](https://click.palletsprojects.com).

To start with, we advise getting familiar with
[**JSON schemas**](https://json-schema.org).

We then provide an example CLI schema
([`examples/vesselseg_schema.yaml`](examples/vesselseg_schema.yaml))
and corresponding parameter file
([`examples/vesselseg_params.yaml`](examples/vesselseg_params.yaml)).

A CLI parser can be generated like this:
```python
import yaml
import parseman

with open('vesselseg_schema.yaml') as f:
    schema = yaml.load(f)

parser = parseman.schema2parser(schema)

parser(['--help'])
```

These few lines will print
```
VesselSeg OCT trainer
        Train a VesselSeg model for OCT data


All parameters related to training data:
--train    str ...   Training data (folder or list of files)
--eval     [str] ... Evaluation data (folder or list of files) (default: [])
--split    float     If no evaluation data, proportion of the training data to
                     use for evaluation (default: 0.2)

All parameters related to optimization:
--loss     any       Training losses (default: {'0': 'dice2'})
--metric   any       Metrics to monitor (default: ['dice2'])
--lr       float     Learning rate (default: 0.0001)
--epochs   int       Number of epochs (default: 200)

All parameters related to saving the model:
--folder   str       Path to output folder. A new folder specific to this run
                     will be written inside (default: .)
--naming   str       Naming convention. A relative path that can contain keys
                     {unique}, {run}, {params} which will be replaced by their
                     value at runtime (default: {datetime}_{unique})
--continue [bool]    Continue from latest checkpoint (default: False)
--every    int       Save the model every N epochs (default: 10)
--top      int       Save the top K models (default: 1)
--last     int       Save the last N models (default: 0)

All parameters related to the system:
--seed     int       Random seed (default: 42)
--gpu      [any] ... IDs of GPUs to use. If True, use default GPU. (default:
                     False)
Display help:
-h, --help [int]     Display this help. Value 1 shows more advanced options.
```

Now running
```python
params = parser(['--train', '/tmp'])

print(yaml.dump(params, sort_keys=False))
```
prints
```
data:
  train:
  - /tmp
  eval: []
  split: 0.2
optim:
  loss:
    '0': dice2
  metric:
  - dice2
  lr: 0.0001
  epochs: 200
archi:
  backbone: unet
  nblevels: 6
  nbfeat:
  - 24
  nbconv: 2
  affine: true
  activation: ELU
  kernel: 3
save:
  folder: .
  naming: '{datetime}_{unique}'
  continue: false
  every: 10
  top: 1
  last: 0
sys:
  seed: 42
  gpu: false
```

A function that takes a dictionary of parameters can easily be transformed
into a CLI parser using the decorator `parseman.command`:
```
@command(schema)
def segment(params):
    # do something with `params`, which is a dictionary of parameters
    ....

segment({'seed': 42})       # works
segment(['--seed', '42'])   # works too
```
