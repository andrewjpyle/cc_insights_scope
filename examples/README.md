# Demo data

SAMPLE DATA, fictional. Nothing here comes from a real Claude Code session.

Two pretend machines hold sessions for the same fictional repo, `acme_widgets`, under different
usernames, plus one unrelated repo that must stay out of the report.

| Folder | Machine | Sessions |
|---|---|---|
| `sources/laptop/projects/-opt-alice-code-acme-widgets` | laptop | 3 |
| `sources/desktop/-srv-bob-dev-acme-widgets` | desktop (bare rsync folder) | 3, one is the same session as the laptop's |
| `sources/laptop/projects/-opt-alice-code-unrelated-blog` | laptop | 1, must be excluded |

Run it from the repo root:

```bash
python3 cc_insights_scope.py acme_widgets \
    --default-source examples/sources/laptop --source examples/sources/desktop \
    --no-mirror --workspace .scope-demo
```

Expected: 5 transcripts copied, 1 duplicate skipped, the unrelated repo absent.
The committed capture of this run is `docs/assets/src/captures/demo_run.json`.
