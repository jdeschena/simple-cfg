from omegaconf import OmegaConf


def default_args():
    return dict(v1=12, name="example_lib")


class Model:
    def __init__(self, only_arg="Lonely arg"):
        print(only_arg)


def print_arguments(args):
    print(OmegaConf.to_yaml(args))
