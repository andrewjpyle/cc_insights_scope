#!/usr/bin/env python3
"""Assemble a scoped CLAUDE_CONFIG_DIR workspace for a single repo, pooling
session transcripts from multiple sources (this machine + synced copies from
other machines / other Claude Code accounts).

`/insights` analyzes every `*.jsonl` transcript under the active config dir's
`projects/` folder, and it respects `CLAUDE_CONFIG_DIR`. It has no repo filter:
you get one report for every session on the machine, mixing every project you
have ever touched. By building a throwaway config dir that contains ONLY the
transcripts for one repo — copied from however many source roots you point at —
you get a repo-scoped, cross-account insights report instead.

On macOS auth lives in the Keychain (global), so launching with this workspace
usually needs no re-login.

Pure stdlib. No network, no third-party packages. Safe to run anywhere.

Examples
--------
  # this machine only, repo "my_project"
  cc_insights_scope.py my_project

  # pool this machine + a folder you rsynced from your work laptop
  cc_insights_scope.py my_project --source ~/cc-sources/my_project-work

The repo argument is a FRAGMENT, not an exact path: it is normalized to a match
token (e.g. "my_project" -> "my-project") and every project folder across all
sources whose encoded name CONTAINS that token is pooled. That tolerates a
different OS username on the other machine, which changes the folder prefix —
matching on the full encoded path would silently find nothing.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


def encode_token(fragment: str) -> str:
    """Normalize a repo fragment the way Claude Code encodes path segments:
    every run of non-alphanumeric characters (``/``, ``_``, ``.``, space)
    collapses to a single ``-``, lowercased for matching."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", fragment).strip("-").lower()


def candidate_projects_dirs(root: Path) -> list[Path]:
    """A source root may be any of three shapes, and we accept all of them:

    * a **config dir** (has a ``projects/`` child) — e.g. ``~/.claude``
    * a **``projects/`` dir** itself
    * a **bare folder of encoded project dirs** — e.g. a folder you rsynced

    Return every plausible ``projects``-style dir to scan, de-duplicated.
    """
    dirs: list[Path] = []
    if (root / "projects").is_dir():
        dirs.append(root / "projects")
    if root.name == "projects" or any(root.glob("-*")):
        dirs.append(root)
    seen, out = set(), []
    for d in dirs:
        rp = d.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(d)
    return out


def find_matching_folders(sources: list[Path], token: str) -> list[Path]:
    """Every project folder, across every source, whose encoded name contains
    ``token``. A missing source is a warning, not an error — you may be running
    on a machine where only some of the sources exist."""
    matches: list[Path] = []
    for src in sources:
        if not src.exists():
            print(f"  ! source not found, skipping: {src}", file=sys.stderr)
            continue
        for pdir in candidate_projects_dirs(src):
            for child in sorted(pdir.iterdir()):
                if child.is_dir() and token in child.name.lower():
                    matches.append(child)
    return matches


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build a repo-scoped /insights workspace.")
    ap.add_argument(
        "repo",
        help="Repo fragment, e.g. my_project (matched as a substring of the encoded folder name).",
    )
    ap.add_argument(
        "--source", action="append", default=[],
        help="Extra source root to pool from (repeatable). May be a config dir, a projects/ dir, "
             "or a bare folder of encoded project dirs — e.g. a folder rsynced from another machine.",
    )
    ap.add_argument(
        "--default-source", default=str(Path.home() / ".claude"),
        help="The live config dir for this account (default ~/.claude). Pass '' to exclude it.",
    )
    ap.add_argument(
        "--mirror", action="append", default=[],
        help="Extra shared-storage mirror root to auto-include if it exists (repeatable). "
             "Defaults to the Dropbox cc-transcripts mirror written by contrib/launchd/.",
    )
    ap.add_argument(
        "--no-mirror", action="store_true",
        help="Don't auto-include any shared-storage mirror.",
    )
    ap.add_argument(
        "--workspace", default="",
        help="Output config dir (default ~/.claude-insights/<repo-token>).",
    )
    args = ap.parse_args(argv)

    token = encode_token(args.repo)
    if not token:
        print("error: repo fragment is empty after normalization", file=sys.stderr)
        return 2

    workspace = (
        Path(args.workspace).expanduser() if args.workspace
        else Path.home() / ".claude-insights" / token
    )
    dest_projects = workspace / "projects"
    canonical = dest_projects / f"insights-scope-{token}"

    sources: list[Path] = []
    if args.default_source:
        sources.append(Path(args.default_source).expanduser())
    sources.extend(Path(s).expanduser() for s in args.source)

    # Auto-include the shared-storage mirror written by the launchd router in
    # contrib/launchd/, so cross-machine / cross-account pooling works with no
    # --source flag at all. Both the classic and the modern CloudStorage Dropbox
    # paths are probed; override or extend with --mirror.
    if not args.no_mirror:
        mirrors = [Path(m).expanduser() for m in args.mirror] or [
            Path.home() / "Dropbox" / "cc-transcripts",
            Path.home() / "Library" / "CloudStorage" / "Dropbox" / "cc-transcripts",
        ]
        for m in mirrors:
            if m.is_dir() and m not in sources:
                sources.append(m)

    print(f"repo fragment : {args.repo}")
    print(f"match token   : {token}")
    print(f"workspace     : {workspace}")
    print(f"sources       : {', '.join(str(s) for s in sources)}")
    print()

    folders = find_matching_folders(sources, token)
    if not folders:
        print(f"error: no project folders matched token '{token}' in any source.", file=sys.stderr)
        print("       Check the repo name, or that the other machine's transcripts are", file=sys.stderr)
        print("       synced into a --source dir.", file=sys.stderr)
        return 1

    # Rebuild the workspace's projects dir from scratch. Without this, a previous
    # repo's transcripts stay behind and silently join the next report — and a
    # too-large report is indistinguishable from a correct one.
    if dest_projects.exists():
        shutil.rmtree(dest_projects)
    canonical.mkdir(parents=True)

    copied, skipped_dupe = 0, 0
    per_folder: dict[str, int] = {}
    for folder in folders:
        n = 0
        for jsonl in sorted(folder.glob("*.jsonl")):
            target = canonical / jsonl.name
            if target.exists():  # the same session id, synced from two places
                skipped_dupe += 1
                continue
            shutil.copy2(jsonl, target)
            copied += 1
            n += 1
        per_folder[str(folder)] = n

    print("pooled transcripts:")
    for f, n in per_folder.items():
        print(f"  {n:4d}  {f}")
    print(f"\n  total copied: {copied}   (skipped {skipped_dupe} duplicate session files)")

    print("\n" + "=" * 70)
    print("NEXT — launch Claude Code against this scoped workspace, then /insights:")
    print(f'\n  CLAUDE_CONFIG_DIR="{workspace}" claude\n')
    print("  …then run:  /insights")
    print("=" * 70)
    print("Run /insights INTERACTIVELY (not `claude -p`): a fresh config dir is not")
    print("auto-authenticated. If it says 'Not logged in', run /login ONCE in that dir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
