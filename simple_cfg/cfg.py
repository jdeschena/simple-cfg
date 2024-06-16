import argparse
import omegaconf
from omegaconf import OmegaConf
import yaml
import os
from os import path as osp
from datetime import datetime
import sys
import importlib
import inspect

_TYPE_MAPPINGS = {
    int: "Integer",
    float: "Float",
    str: "String",
    bool: "Boolean",
    list: "List",
    dict: "Dictionary",
    tuple: "Tuple",
    set: "Set",
    frozenset: "Frozen Set",
    complex: "Complex Number",
    bytes: "Bytes",
    bytearray: "Byte Array",
    memoryview: "Memory View",
    range: "Range",
    type(None): "NoneType",
}


def get_cli_type_string(obj_type):
    return _TYPE_MAPPINGS.get(obj_type, None)


def vassert(cond: bool, err_msg: str):
    """Assertion util; raise a ValueError if the condition is not met

    Args:
        cond (bool): Condition to be met
        err_msg (str): Error message to be displayed

    Raises:
        ValueError: Throw if `cond` is False
    """
    if not cond:
        raise ValueError(err_msg)


def flatten_dict(d: dict, sep="/"):
    """Flatten nested dictionnaries.

    Args:
        d (dict): Dictionary with nested dictionaries.
        sep (str, optional): Separator to use to compute the flattened. Defaults to "/".

    Returns:
        dict: Flat dictionary, with keys corresponding to the nesting structure.
    """
    out_dict = dict()

    for k, v in d.items():
        if isinstance(v, dict) or isinstance(v, omegaconf.dictconfig.DictConfig):
            sub_flat = flatten_dict(v, sep)
            sub_flat = {f"{k}{sep}{sub_k}": v for sub_k, v in sub_flat.items()}
            out_dict.update(sub_flat)
        else:
            out_dict[k] = v

    return out_dict


def unflatten_dict(d: dict, sep="/"):
    """Reverse `flatten_dict` operation.

    Args:
        d (dict): One-level dictionary to unflatten.
        sep (str, optional): Separator to split the flat key. Defaults to "/".

    Returns:
        dict: Nested dictionary from the flattened one.
    """
    out_dict = dict()

    def insert_rec(root, key, value):
        if len(key) == 1:
            k = key[0]
            root[k] = value
        else:
            k = key[0]
            rest = key[1:]
            if k not in root:
                root[k] = dict()
            insert_rec(root[k], rest, value)

    for k, v in d.items():
        insert_rec(out_dict, k.split(sep), v)

    return out_dict


def str2bool(v):
    """Parse string to boolean value.

    Args:
        v (str): String to base.

    Raises:
        argparse.ArgumentTypeError: if string cannot be parsed.

    Returns:
        bool: Boolean value extracted from string.

    Taken from https://stackoverflow.com/questions/15008758/parsing-boolean-values-with-argparse
    """

    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("boolean value expected")


def default_arguments():
    """Default arguments injected into all configs from the parser.

    Returns:
        dict: Dictionnary with default arguments.
    """
    return dict(
        seed=0,
        cfg_from=None,
        workdir=None,
    )


def add_args(parser: argparse.ArgumentParser, defaults: dict, prefix: str = ""):
    """Add arguments from a dictionnary of default values to an argparse parser.

    Args:
        parser (argparse.ArgumentParser): Parser from argparse library.
        defaults (dict): Dictionnary containing default values; Used to infer types of parameters in parser.
        prefix (str, optional): Prefix of parameters. For example, if prefix is `test` and `defaults` contains a key `val1`, it will be accessible in the parser/config as `test.val1`. Defaults to "".
    """
    for k, v in defaults.items():
        v_type = type(v)
        if v is None:
            parse_type = str
            help_type = str
        elif isinstance(v, bool):
            parse_type = str2bool
            help_type = bool
        else:
            help_type = parse_type = v_type

        if prefix != "":
            k = f"--{prefix}.{k}"
        else:
            k = "--" + k

        helper_type = get_cli_type_string(help_type)
        helper_string = f"Default: `{v}`"
        if helper_type is None:
            helper_string += " (Unknown type)"
        else:
            helper_string += f". Type: {helper_type}"

        parser.add_argument(k, default=v, type=parse_type, help=helper_string)


