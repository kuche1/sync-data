#! /usr/bin/env python3

from argparse import ArgumentParser
import tomllib
from pathlib import Path
import warnings
from datetime import datetime
import subprocess

SYSTEM_HOSTS_FILE = Path("/etc/hosts")


type Ip = str
type Host = str


def node_delete(node: Path) -> None:
    now = datetime.now()
    new_name = node.with_name(node.name + ".bak_" + now.strftime("%Y-%m-%d_%H-%M-%S"))
    print(f"Deleted file to `{new_name}`")
    node.rename(new_name)


def node_symlink(real_file: Path, symlink_to_create: Path) -> None:
    if symlink_to_create.exists():
        # if the existing file is a symlink and it points to the right location, leave it as is # TODO: but what if it is a symlink to a symlink ? do they both get resolved ?
        if symlink_to_create.resolve() == real_file:
            return

        # if the existing file is not a symlink or it does not point to the right location, "delete" it
        node_delete(symlink_to_create)

    print(f"Symlinking `{symlink_to_create}` -> `{real_file}`")
    symlink_to_create.symlink_to(
        real_file
    )  # TODO: but what if it is a nested subdirectory ?


def sudo_copy_file(source: Path, destination: Path) -> None:
    print(f"Sudo copying `{source}` -> `{destination}`")
    subprocess.run(["sudo", "cp", source, destination], check=True)


def sudo_append_file(file: Path, data: str) -> None:
    print(f"Sudo appending `{file}` -> ```{data}```")
    subprocess.run(["sudo", "tee", "-a", file], text=True, input=data, check=True)


def sudo_service_start_enable(name: str) -> None:
    subprocess.run(["sudo", "systemctl", "enable", "--now", name], check=True)


def handle_sync_folder(config_toml_parent: Path, config: dict) -> None:
    sync_folder = config_toml_parent / config.pop("sync-folder")
    symlinks = config.pop(
        "symlinks"
    )  # TODO: need to check if there are any additional nodes in the sync folder that are missing here

    for relative_path in symlinks:
        sync_folder_node = sync_folder / relative_path
        home_folder_node = Path.home() / relative_path

        if sync_folder_node.exists():
            node_symlink(sync_folder_node, home_folder_node)
        else:
            warnings.warn(f"node does not exist: {sync_folder_node}")


def handle_services(config_toml_parent: Path, config: dict) -> None:
    key = "services-folder"

    if key not in config:
        return

    services_folder = config_toml_parent / config.pop(key)

    for dir_, folders, files in services_folder.walk():
        for folder in folders:
            path = dir_ / folder
            warnings.warn(f"folder ignored: {path}")

        for file in files:
            path_repo = dir_ / file
            path_system = Path("/etc/systemd/system") / file

            if path_system.exists():
                content_repo = path_repo.open("rb").read()
                content_system = path_system.open("rb").read()

                if content_repo != content_system:
                    warnings.warn(
                        f"different service with the same name already exists: `{path_system}` and `{path_repo}`"
                    )

                continue

            sudo_copy_file(path_repo, path_system)
            sudo_service_start_enable(path_system.stem)


def handle_hosts(config_toml_parent: Path, config: dict) -> None:
    def parse_hosts_file(file: Path) -> list[tuple[Ip, Host]]:
        with file.open() as f:
            data = f.readlines()

        # delete new line character
        for idx, line in enumerate(data):
            data[idx] = line.replace("\n", "")

        # delete comments
        for idx, line in reversed(list(enumerate(data))):
            if line.startswith("#"):
                del data[idx]

        # convert all whitespace variants into a single space
        for idx, line in enumerate(data):
            line = line.replace("\t", " ")

            while "  " in line:
                line = line.replace("  ", " ")

            data[idx] = line

        # convert whitespace-only lines into empty lines
        for idx, line in enumerate(data):
            if len(line) == line.count(" "):
                data[idx] = ""

        # delete empty lines
        for idx, line in reversed(list(enumerate(data))):
            if len(line) == 0:
                del data[idx]

        return_data = []

        for line in data:
            if line.count(" ") != 1:
                warnings.warn("parse failure")
                continue

            ip, host = line.split(" ")

            return_data.append((ip, host))

        return return_data

    key = "hosts-file"

    if key not in config:
        return

    repo_hosts_file = config_toml_parent / config.pop(key)

    system_data = parse_hosts_file(SYSTEM_HOSTS_FILE)
    repo_data = parse_hosts_file(repo_hosts_file)

    missing_entries = []

    for repo_ip, repo_host in repo_data:
        if any(system_host == repo_host for _system_ip, system_host in system_data):
            continue
        missing_entries.append((repo_ip, repo_host))

    if len(missing_entries) <= 0:
        return

    data_to_append = "\n"
    for repo_ip, repo_host in missing_entries:
        data_to_append += f"{repo_ip} {repo_host}\n"

    sudo_append_file(SYSTEM_HOSTS_FILE, data_to_append)


def main(config_toml: Path) -> None:
    with config_toml.open("rb") as f:
        config = tomllib.load(f)

    handle_sync_folder(config_toml.parent, config)
    handle_services(config_toml.parent, config)
    handle_hosts(config_toml.parent, config)

    if len(config) != 0:
        warnings.warn(f"unknown config items: {config}")


def parse_cmdline() -> None:
    parser = ArgumentParser()
    parser.add_argument("config_toml", type=Path)
    args = parser.parse_args()

    main(args.config_toml)


if __name__ == "__main__":
    parse_cmdline()
