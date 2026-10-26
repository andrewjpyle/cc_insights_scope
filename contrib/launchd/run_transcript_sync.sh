#!/usr/bin/env bash
# Per-repo Claude Code transcript router → shared storage.
#
# For each project folder under ~/.claude/projects/, rsync its *.jsonl session
# transcripts into a per-repo folder in shared storage:
#
#   $MIRROR_ROOT/cc-transcripts/<encoded-project-folder>/*.jsonl
#
# The encoded folder name (e.g. -Users-alice-code-my-project) IS the repo key.
# Several machines sync into the same per-repo folder; session filenames are
# globally-unique UUIDs, so this is a union with no clobber. We never pass
# --delete: the mirror is an additive archive, and a machine that goes offline
# must not cause its history to be reaped from the mirror.
#
# cc_insights_scope.py reads $MIRROR_ROOT/cc-transcripts as a source, which is
# what makes cross-machine / cross-account /insights reports possible.
#
# Pure rsync. No secrets. A machine with no mirror folder no-ops cleanly.
#
# SCOPE / CONFIDENTIALITY: edit transcript_sync_excludes.txt (one substring per
# line) to keep a repo's transcripts OUT of shared storage - e.g. a client or
# employer repo you must not copy into personal cloud storage. Excluded repos
# are named in the log, so an exclusion is never silent.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXCLUDES_FILE="$SCRIPT_DIR/transcript_sync_excludes.txt"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

ts() { date +'%Y-%m-%d %H:%M:%S %Z'; }

SRC="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"

# Resolve the mirror root. MIRROR_ROOT wins if set (put it in the plist); other-
# wise probe the classic and the modern macOS CloudStorage Dropbox paths.
resolve_mirror() {
    if [[ -n "${MIRROR_ROOT:-}" && -d "${MIRROR_ROOT}" ]]; then
        printf '%s' "$MIRROR_ROOT"; return 0
    fi
    for p in "$HOME/Dropbox" "$HOME/Library/CloudStorage/Dropbox"; do
        [[ -d "$p" ]] && { printf '%s' "$p"; return 0; }
    done
    return 1
}

echo "[$(ts)] cc-transcript-sync: starting (src=$SRC)"

if [[ ! -d "$SRC" ]]; then
    echo "[$(ts)] no $SRC on this host - nothing to sync"; exit 0
fi

MIRROR="$(resolve_mirror)" || {
    echo "[$(ts)] no mirror folder found - skipping (set MIRROR_ROOT to override)"; exit 0
}
DEST_BASE="$MIRROR/cc-transcripts"
mkdir -p "$DEST_BASE"

# Load exclude substrings (skip blanks + comments).
excludes=()
if [[ -f "$EXCLUDES_FILE" ]]; then
    while IFS= read -r line; do
        line="${line%%#*}"; line="$(echo "$line" | xargs)"  # strip comment + trim
        [[ -n "$line" ]] && excludes+=("$line")
    done < "$EXCLUDES_FILE"
fi

synced_repos=0 synced_files=0 skipped_repos=0
for dir in "$SRC"/*/; do
    [[ -d "$dir" ]] || continue
    name="$(basename "$dir")"

    # Only consider folders that actually hold transcripts.
    shopt -s nullglob
    jsonls=("$dir"*.jsonl)
    shopt -u nullglob
    [[ ${#jsonls[@]} -gt 0 ]] || continue

    excluded=0
    for ex in "${excludes[@]}"; do
        case "$name" in *"$ex"*) excluded=1; break;; esac
    done
    if [[ $excluded -eq 1 ]]; then
        echo "[$(ts)]   excluded: $name"
        skipped_repos=$((skipped_repos + 1))
        continue
    fi

    dest="$DEST_BASE/$name"
    mkdir -p "$dest"
    rsync -a --include='*.jsonl' --exclude='*' "$dir" "$dest/" >/dev/null 2>&1
    synced_repos=$((synced_repos + 1))
    synced_files=$((synced_files + ${#jsonls[@]}))
done

echo "[$(ts)] cc-transcript-sync: done - $synced_repos repo(s), ~$synced_files transcript file(s), $skipped_repos excluded → $DEST_BASE"
exit 0
