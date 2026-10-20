from dataclasses import dataclass
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

import yaml


REPOSITORY = Path(__file__).resolve().parents[3]
TOOL_NAMES = ("ace-step", "minimax-music3", "yue")
# Share the runners' safe, duplicate-rejecting YAML 1.2 loader.
sys.path.insert(0, str(REPOSITORY / "bin"))
from song_jobs import UniqueLoader


def read_yaml(path):
    try:
        return yaml.load(Path(path).read_text(encoding="utf-8-sig"), Loader=UniqueLoader)
    except (OSError, yaml.YAMLError, ValueError):
        # YAML parser errors may include the offending secret line.
        raise ValueError("Cannot read configuration YAML; check the file and its syntax") from None


def inside(root, relative):
    if not isinstance(relative, str) or not relative.strip() or Path(relative).is_absolute():
        raise ValueError("Expected a nonempty relative workspace path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("Configured path escapes its workspace directory")
    return path


@dataclass(frozen=True)
class Settings:
    repository: Path
    bin_dir: Path
    state_dir: Path
    keys_file: Path
    host: str
    port: int
    public_url: str
    allowed_hosts: list[str]
    allowed_origins: list[str]
    tools: list[str]
    max_queued: int = 100
    max_text_bytes: int = 1048576


def load_settings(path=None):
    path = Path(path or REPOSITORY / "config/tool-service.yaml").resolve()
    data = read_yaml(path)
    fields = {"version", "host", "port", "public_url", "allowed_hosts", "allowed_origins",
              "keys_file", "state_directory", "max_queued", "max_text_bytes", "tools"}
    if not isinstance(data, dict) or set(data) != fields or type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Invalid tool-service configuration fields/version")
    for name, maximum in (("port", 65535), ("max_queued", 10000), ("max_text_bytes", 1048576)):
        if type(data[name]) is not int or not 1 <= data[name] <= maximum:
            raise ValueError(f"Invalid {name}")
    for name in ("allowed_hosts", "allowed_origins", "tools"):
        if not isinstance(data[name], list) or not data[name] or any(not isinstance(x, str) or not x for x in data[name]):
            raise ValueError(f"{name} must be a nonempty string list")
        if len(data[name]) != len(set(data[name])):
            raise ValueError(f"Duplicate entries in {name}")
    if set(data["tools"]) - set(TOOL_NAMES):
        raise ValueError("Only registered music adapters can be enabled")
    if any("*" in host or "/" in host or ":" in host for host in data["allowed_hosts"]):
        raise ValueError("allowed_hosts must contain explicit hostnames or IPv4 addresses")
    if not isinstance(data["host"], str) or not data["host"]:
        raise ValueError("host must be a nonempty string")
    for address in [data["public_url"], *data["allowed_origins"]]:
        if not isinstance(address, str):
            raise ValueError("URLs must be strings")
        url = urlsplit(address)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
            raise ValueError("URLs must be HTTP(S) origins without credentials or paths")
    if urlsplit(data["public_url"]).hostname not in data["allowed_hosts"]:
        raise ValueError("public_url hostname must appear in allowed_hosts")
    workspace_file = REPOSITORY / "config/workspace.yaml"
    manifest = read_yaml(workspace_file)
    workspace = manifest["workspace"]
    if manifest.get("version") != 1 or not isinstance(workspace, dict):
        raise ValueError("Invalid workspace configuration")
    if not isinstance(data["keys_file"], str) or not data["keys_file"].strip():
        raise ValueError("keys_file must be a nonempty path")
    root = (workspace_file.parent / os.environ.get("AI_WORKSPACE_ROOT", workspace["root"])).resolve()
    bin_dir = inside(root, workspace["directories"]["bin"])
    work_dir = inside(root, workspace["directories"]["work"])
    return Settings(REPOSITORY, bin_dir, inside(work_dir, data["state_directory"]),
                    (path.parent / data["keys_file"]).resolve(), data["host"], data["port"],
                    data["public_url"].rstrip("/"), data["allowed_hosts"],
                    [x.rstrip("/") for x in data["allowed_origins"]], data["tools"],
                    data["max_queued"], data["max_text_bytes"])


def load_keys(path):
    keys = read_yaml(path)
    if not isinstance(keys, list) or not keys or any(
        not isinstance(key, str) or not key.strip() or key != key.strip()
        or len(key) > 4096 or any(ord(c) < 32 for c in key) for key in keys
    ) or len(set(keys)) != len(keys):
        raise ValueError("Keys must be a nonempty YAML list of unique nonempty strings")
    if any("replace-with-a-long-random" in key for key in keys):
        raise ValueError("Replace the example keys before starting the service")
    return keys
