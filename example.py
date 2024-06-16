from omegaconf import OmegaConf
from simple_cfg import (
    parse_args,
    add_args,
    add_module_args,
    save_args_to_cfg,
    get_parser,
    get_default_args,
)
import importlib
import os


def default_args():
    return dict(
        lib="example_lib",
    )


def test_function(arg1=12, arg2=43):
    print(arg1)
    print(arg2)


class TestClass:
    def __init__(self, arg1="test argument 1", arg2="value to store in arg 2"):
        self.arg1 = arg1
        self.arg2 = arg2

        print(f"Successfully initialized class with `{arg1}`, `{arg2}`.")


def main(args):
    lib = importlib.import_module(args.lib)
    print("Calling sub_lib print function:")
    lib.print_arguments(args.sub_lib)

    print("Calling test function...")
    test_function(**args.test_fn)

    print("Constructing class...")


if __name__ == "__main__":
    parser = (
        get_parser()
    )  # Create argparse parser and add default arguments used by the library, seed, workdir, cfg_from (to load config from disk)
    # Add some arguments from a dictionary
    add_args(parser, default_args())
    # Add arguments using default from function signature
    add_args(parser, get_default_args(test_function), prefix="test_fn")
    # Add arguments using defaults from constructor of python class, located in the current file
    add_module_args(parser, "lib", prefix="sub_class_args", loc="Model")
    add_args(parser, get_default_args(TestClass), prefix="test_class")
    # Add arguments from an other file:
    # 1. Import the file in the field `lib`
    # 2. Get arguments by calling the function "default_args"
    # 3. Add the default arguments returned by lib.default_args to the parser in the subfield sub_lib
    add_module_args(parser, "lib", "sub_lib", loc="default_args")
    # Parse + save config
    args = parse_args(parser)
    os.makedirs(
        args.workdir, exist_ok=False
    )  # Ensure you are not erasing stuff from a previous run
    # Save args in `config.yaml` file in workdir
    save_args_to_cfg(args)

    # Print arguments to command line:
    print("### Arguments for the run: ###")
    print(OmegaConf.to_yaml(args, sort_keys=True))
    """
    Expected argument structure:
    cfg_from: null
    lib: example_lib
    seed: 0
    sub_class_args:
        only_arg: Lonely arg
    sub_lib:
        name: example_lib
        v1: 12
    test_class:
        arg1: test argument 1
        arg2: value to store in arg 2
    test_fn:
        arg1: 12
        arg2: 43
        workdir: ./runs/example/<today's date>/<current time>
    """
    print("-----")
    print("Calling main...")
    main(args)
