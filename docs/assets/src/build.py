"""Build the README graphics for cc_insights_scope.

    python docs/assets/src/build.py
    uv run --with playwright==1.56.0 --with pillow python docs/assets/src/render.py docs/assets/src docs/assets

hero, how-it-works and guards are structural diagrams. anatomy renders ONLY from
captures/demo_run.json, a real run against the fictional sample data in examples/.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import readme_kit as k  # noqa: E402

REPO = "CC_INSIGHTS_SCOPE"


def hero() -> str:
    return k.hero(
        "CC_INSIGHTS_SCOPE · CLAUDE CODE TOOL · MIT",
        "/insights for",
        "one repo.",
        "Claude Code's report has no repo filter. This builds a throwaway config dir holding "
        "<b style='color:var(--ivory);font-weight:600'>only one repo's transcripts</b>, pooled "
        "from every machine and account you point it at.",
        [
            ("Pooled across machines", "Matches the repo by name fragment, so a different username on another machine still counts."),
            ("Rebuilt every run", "No stale transcripts from the last repo leak into this report."),
            ("Fails loudly", "No match, an empty pool or a workspace that would delete a source is an error."),
        ],
        "ONE FILE · STDLIB ONLY · 0 NETWORK CALLS",
        k.wheel(["LAPTOP", "DESKTOP", "MIRROR", "LIVE"], "ONE REPO", "Scope", size=560, node_r=52),
        f"{REPO} · HOW IT WORKS",
    )


def architecture() -> str:
    boxes = (
        k.box(56, 200, 250, 150, "SOURCE · LIVE", ["~/.claude", "projects/<encoded>/", "*.jsonl"])
        + k.box(56, 380, 250, 150, "SOURCE · --source", ["any config dir,", "projects/ dir, or bare", "rsynced folder"])
        + k.box(56, 560, 250, 120, "SOURCE · MIRROR", ["~/Dropbox/", "cc-transcripts/"])
        + k.box(400, 300, 300, 260, "MATCH + POOL", ["repo fragment ->", "token: my_project", "-> my-project", "", "substring of the", "encoded folder name,", "same UUID copied once"], True)
        + k.box(790, 300, 260, 260, "WORKSPACE", ["rebuilt from scratch", "~/.claude-insights/", "<token>/projects/", "refuses to delete", "a source"], True)
        + k.box(1110, 300, 234, 260, "YOU", ["CLAUDE_CONFIG_DIR=", "<workspace> claude", "", "then /insights", "(interactive)"])
    )
    arrows = [(306, 275, 400, 380), (306, 455, 400, 430), (306, 620, 400, 500), (700, 430, 790, 430), (1050, 430, 1110, 430)]
    return k.flow("HOW IT WORKS", f"Pool, scope, {k.em('run')}.", "read-only on every source · writes only inside the workspace", boxes, arrows, f"{REPO} · HOW IT WORKS")


def guards() -> str:
    cards = [
        ("EMPTY FRAGMENT", "Exit 2 instead of matching every folder you own.", "exit 2", "a fragment like ///"),
        ("NO MATCH", "Exit 1, not an empty workspace that reads as no work.", "exit 1", "typo in the repo name"),
        ("MATCHED, NO FILES", "Folders matched but held no transcripts: exit 1.", "exit 1", "new, with a test"),
        ("WORKSPACE IS A SOURCE", "Refuses to rebuild a dir it would delete: exit 2.", "exit 2", "new, with a test"),
        ("MISSING SOURCE", "A warning, not a failure. Other machines may be absent.", "warn + skip", "stderr"),
        ("DUPLICATE SESSION", "Same UUID from two places is copied once.", "skipped N", "never double counted"),
    ]
    return k.catalog("GUARDS", f"Six ways it says {k.em('no')}.", "Each guard has a test in tests/test_cc_insights_scope.py.", cards, f"{REPO} · HOW IT WORKS", cols=3, card_height=170)


def anatomy() -> str:
    c = k.load_capture(HERE / "captures" / "demo_run.json")
    lines = [ln for ln in c["output"].splitlines()]
    top = lines[:20]
    doc = [("code", k.esc(ln) or "&nbsp;") for ln in top]
    doc.append(("m", f"examples/ · SAMPLE DATA, fictional · captured {c['captured_at'][:10]}"))
    notes = [
        (140, "The repo name becomes a token. It matches the encoded folder on every machine."),
        (255, "Two usernames, two folder names, one repo. Both are found."),
        (322, "5 sessions copied. 1 was on both machines and is counted once. The unrelated repo in the laptop source is left out."),
        (440, "Then launch Claude Code in the scoped dir and run /insights."),
        (532, "Run it interactively: a fresh config dir is not logged in."),
    ]
    return k.anatomy("ANATOMY OF A REAL RUN", doc, notes, f"{REPO} · REAL RUN {c['captured_at'][:10]} · SAMPLE DATA", doc_width=780)


if __name__ == "__main__":
    pages = {"hero": hero(), "architecture": architecture(), "guards": guards()}
    if (HERE / "captures" / "demo_run.json").exists():
        pages["anatomy"] = anatomy()
    k.write_pages(HERE, pages)