def get_default_from_signature(sig):
    default_args = dict()
    empty_parameters = []

    for k, v in sig.parameters.items():
        if k == "self":
            continue
        if v.default is inspect.Parameter.empty:
            empty_parameters.append(k)
        else:
            default_args[k] = v.default

    if len(empty_parameters) > 0:
        err_message = "The following parameters have no default_values. Please define a default value for the parser to work:\n"
        err_message += "\n".join("\t* " + v for v in empty_parameters)
        raise ValueError(err_message)

    return default_args


def get_default_from_fn(fn):
    sig = inspect.signature(fn)
    if len(sig.parameters) == 0:
        return fn()  # Assumes that it returns a dictionary containing the parameters
    else:
        return get_default_from_signature(sig)


def get_default_from_class(cls):
    sig = inspect.signature(cls.__init__)
    return get_default_from_signature(sig)


def get_default_args(obj):
    if inspect.isfunction(obj):
        return get_default_from_fn(obj)
    elif inspect.isclass(obj):
        return get_default_from_class(obj)
    else:
        raise ValueError(
            f"`obj` should be either a callable function or a class. Current type: `{type(obj)}`"
        )


def add_module_args(
    parser: argparse.ArgumentParser, attr: str, prefix: str, loc: str = "default_args"
):
    """Add default arguments, imported from the module referenced in `attr` into the parser.

    Args:
        parser (argparse.ArgumentParser): Standard argparse's parser.
        attr (str): Argument from the parser where the library to import from is stored. Example: "library.module1".
        prefix (str): Prefix of defaults imported from `attr` (i.e. in what sub field of the config they will be).
        loc (str): Which attribute of the module to take arguments from. Can be a top-level class or function.
    """
    args = parse_args(parser, parse_known_only=True)
    module_key = get_args_rec(args, attr)
    if module_key is not None:
        module = importlib.import_module(module_key)
        obj = getattr(module, loc)
        args_to_add = get_default_args(obj)
        add_args(parser, args_to_add, prefix)


def get_cli_passed_args():
    """Return actual arguments passed from the command line (as opposed to the ones having default values)

    Returns:
        set: Set of argument names. Assumes they start with --
    """
    arguments = set()
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            arguments.add(arg[2:])

    arguments -= set(["cfg_from"])
    return arguments


def check_missing_keys(parser: argparse.ArgumentParser, args: dict):
    """Check whether there are too many or too few parameters. Typically useful when loading a configuration from a yaml file. Use the parser to determine which arguments are required.

    Args:
        parser (argparse.ArgumentParser): argparse's parser.
        args (dict): Actual arguments received by the program.

    Raises:
        ValueError: If missing key in args.
        ValueError: If unexpected (additional) key in args.
    """
    default_expected_args = parser.parse_args([])
    keys = vars(default_expected_args).keys()
    actual_keys = flatten_dict(args, ".").keys()

    missing_keys = keys - actual_keys
    additional_keys = actual_keys - keys

    if len(missing_keys) > 0:
        err_message = "Missing keys in config:"
        for k in missing_keys:
            err_message += f"\n    * `{k}`"
        raise ValueError(err_message)

    if len(additional_keys) > 0:
        err_message = "Unknown keys in arguments not required by program:"
        for k in additional_keys:
            err_message += f"\n    * `{k}`"

        raise ValueError(err_message)


