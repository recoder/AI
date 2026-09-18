"""Shared, non-executable Markdown song job reader."""
from pathlib import Path
import re
import yaml
from markdown_it import MarkdownIt


class UniqueLoader(yaml.SafeLoader):
    pass


# Keep tuning strings such as planning: off intact (YAML 1.2 boolean spelling).
UniqueLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in entries if tag != "tag:yaml.org,2002:bool"]
    for key, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
UniqueLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF"))


def mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result or key == "<<":
            raise ValueError("YAML keys must be unique strings; merge keys are unsupported")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def read_yaml(text):
    result = yaml.load(text, Loader=UniqueLoader)
    if not isinstance(result, dict):
        raise ValueError("Expected a YAML mapping")
    return result


def read_job(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    metadata = {}
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            raise ValueError("Unclosed YAML frontmatter")
        metadata = read_yaml("".join(lines[1:end]))
        lines = lines[end + 1:]
    tokens = MarkdownIt().parse("".join(lines))
    headings = [i for i, token in enumerate(tokens) if token.type == "heading_open" and token.tag == "h1"]
    if len(headings) != 1:
        raise ValueError("A job must have exactly one H1 song title")
    heading = tokens[headings[0]]
    if heading.level != 0 or "".join(lines[:heading.map[0]]).strip():
        raise ValueError("The H1 title must be the first body content")
    title = tokens[headings[0] + 1].content.strip()
    if not title:
        raise ValueError("Song title cannot be empty")
    blocks, excluded = {}, set(range(*heading.map))
    for token in tokens:
        if token.type != "fence":
            continue
        name = token.info.strip()
        if token.level != 0 or name not in {"song-positive-style", "song-negative-prompt", "song-lyrics", "song-reference-audio"}:
            raise ValueError(f"Unsupported generation code block: {name!r}")
        if name in blocks:
            raise ValueError(f"Duplicate generation code block: {name}")
        closing = lines[token.map[1] - 1].strip()
        if not re.fullmatch(re.escape(token.markup[0]) + "{" + str(len(token.markup)) + ",}", closing):
            raise ValueError(f"Unclosed generation code block: {name}")
        blocks[name] = token.content.strip()
        excluded.update(range(*token.map))
    body = "".join(line for i, line in enumerate(lines) if i not in excluded).strip()
    return {"title": title, "prompt": body, "metadata": metadata, "blocks": blocks}
