#!/usr/bin/env python3
"""Edit Yautja's config blocks without reformatting the surrounding user config."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


LEGACY_LUA = '''-- Yautja mode (neil.yautja). Remove with the plugin's uninstall.sh.
local yautja_mode = loadfile(os.getenv("HOME") .. "/.config/omarchy/plugins/neil.yautja/hypr/yautja.lua") -- neil.yautja
if yautja_mode then yautja_mode() end -- neil.yautja
'''
LUA_BLOCK = "-- >>> neil.yautja\n" + LEGACY_LUA + "-- <<< neil.yautja\n"
TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|//[^\n]*|/\*[\s\S]*?\*/|\s+|.', re.DOTALL)


def jsonc(text):
    """Parse JSONC, retaining token offsets for edits and allowing trailing commas."""
    clean = list(text)
    tokens = []
    for match in TOKEN.finditer(text):
        value = match.group()
        if value.startswith(("//", "/*")):
            clean[match.start():match.end()] = ["\n" if c == "\n" else " " for c in value]
        elif not value.isspace():
            tokens.append((value, match.start(), match.end()))
    for current, following in zip(tokens, tokens[1:]):
        if current[0] == "," and following[0] in ("}", "]"):
            clean[current[1]] = " "
    parsed = json.loads("".join(clean))
    if not isinstance(parsed, dict):
        raise ValueError("the menu must contain a JSONC object")
    return parsed, tokens


def remove_block(text, comment):
    start = re.compile(rf"^[ \t]*{comment} >>> neil\.yautja(?:[^\n]*)\n", re.MULTILINE)
    end = re.compile(rf"^[ \t]*{comment} <<< neil\.yautja[ \t]*(?:\n|$)", re.MULTILINE)
    starts, ends = list(start.finditer(text)), list(end.finditer(text))
    if not starts and not ends:
        return text
    if len(starts) != 1 or len(ends) != 1 or starts[0].start() >= ends[0].start():
        raise ValueError("Yautja config markers are incomplete or duplicated; repair them first")
    return text[:starts[0].start()] + text[ends[0].end():]


def menu_edit(original, fragment, install):
    # Check the original before changing it, including any existing managed block.
    jsonc(original)
    text = remove_block(original, "//")
    values, tokens = jsonc(text)
    if not install:
        return text
    additions, _ = jsonc("{\n" + fragment + "\n}")
    collisions = values.keys() & additions.keys()
    if collisions:
        raise ValueError("menu entries already exist outside the managed block: " + ", ".join(sorted(collisions)))
    closing = tokens[-1][1]
    # Insert the separator at the last value, before a possible end-of-line comment.
    if tokens[-2][0] not in ("{", ","):
        previous_end = tokens[-2][2]
        text = text[:previous_end] + "," + text[previous_end:]
        closing += 1
    prefix = text[:closing]
    # Put the block on its own line, including when the entire config was '{}'.
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    result = prefix + fragment.rstrip() + "\n" + text[closing:]
    jsonc(result)
    return result


def lua_edit(original, install):
    text = remove_block(original, "--")
    # Only remove the exact loader written by earlier releases, never other lines
    # merely mentioning the plugin's name.
    text = text.replace(LEGACY_LUA, "")
    if install:
        text = text.rstrip("\n") + "\n\n" + LUA_BLOCK
    return text


def save(path, original, updated):
    if original == updated:
        return
    path = path.resolve()  # Preserve config symlinks used by dotfile managers.
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        fd, backup = tempfile.mkstemp(prefix=path.name + ".bak.", dir=path.parent)
        os.close(fd)
        shutil.copy2(path, backup)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(updated)
        if path.exists():
            shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install", "uninstall"))
    parser.add_argument("hypr", type=Path)
    parser.add_argument("menu", type=Path)
    parser.add_argument("fragment", type=Path)
    args = parser.parse_args()
    install = args.action != "uninstall"
    edits = []
    if args.hypr.exists():
        original = args.hypr.read_text(encoding="utf-8")
        edits.append((args.hypr, original, lua_edit(original, install)))
    if args.menu.exists() or install:
        original = args.menu.read_text(encoding="utf-8") if args.menu.exists() else "{\n}\n"
        fragment = args.fragment.read_text(encoding="utf-8")
        edits.append((args.menu, original, menu_edit(original, fragment, install)))
    if args.action != "check":
        # Prepare and validate every edit before writing either config.
        for edit in edits:
            save(*edit)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f"Yautja config: {error}")
