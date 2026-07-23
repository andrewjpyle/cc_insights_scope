# cc_insights_scope

**Run Claude Code's `/insights` on one repo — or on one repo across several machines and accounts.**

`/insights` has no repo filter. It rebuilds its report from *every* `*.jsonl` transcript under the active config dir's `projects/` folder, so on a machine where you touch a dozen projects you get one blended report about all of them. And because a config dir is per-account and per-machine, a repo you work on from two laptops (or from a personal and a work account) produces two partial reports and no whole one.

This is a ~170-line, zero-dependency script that fixes both, without patching anything:

`/insights` respects **`CLAUDE_CONFIG_DIR`**. So build a throwaway config dir containing *only* the transcripts you care about, pooled from as many sources as you like, and run `/insights` inside it.

```bash
python3 cc_insights_scope.py my_project
```

```
repo fragment : my_project
match token   : my-project
workspace     : ~/.claude-insights/my-project
sources       : ~/.claude, ~/Dropbox/cc-transcripts

pooled transcripts:
    38  ~/.claude/projects/-Users-alice-code-my-project
    52  ~/Dropbox/cc-transcripts/-Users-bob-dev-my-project

  total copied: 90   (skipped 4 duplicate session files)

======================================================================
NEXT — launch Claude Code against this scoped workspace, then /insights:

  CLAUDE_CONFIG_DIR="$HOME/.claude-insights/my-project" claude

  …then run:  /insights
======================================================================
```

*(The real output prints absolute paths; they're shown here as `~` for brevity.)*

## Install

There is nothing to install. It's one stdlib Python file.

```bash
curl -O https://raw.githubusercontent.com/andrewjpyle/cc_insights_scope/main/cc_insights_scope.py
python3 cc_insights_scope.py --help
```

Requires Python 3.9+ and Claude Code. No pip, no network calls, no config.

## Pooling across machines and accounts

A source root can be any of three shapes, and all three are accepted:

- a **config dir** (`~/.claude` — anything with a `projects/` child)
- a **`projects/` dir** itself
- a **bare folder of encoded project dirs**, which is what you get when you rsync from another machine

```bash
python3 cc_insights_scope.py my_project \
    --source ~/cc-sources/from-work-laptop \
    --source ~/cc-sources/from-desktop
```

Session filenames are globally-unique UUIDs, so pooling is a plain copy and the same session appearing in two sources is de-duplicated rather than double-counted.

To make that automatic, `contrib/launchd/` has a small router that rsyncs each repo's transcripts into per-repo folders in shared storage every 15 minutes. Install it on each machine; `cc_insights_scope.py` picks the mirror up with no `--source` flag at all.

```bash
cd contrib/launchd && ./install.sh
```

**Read `transcript_sync_excludes.txt` before you leave that running.** Every repo you work in gets copied into shared storage unless you exclude it, and a client or employer repo almost certainly must not land in your personal cloud storage. Excluded repos are printed in the log on every run, so an exclusion is visible rather than assumed.

## Why the repo argument is a fragment, not a path

Claude Code encodes a project's absolute path into its folder name, collapsing every non-alphanumeric run to a dash:

```
~/code/my_project   ->   -Users-alice-code-my-project
```

That name embeds the **username**. The same repo on a colleague's machine — or on your work laptop under a different account — encodes differently:

```
-Users-bob-dev-my-project
```

So matching on the full encoded path finds one machine's history and silently misses the other, which is the worst possible failure here: you'd get a report that looks complete and isn't. The argument is therefore normalized to a token (`my_project` → `my-project`) and matched as a **substring** of the folder name, across every source.

## Auth: run `/insights` interactively

A freshly-created `CLAUDE_CONFIG_DIR` is **not** authenticated.

Headless `claude -p "/insights"` in a new workspace reports *"Not logged in"* and still prints a report — but only the **deterministic half** of it (message counts, tool usage, languages, timings). The LLM-analyzed sections — *What You Wanted*, *Outcomes*, *Friction*, *Satisfaction* — come back **"No data"**, because the model never ran. This is the dangerous failure mode: the command exits 0 and produces output that looks like a report.

So: launch Claude Code **interactively** in the workspace and run `/insights` there. If it prompts, `/login` once — it persists in that dir.

Seeding `~/.claude.json` into the workspace does *not* fix headless auth; subscription OAuth appears to be interactive-only. On macOS the Keychain is global, so in practice you usually aren't prompted at all.

## Behavior worth knowing

- **The workspace is rebuilt from scratch every run.** Otherwise the previous repo's transcripts stay behind and quietly join the next report — and a too-large report is indistinguishable from a correct one.
- **No match is an error (exit 1), not an empty workspace.** An empty report would read as *"you did no work in that repo"* rather than *"you typed the name wrong."*
- **An empty fragment exits 2** rather than matching every folder you own.
- **A missing `--source` is a warning, not a failure** — you may legitimately be on a machine where only some sources exist.

## Claude Code skill

`contrib/claude-skill/SKILL.md` wraps this as a Claude Code skill, so you can just ask for it in natural language ("run insights for my_project across both my Macs"). Drop the folder into `~/.claude/skills/`.

## Tests

```bash
cd tests && python3 -m unittest discover -v
```

Stdlib `unittest` — no pytest, no dependencies. 14 tests.

## License

MIT

---

## Part of a larger system

`cc_insights_scope` is one of the reusable pieces pulled out of a private, autonomous build
system and released on its own — the machine needed it, so it built it, and now
it's yours too, MIT-licensed.

See the rest of the parts → **https://autonomousaj.com/parts**
