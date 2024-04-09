from omegaconf import OmegaConf
from simple_cfg import parse_args, add_args, cli_defaults, add_module_args, save_args_to_cfg
import argparse
import importlib
import os


def default_args():
    return dict(
        lib="example_lib",
    )

def main(args):
    lib = importlib.import_module(args.lib)
    print("Calling sub_lib print function:")
    lib.print_arguments(args.sub_lib)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_args(parser, cli_defaults())
    add_args(parser, default_args())

    # Add arguments from an other file
    add_module_args(parser, "lib", "sub_lib", args_fn="default_args")
    # Parse + save config
    args = parse_args(parser)
    os.makedirs(args.workdir, exist_ok=False)
    save_args_to_cfg(args)

    # Print arguments to command line:
    print("### Arguments for the run: ###")
    print(OmegaConf.to_yaml(args, sort_keys=True))
    print("-----")
    print("Calling main...")
    main(args)