def check_workdir(args: OmegaConf):
    """Check that the `workdir` key is set, or compute a value based of script name

    Args:
        args (OmegaConf): Object containing the cli args

    Returns:
        OmegaConf: updated cli args object (set its `workdir` field)
    """
    script_name, _ = osp.splitext(sys.argv[0])
    now = datetime.now()
    day_str = now.strftime("%d-%m-%Y")
    time_str = now.strftime("%H:%M:%S")
    workdir_parent = "./runs"
    workdir = osp.join(workdir_parent, script_name, day_str, time_str)

    idx = 2
    while osp.exists(workdir):
        time_str = now.strftime(f"%H:%M:%S({idx})")
        workdir = osp.join(workdir_parent, script_name, day_str, time_str)
        idx += 1

    args.workdir = workdir

    return args


def parse_args(parser: argparse.ArgumentParser, parse_known_only=False, args=None):
    """Parse args: create OmegaConf dictionnary containing arguments from the parser.

    Args:
        parser (argparse.ArgumentParser): argparse's parser.
        parse_known_only (bool, optional): Whether to parse only known arguments, useful for parsing while not all arguments are provided. Defaults to False.
        args (list, optional): Optional list of arguments to parse, instead of using the input from the command. Defaults to None.

    Returns:
        dict: OmegaConf dictionnary (can use dotted notation on it).
    """
    known_only_args, _ = parser.parse_known_args(args)
    known_keys = set(vars(known_only_args).keys())

    if known_only_args.cfg_from is not None:
        # Load config from file if cfg_from defined
        with open(known_only_args.cfg_from, "r") as f:
            yaml_in = yaml.safe_load(f)

        yaml_args = OmegaConf.create(yaml_in)
        flat_yaml_args = flatten_dict(yaml_args, sep=".")
        # Avoid parsing unknown stuff
        if parse_known_only:
            cli_non_default_args = get_cli_passed_args() & known_keys
        else:
            cli_non_default_args = get_cli_passed_args()
        # Overwrite config from CLI if provided
        known_only_dict = vars(known_only_args)
        for cli_k in cli_non_default_args:
            vassert(cli_k in known_only_dict, f"Unknown CLI arg passed: `{cli_k}`.")
            flat_yaml_args[cli_k] = known_only_dict[cli_k]

        if parse_known_only:
            flat_yaml_args = {
                k: v for k, v in flat_yaml_args.items() if k in known_keys
            }

        args = unflatten_dict(flat_yaml_args, sep=".")
        args = OmegaConf.create(args)

    elif parse_known_only:
        # Parse only known args
        args = vars(known_only_args)
        args = unflatten_dict(args, ".")
        args = OmegaConf.create(args)
    else:
        # Parse from command line
        args = parser.parse_args(args)
        args = vars(args)
        args = unflatten_dict(args, ".")
        args = OmegaConf.create(args)

    if not parse_known_only:
        check_missing_keys(parser, args)

    if args.workdir is None:
        args = check_workdir(args)
    return args


def get_parser():
    parser = argparse.ArgumentParser()
    add_args(parser, default_arguments())
    return parser


def save_args_to_cfg(args: dict):
    """Save arguments to a config file for reproducibility. Use workdir field to find where to save.

    Args:
        args (dict): OmegaConf dict of arguments.
    """
    config_out_path = osp.join(args.workdir, "config.yaml")
    os.makedirs(args.workdir, exist_ok=True)

    with open(config_out_path, "w") as f:
        f.writelines(OmegaConf.to_yaml(args))


def get_args_rec(args: dict, prefix: str, default=None):
    """Recursively extract an argument from a dictionnary using a dotted key (e.g. top_level.inner.key1).

    Args:
        args (dict): Dictionnary containing nested dictionnaries.
        prefix (str): Dotted predix to search for, e.g top_level.inner.key1. Each dot corresponds to entering a nested dictionnary
        default (any, optional): Default value to return if the key is not found. Defaults to None.

    Returns:
        any: Value in nested dictionary. If not found, return `default` argument.
    """
    ks = prefix.split(".")

    def _rec(ks, args):
        k = ks[0]
        tail = ks[1:]
        if k not in args:
            return default
        elif len(tail) == 0:
            return args[k]
        else:
            return _rec(tail, args[k])

    return _rec(ks, args)
