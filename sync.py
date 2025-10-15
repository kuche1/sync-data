#! /usr/bin/env python3

from argparse import ArgumentParser
import tomllib
from pathlib import Path
import warnings
from datetime import datetime
import os
import subprocess

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
    symlink_to_create.symlink_to(real_file) # TODO: but what if it is a nested subdirectory ?

def sudo_copy_file(source: Path, destination: Path) -> None:
    print(f'Sudo copying `{source}` -> `{destination}`')
    subprocess.run(['sudo', 'cp', source, destination], check=True)

def sudo_service_start_enable(name: str) -> None:
    subprocess.run(['sudo', 'systemctl', 'enable', '--now', name], check=True)

def handle_sync_folder(config_toml_parent: Path, config: dict) -> None:
    sync_folder = config_toml_parent / config.pop('sync-folder')
    symlinks = config.pop('symlinks') # TODO: need to check if there are any additional nodes in the sync folder that are missing here
    
    for relative_path in symlinks:
        sync_folder_node = sync_folder / relative_path
        home_folder_node = Path.home() / relative_path

        if sync_folder_node.exists():
            node_symlink(sync_folder_node, home_folder_node)
        else:
            warnings.warn(f'node does not exist: {sync_folder_node}')

def handle_services(config_toml_parent: Path, config: dict) -> None:
    key = "services-folder"

    if key not in config:
        return

    services_folder = config_toml_parent / config.pop(key)

    for dir_, folders, files in services_folder.walk():

        for folder in folders:
            path = dir_ / folder
            warnings.warn(f'folder ignored: {path}')

        for file in files:
            path_repo = dir_ / file
            path_system = Path('/etc/systemd/system') / file

            if path_system.exists():
                warnings.warn(f'service already exists: {path_system}')
                continue

            sudo_copy_file(path_repo, path_system)
            sudo_service_start_enable(path_system.stem)

def main(config_toml: str) -> None:
    config_toml = Path(config_toml)

    with config_toml.open("rb") as f:
        config = tomllib.load(f)

    handle_sync_folder(config_toml.parent, config)
    handle_services(config_toml.parent, config)

    if len(config) != 0:
        warnings.warn(f'unknown config items: {config}')

def parse_cmdline() -> None:
    parser = ArgumentParser()
    parser.add_argument('config_toml', type=str)
    args = parser.parse_args()

    main(args.config_toml)

if __name__ == '__main__':
    parse_cmdline()