__all__ = ['populate']
# stdlib
from copy import deepcopy
from collections.abc import Mapping
# dep
import jsonschema
# internal
from parseman.actions import get_action
from parseman.checks import get_check


def populate(instance, schema):
    """
    Validate + Populate a YAML object with a schema

    YAML/JSON validators do not modify the instance, and therefore do
    not insert default values when optional keys are missing.
    In contrast, this function does insert default values.

    We further handle schemas that contain a set of private keys:
    - `x-checks` : a list of `parseman.Check` to apply on the data
    - `x-actions` : a list of `parseman.Action` to apply to the data

    Parameters
    ----------
    instance : object
        An object loaded by `yaml.load`
    schema : object
        A schema loaded by `yaml.load`

    Returns
    -------
    instance : object
        The input instance, modified in-place

    Yields
    ------
    jsonschema.ValidationError
    """
    validator = jsonschema.validators.validator_for(schema)
    # first pass : only checks and actions on fields effectively
    # set by the user. We do this before defaults because
    # 1. we expect the defaults to be valid
    # 2. if they are not, we assume that the author of the schema
    #    knows what they are doing
    # 3. we only trigger actions on non-default values
    #    (otherwise an action like SetTrue would always be triggered)
    validator1 = extend_validator(validator, ('checks', 'actions'))
    validator1(schema).validate(instance)
    # second pass: fill defaults
    validator2 = extend_validator(validator, ('defaults',))
    validator2(schema).validate(instance)
    return instance


def extend_validator(validator_class,
                     components=('checks', 'actions', 'defaults')):
    # https://stackoverflow.com/questions/41290777/
    # https://gist.github.com/adrien-berchet/4da364bee20b9d4286f3e38161d4eb72

    _NO_DEFAULT = object()
    do_validate = validator_class.VALIDATORS["properties"]

    def do_checks(validator, properties, instance, schema):
        for prop, subschema in properties.items():
            if prop not in instance:
                # FIXME: is it possible, since we've run set_default first?
                continue
            value = instance.get(prop)
            checks = subschema.get('x-check', [])
            if not isinstance(checks, list):
                checks = [checks]

            for check in checks:
                if isinstance(check, dict):
                    if len(check) != 1:
                        raise jsonschema.ValidationError(
                            'Checks should be a (list of) elements, where '
                            'each element is either a string (i.e. the '
                            'checker name) or a one-element dictionary, '
                            'where the key is the checker name and the '
                            'element is a dictionary of options.\n'
                            f'I got a {len(check)}-elements dictionary.'
                        )
                    (check, args), = check.items()
                    if isinstance(args, dict):
                        args, kwargs = [], args
                elif not isinstance(check, str):
                    raise jsonschema.ValidationError(
                        'Checks should be a (list of) elements, where '
                        'each element is either a string (i.e. the '
                        'checker name) or a one-element dictionary, '
                        'where the key is the checker name and the '
                        'element is a dictionary of options.\n'
                        f'I got a {type(check).__name__}-typed element.'
                    )
                else:
                    args, kwargs = [], {}
                try:
                    check = get_check(check)(*args, **kwargs)
                    check(value)
                except Exception as e:
                    yield jsonschema.ValidationError(e)

    def do_actions(validator, properties, instance, schema):
        new_instance = deepcopy(instance)
        is_valid = True
        for prop, subschema in properties.items():
            if prop not in instance:
                continue
            value = instance.get(prop)
            actions = subschema.get('x-action', [])
            if not isinstance(actions, list):
                actions = [actions]

            for action in actions:
                if isinstance(action, dict):
                    if len(action) != 1:
                        raise jsonschema.ValidationError(
                            'Actions should be a (list of) elements, where '
                            'each element is either a string (i.e. the '
                            'action name) or a one-element dictionary, '
                            'where the key is the checker name and the '
                            'element is a dictionary of options.\n'
                            f'I got a {len(action)}-elements dictionary.'
                        )
                    (action, args), = action.items()
                    if isinstance(args, dict):
                        args, kwargs = [], args
                elif not isinstance(action, str):
                    raise jsonschema.ValidationError(
                        'Checks should be a (list of) elements, where '
                        'each element is either a string (i.e. the '
                        'action name) or a one-element dictionary, '
                        'where the key is the action name and the '
                        'element is a dictionary of options.\n'
                        f'I got a {type(action).__name__}-typed element.'
                    )
                else:
                    args, kwargs = [], {}
                try:
                    action = get_action(action)(*args, **kwargs)
                    value = action(value)
                except Exception as e:
                    is_valid = False
                    yield jsonschema.ValidationError(e)

                new_instance[prop] = value

        if is_valid:
            instance.update(new_instance)

    def do_defaults(validator, properties, instance, schema):
        drop_if_empty = set()
        new_instance = deepcopy(instance)
        is_valid = True
        for prop, subschema in properties.items():
            if prop in new_instance:
                continue
            obj_type = subschema.get("type", "")
            default_value = subschema.get("default", _NO_DEFAULT)
            if default_value is not _NO_DEFAULT:
                new_instance.setdefault(prop, default_value)
            elif obj_type == "object":
                new_instance.setdefault(prop, {})
                drop_if_empty.add(prop)

        for error in do_validate(
            validator,
            properties,
            new_instance,
            schema,
        ):
            is_valid = False
            yield error

        for prop in drop_if_empty:
            instance_prop = new_instance[prop]
            if isinstance(instance_prop, Mapping) and len(instance_prop) == 0:
                del new_instance[prop]

        if is_valid:
            instance.update(new_instance)

    def do_all(validator, properties, instance, schema):
        is_valid = True
        new_instance = deepcopy(instance)

        for error in do_validate(
            validator,
            properties,
            new_instance,
            schema,
        ):
            is_valid = False
            yield error

        if not is_valid:
            return

        if 'checks' in components:
            for error in do_checks(
                validator,
                properties,
                new_instance,
                schema,
            ):
                is_valid = False
                yield error

        if not is_valid:
            return

        if 'actions' in components:
            for error in do_actions(
                validator,
                properties,
                new_instance,
                schema,
            ):
                is_valid = False
                yield error

        if not is_valid:
            return

        if 'defaults' in components:
            for error in do_defaults(
                validator,
                properties,
                new_instance,
                schema,
            ):
                is_valid = False
                yield error

        if not is_valid:
            return

        instance.update(new_instance)

    return jsonschema.validators.extend(
        validator_class,
        {"properties": do_all},
    )
