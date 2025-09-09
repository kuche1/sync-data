#! /usr/bin/env python3

from argparse import ArgumentParser
import tomllib
from pathlib import Path
import warnings
from datetime import datetime
import os

def node_delete(node: Path) -> None:
    now = datetime.now()
    new_name = node.with_name(node.name + f'.bak_' + now.strftime("%Y-%m-%d_%H-%M-%S"))
    print(f'Deleted file to `{new_name}`')
    node.rename(new_name)

def node_symlink(real_file: Path, symlink_to_create: Path) -> None:
    if symlink_to_create.exists():
        # if the existing file is a symlink and it points to the right location, leave it as is # TODO: but what if it is a symlink to a symlink ? do they both get resolved ?
        if symlink_to_create.resolve() == real_file:
            return
        
        # if the existing file is not a symlink or it does not point to the right location, "delete" it
        node_delete(symlink_to_create)

    print(f'Symlinking `{symlink_to_create}` -> `{real_file}`')
    symlink_to_create.symlink_to(real_file)

def main(config_toml: str) -> None:
    config_toml = Path(config_toml)

    with config_toml.open("rb") as f:
        config = tomllib.load(f)
    
    sync_folder = config_toml.parent / config.pop('sync-folder')
    symlinks = config.pop('symlinks') # TODO: need to check if there are any additional nodes in the sync folder that are missing here

    if len(config) != 0:
        warnings.warn(f'unknown config items: {config}')
    
    for relative_path in symlinks:
        sync_folder_node = sync_folder / relative_path
        home_folder_node = Path.home() / relative_path

        print(f'{sync_folder_node.exists()}')
        print(f'{home_folder_node.exists()}')

        if sync_folder_node.exists():
            node_symlink(sync_folder_node, home_folder_node)
        else:
            raise NotImplementedError

def parse_cmdline() -> None:
    parser = ArgumentParser()
    parser.add_argument('config_toml', type=str)
    args = parser.parse_args()

    main(args.config_toml)

if __name__ == '__main__':
    parse_cmdline()