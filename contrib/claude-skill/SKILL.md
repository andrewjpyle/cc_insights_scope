---
name: insights-scope
description: |
  Use this skill when the user wants a `/insights` usage report scoped to ONE repository,
  and/or pooled across MULTIPLE Claude Code accounts or machines - e.g. "run insights just
  for my_project", "I work on this repo from two accounts, give me one combined report",
  "insights for <repo> across both my Macs". Claude Code's built-in `/insights` has no repo
  filter and analyzes every local session; this skill works around that by assembling a
  throwaway CLAUDE_CONFIG_DIR workspace containing ONLY the chosen repo's transcripts
  (pooled from however many source roots you point at), so the subsequent `/insights` run
  is automatically scoped and merged.

  Skip this skill for: a normal whole-machine `/insights` run (just run `/insights`), or
  questions about a single session.
allowed-tools:
  - Bash
  - Read
---

# insights-scope - repo-scoped, cross-account `/insights`

`/insights` rebuilds its analysis from every `*.jsonl` transcript under the **active config
dir's** `projects/` folder, and it respects `CLAUDE_CONFIG_DIR`. So to scope a report to one
repo - and/or pool it across accounts and machines - build a scratch config dir containing
only that repo's transcripts, then run `/insights` inside it.

## How to invoke

1. Work out the repo fragment (e.g. `my_project`) and any extra source roots the user has
   synced from other machines. The live `~/.claude` is always included automatically, as is
   the shared-storage mirror if the launchd router is installed.

2. Run the workspace builder (pure stdlib python3, no dependencies):

   ```bash
   python3 <path-to>/cc_insights_scope.py <repo-fragment> [--source <dir> ...]
   ```

   It pools every project folder whose encoded name contains the fragment (tolerant of a
   different username on another machine), copies the `*.jsonl` into
   `~/.claude-insights/<repo>/projects/`, and prints the exact launch line.

3. **Relay the printed launch line to the user.** They open a new Claude Code session in that
   workspace and run `/insights` there:

   ```bash
   CLAUDE_CONFIG_DIR="$HOME/.claude-insights/<repo>" claude
   # then: /insights
   ```

   This skill does **not** run `/insights` itself - it's an interactive command the user runs
   in the scoped session.

## The auth gotcha - do not skip this

A fresh `CLAUDE_CONFIG_DIR` is **not** auto-authenticated. Headless `claude -p "/insights"`
reports "Not logged in" and still emits a report - but only the deterministic half of it
(message/tool/language/timing stats). The LLM-analyzed sections ("What You Wanted",
"Outcomes", "Friction", "Satisfaction") come back "No data" because the model never ran.

It exits 0 and looks like a report. **Do not hand that to the user as the answer.** Tell them
to run `/insights` interactively in the workspace, and to `/login` once if prompted (it
persists in that dir).

## Notes

- The workspace's `projects/` is rebuilt fresh on every run, so a previously-scoped repo
  never leaks into the next report.
- If the builder exits 1 ("no project folders matched"), the repo fragment is wrong or the
  other machine's transcripts were never synced. Do not report this as "no activity found."
- **Confidentiality:** if the repo belongs to an employer or client, be deliberate about
  copying its transcripts into personal storage. The builder only reads and copies locally -
  where the `--source` files came from is the operator's call.
