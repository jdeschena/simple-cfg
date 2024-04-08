from omegaconf import OmegaConf

def default_args():
    return dict(
        v1=12,
        name="example_lib"
    )


def print_arguments(args):
    print(OmegaConf.to_yaml(args))