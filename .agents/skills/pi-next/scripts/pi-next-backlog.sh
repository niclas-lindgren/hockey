#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="${1:-.}"
ACTION="${2:-list}"
shift 2 || true

if [ -f "$WORK_DIR/BACKLOG.md" ]; then
  PS_DIR="$(cd "$WORK_DIR" && pwd)"
elif [ -d "$WORK_DIR/.ps-next" ]; then
  PS_DIR="$(cd "$WORK_DIR/.ps-next" && pwd)"
else
  slug="$(basename "$(cd "$WORK_DIR" && pwd)")"
  PS_DIR="$HOME/.ps-next/projects/$slug"
fi

BACKLOG="$PS_DIR/BACKLOG.md"
[ -f "$BACKLOG" ] || { echo "BACKLOG.md not found at $BACKLOG" >&2; exit 1; }

python3 - "$BACKLOG" "$ACTION" "$@" <<'PY'
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

path = Path(sys.argv[1])
action = sys.argv[2]
args = sys.argv[3:]
text = path.read_text()

ITEM_RE = re.compile(r"^- \[(\d+)\] \[([ x])\] (.*)$", re.MULTILINE)
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

@dataclass
class Section:
    name: str
    start: int
    content_start: int
    end: int


def sections(src: str) -> dict[str, Section]:
    lines = src.splitlines(keepends=True)
    found: list[tuple[str, int]] = []
    pos = 0
    for line in lines:
        match = SECTION_RE.match(line.rstrip("\r\n"))
        if match:
            found.append((match.group(1).strip().lower(), pos))
        pos += len(line)
    result: dict[str, Section] = {}
    for index, (name, start) in enumerate(found):
        end = found[index + 1][1] if index + 1 < len(found) else len(src)
        line_end = src.find("\n", start)
        content_start = len(src) if line_end == -1 else line_end + 1
        result[name] = Section(name, start, content_start, end)
    return result


def item_blocks(src: str, section_name: str | None = None) -> list[dict]:
    scope_start = 0
    scope_end = len(src)
    if section_name is not None:
        sec = sections(src).get(section_name.lower())
        if not sec:
            return []
        scope_start, scope_end = sec.content_start, sec.end
    scope = src[scope_start:scope_end]
    starts: list[tuple[int, re.Match[str]]] = []
    for m in ITEM_RE.finditer(scope):
        starts.append((scope_start + m.start(), m))
    blocks = []
    for idx, (abs_start, match) in enumerate(starts):
        abs_end = starts[idx + 1][0] if idx + 1 < len(starts) else scope_end
        raw = src[abs_start:abs_end]
        # Keep only until the next section if this is the last item in the section.
        next_section = re.search(r"(?m)^##\s+", raw)
        if next_section and next_section.start() != 0:
            raw = raw[: next_section.start()]
            abs_end = abs_start + len(raw)
        blocks.append({
            "id": int(match.group(1)),
            "checked": match.group(2) == "x",
            "text": match.group(3),
            "start": abs_start,
            "end": abs_end,
            "raw": raw,
        })
    return blocks


def all_ids(src: str) -> list[int]:
    return [int(m.group(1)) for m in ITEM_RE.finditer(src)]


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def duplicate_ids(src: str) -> list[int]:
    ids = all_ids(src)
    return sorted({item_id for item_id in ids if ids.count(item_id) > 1})


def ensure_done_section(src: str) -> str:
    if "done" in sections(src):
        return src
    return src.rstrip() + "\n\n## Done\n"


def open_blocks(src: str) -> list[dict]:
    return [block for block in item_blocks(src, "open") if not block["checked"]]


def write_updated(src: str) -> None:
    path.write_text(src)


if action == "list":
    for block in open_blocks(text):
        first = block["raw"].splitlines()[0]
        print(first)
    raise SystemExit(0)

if action == "get":
    if len(args) != 1:
        fail("usage: pi-next-backlog.sh WORK_DIR get ID")
    target = int(args[0])
    matches = [block for block in open_blocks(text) if block["id"] == target]
    if len(matches) != 1:
        fail(f"Open backlog item [{target}] not found or not unique")
    print(matches[0]["raw"].rstrip())
    raise SystemExit(0)

if action == "add":
    if not args or not " ".join(args).strip():
        fail("usage: pi-next-backlog.sh WORK_DIR add TEXT")
    dups = duplicate_ids(text)
    if dups:
        fail("Duplicate backlog IDs found: " + ", ".join(map(str, dups)))
    new_id = (max(all_ids(text)) + 1) if all_ids(text) else 1
    new_line = f"- [{new_id}] [ ] {' '.join(args).strip()}\n"
    sec = sections(text).get("open")
    if sec:
        insert_at = sec.content_start
        updated = text[:insert_at] + ("" if text[insert_at:insert_at+1] == "\n" else "\n") + new_line + text[insert_at:]
    else:
        updated = text.rstrip() + "\n\n## Open\n\n" + new_line
    write_updated(updated)
    print(new_line.rstrip())
    raise SystemExit(0)

if action == "done":
    if len(args) != 1:
        fail("usage: pi-next-backlog.sh WORK_DIR done ID")
    target = int(args[0])
    open_matches = [block for block in open_blocks(text) if block["id"] == target]
    if len(open_matches) != 1:
        fail(f"Open backlog item [{target}] not found or not unique")
    if sum(1 for item_id in all_ids(text) if item_id == target) != 1:
        fail(f"Backlog item [{target}] has duplicate/conflicting IDs")
    block = open_matches[0]
    today = date.today().isoformat()
    lines = block["raw"].rstrip("\n").splitlines()
    first = re.sub(r"^- \[(\d+)\] \[ \] (.*)$", rf"- [{target}] [x] \2 ({today})", lines[0])
    moved = "\n".join([first, *lines[1:]]) + "\n"
    without = text[: block["start"]] + text[block["end"] :]
    without = ensure_done_section(without)
    done_sec = sections(without)["done"]
    insert_at = done_sec.content_start
    prefix = without[:insert_at]
    suffix = without[insert_at:]
    spacer = "" if suffix.startswith("\n") or not suffix else "\n"
    updated = prefix + moved + spacer + suffix
    write_updated(updated)
    print(f"Marked [{target}] done.")
    raise SystemExit(0)

if action == "validate":
    dups = duplicate_ids(text)
    if dups:
        fail("Duplicate backlog IDs found: " + ", ".join(map(str, dups)))
    print("VALID")
    raise SystemExit(0)

fail(f"Unknown action: {action}")
PY
