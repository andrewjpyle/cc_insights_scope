"""Tests for cc_insights_scope.

Stdlib `unittest` only - the whole point of this package is that it has no
dependencies, and a test suite that needs pytest would quietly undo that.

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cc_insights_scope as cis  # noqa: E402


def _mkproject(projects_dir: Path, encoded_name: str, session_ids: list[str]) -> Path:
    """Create one encoded project folder holding N session transcripts."""
    folder = projects_dir / encoded_name
    folder.mkdir(parents=True)
    for sid in session_ids:
        (folder / f"{sid}.jsonl").write_text(f'{{"sessionId":"{sid}"}}\n')
    return folder


class EncodeToken(unittest.TestCase):
    def test_collapses_non_alphanumeric_runs_to_a_single_dash(self):
        self.assertEqual(cis.encode_token("my_project"), "my-project")
        self.assertEqual(cis.encode_token("My.Project"), "my-project")
        self.assertEqual(cis.encode_token("a/b//c"), "a-b-c")
        self.assertEqual(cis.encode_token("spaces  here"), "spaces-here")

    def test_strips_leading_and_trailing_separators(self):
        self.assertEqual(cis.encode_token("/my_project/"), "my-project")
        self.assertEqual(cis.encode_token("__x__"), "x")

    def test_empty_after_normalization_is_empty(self):
        # main() turns this into exit code 2 rather than matching every folder.
        self.assertEqual(cis.encode_token("///"), "")
        self.assertEqual(cis.encode_token(""), "")


class CandidateProjectsDirs(unittest.TestCase):
    def test_accepts_a_config_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "projects").mkdir()
            self.assertEqual(cis.candidate_projects_dirs(root), [root / "projects"])

    def test_accepts_a_projects_dir_itself(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "projects"
            root.mkdir()
            self.assertEqual(cis.candidate_projects_dirs(root), [root])

    def test_accepts_a_bare_folder_of_encoded_project_dirs(self):
        # This is the rsynced-from-another-machine shape: no `projects/` wrapper,
        # just the encoded dirs, which all start with '-'.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "-Users-someone-code-my-project").mkdir()
            self.assertEqual(cis.candidate_projects_dirs(root), [root])

    def test_a_config_dir_that_is_also_named_projects_is_not_returned_twice(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "projects"
            (root / "projects").mkdir(parents=True)
            self.assertEqual(len(cis.candidate_projects_dirs(root)), 2)
            # ...and the two are genuinely different dirs, not one dir twice.
            self.assertEqual(
                len({p.resolve() for p in cis.candidate_projects_dirs(root)}), 2
            )


class FindMatchingFolders(unittest.TestCase):
    def test_matches_on_substring_not_exact_path(self):
        """The whole reason this is a substring match: the same repo, checked out
        on two machines under two different usernames, encodes to two different
        folder names. An exact match would find one and silently miss the other."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = root / "mac_a" / "projects"
            b = root / "mac_b" / "projects"
            _mkproject(a, "-Users-alice-code-my-project", ["s1"])
            _mkproject(b, "-Users-bob-dev-my-project", ["s2"])
            _mkproject(a, "-Users-alice-code-other-repo", ["s3"])

            found = cis.find_matching_folders([a, b], "my-project")
            names = sorted(p.name for p in found)
            self.assertEqual(
                names, ["-Users-alice-code-my-project", "-Users-bob-dev-my-project"]
            )
            self.assertNotIn("-Users-alice-code-other-repo", names)

    def test_a_missing_source_warns_and_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "projects"
            _mkproject(real, "-x-my-project", ["s1"])
            missing = root / "does_not_exist"

            err = io.StringIO()
            stderr, sys.stderr = sys.stderr, err
            try:
                found = cis.find_matching_folders([missing, real], "my-project")
            finally:
                sys.stderr = stderr

            self.assertEqual(len(found), 1)
            self.assertIn("source not found", err.getvalue())

    def test_no_match_returns_empty_rather_than_everything(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "projects"
            _mkproject(p, "-x-some-repo", ["s1"])
            self.assertEqual(cis.find_matching_folders([p], "nonexistent"), [])


class MainEndToEnd(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cis.main(argv)
        return rc, buf.getvalue()

    def test_pools_across_sources_and_dedupes_identical_session_ids(self):
        """The same session, synced from two places, must land once. Session
        filenames are globally-unique UUIDs, so a collision means the same
        session - copying it twice would double-count it in the report."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = root / "mac_a" / "projects"
            b = root / "mac_b" / "projects"
            _mkproject(a, "-Users-alice-my-project", ["s1", "shared"])
            _mkproject(b, "-Users-bob-my-project", ["s2", "shared"])
            ws = root / "ws"

            rc, out = self._run([
                "my_project", "--default-source", "",
                "--no-mirror",
                "--source", str(a), "--source", str(b),
                "--workspace", str(ws),
            ])

            self.assertEqual(rc, 0)
            pooled = sorted(
                p.name for p in (ws / "projects" / "insights-scope-my-project").glob("*.jsonl")
            )
            self.assertEqual(pooled, ["s1.jsonl", "s2.jsonl", "shared.jsonl"])
            self.assertIn("skipped 1 duplicate session files", out)

    def test_workspace_is_rebuilt_so_a_previous_repo_cannot_leak_in(self):
        """A stale transcript from a prior run would silently inflate the next
        report, and a too-large report looks exactly like a correct one."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "projects"
            _mkproject(src, "-x-my-project", ["s1"])
            ws = root / "ws"

            stale = ws / "projects" / "insights-scope-old-repo"
            stale.mkdir(parents=True)
            (stale / "leftover.jsonl").write_text("{}\n")

            rc, _ = self._run([
                "my_project", "--default-source", "", "--no-mirror",
                "--source", str(src), "--workspace", str(ws),
            ])

            self.assertEqual(rc, 0)
            self.assertFalse(stale.exists(), "the previous repo's scope dir survived")
            remaining = sorted(p.name for p in (ws / "projects").rglob("*.jsonl"))
            self.assertEqual(remaining, ["s1.jsonl"])

    def test_no_match_exits_nonzero_rather_than_building_an_empty_workspace(self):
        """An empty report is not a finding. Silence here would read as
        'you did no work in that repo' rather than 'the name was wrong'."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "projects"
            _mkproject(src, "-x-some-repo", ["s1"])
            ws = root / "ws"

            err = io.StringIO()
            stderr, sys.stderr = sys.stderr, err
            try:
                rc, _ = self._run([
                    "typo_repo", "--default-source", "", "--no-mirror",
                    "--source", str(src), "--workspace", str(ws),
                ])
            finally:
                sys.stderr = stderr

            self.assertEqual(rc, 1)
            self.assertIn("no project folders matched", err.getvalue())
            self.assertFalse((ws / "projects").exists())

    def test_empty_fragment_exits_2_rather_than_matching_every_repo(self):
        err = io.StringIO()
        stderr, sys.stderr = sys.stderr, err
        try:
            rc, _ = self._run(["///", "--default-source", "", "--no-mirror"])
        finally:
            sys.stderr = stderr
        self.assertEqual(rc, 2)
        self.assertIn("empty after normalization", err.getvalue())


    def _run_err(self, argv):
        err = io.StringIO()
        stderr, sys.stderr = sys.stderr, err
        try:
            rc, _ = self._run(argv)
        finally:
            sys.stderr = stderr
        return rc, err.getvalue()

    def test_refuses_a_workspace_that_would_delete_a_source(self):
        """--workspace pointing at a source config dir used to rmtree the
        user's real transcripts and exit 0 with an empty workspace."""
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "cfg"
            _mkproject(cfg / "projects", "-opt-a-demo-app", ["s1"])
            rc, err = self._run_err([
                "demo_app", "--default-source", str(cfg), "--no-mirror",
                "--workspace", str(cfg),
            ])
            self.assertEqual(rc, 2)
            self.assertIn("is a source", err)
            self.assertTrue((cfg / "projects" / "-opt-a-demo-app" / "s1.jsonl").exists())

    def test_refuses_when_a_matched_folder_lives_inside_the_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            nested = ws / "projects" / "stash"
            _mkproject(nested, "-opt-a-demo-app", ["s1"])
            rc, err = self._run_err([
                "demo_app", "--default-source", "", "--no-mirror",
                "--source", str(nested), "--workspace", str(ws),
            ])
            self.assertEqual(rc, 2)
            self.assertIn("inside the workspace", err)
            self.assertTrue((nested / "-opt-a-demo-app" / "s1.jsonl").exists())

    def test_matched_folders_with_no_transcripts_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "projects" / "-opt-b-demo-app").mkdir(parents=True)
            rc, err = self._run_err([
                "demo_app", "--default-source", str(root), "--no-mirror",
                "--workspace", str(root / "ws"),
            ])
            self.assertEqual(rc, 1)
            self.assertIn("held no *.jsonl", err)
            self.assertFalse((root / "ws" / "projects").exists())


    def test_committed_demo_sources_pool_five_sessions_and_skip_one_duplicate(self):
        """The README demo: fictional sources in examples/ must keep producing
        the documented result (5 copied, 1 duplicate skipped, no unrelated repo)."""
        ex = Path(__file__).resolve().parent.parent / "examples" / "sources"
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "ws"
            rc, out = self._run([
                "acme_widgets", "--default-source", str(ex / "laptop"),
                "--source", str(ex / "desktop"), "--no-mirror", "--workspace", str(ws),
            ])
            self.assertEqual(rc, 0)
            self.assertIn("total copied: 5", out)
            self.assertIn("skipped 1 duplicate", out)
            names = [p.name for p in (ws / "projects" / "insights-scope-acme-widgets").glob("*.jsonl")]
            self.assertEqual(len(names), 5)
            self.assertNotIn("unrelated", out)


if __name__ == "__main__":
    unittest.main()
