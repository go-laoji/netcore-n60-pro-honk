#!/usr/bin/env python3
"""Actions retention checks, including pagination and re-run races."""

from datetime import datetime, timedelta, timezone
import subprocess
import unittest
from unittest.mock import patch

import cleanup_runs


def run(number, status="completed"):
    return {
        "id": number,
        "created_at": (datetime(2026, 10, 31, tzinfo=timezone.utc) +
                       timedelta(minutes=number)).isoformat(),
        "status": status,
        "conclusion": ("success", "failure", "cancelled")[number % 3],
        "head_branch": ("develop", "feature/example")[number % 2],
    }


class CleanupRunsTests(unittest.TestCase):
    def test_creation_time_then_id_determine_latest_not_input_order(self):
        old_high_id = {**run(99), "created_at": run(1)["created_at"]}
        tied = {**run(5), "created_at": run(4)["created_at"]}
        plan = cleanup_runs.plan_cleanup([run(3), old_high_id, run(4), tied], keep=2)
        self.assertEqual(plan["retained"], [5, 4])
        self.assertEqual(plan["candidates"], [3, 99])

    def test_fewer_than_ten_runs_are_all_retained(self):
        plan = cleanup_runs.plan_cleanup([run(i) for i in range(1, 10)])
        self.assertEqual(plan["retained"], list(range(9, 0, -1)))
        self.assertEqual(plan["candidates"], [])

    def test_only_completed_older_runs_are_deleted_across_all_pages(self):
        runs = [run(i) for i in range(1, 124)]
        deleted = []

        def api(endpoint, method="GET", paginate=False):
            if paginate:
                # Include a shifted page-boundary duplicate.
                return [{"workflow_runs": runs[:100]}, {"workflow_runs": runs[99:]}]
            number = int(endpoint.rsplit("/", 1)[1])
            if method == "DELETE":
                deleted.append(number)
                return None
            return run(number)

        with patch("cleanup_runs.gh_api", side_effect=api) as mocked:
            result = cleanup_runs.cleanup("owner/repo", apply=True)
        self.assertEqual(result["total"], 123)
        self.assertEqual(result["retained"], list(range(123, 113, -1)))
        self.assertEqual(deleted, list(range(113, 0, -1)))
        self.assertEqual(result["deleted"], deleted)
        self.assertTrue(mocked.call_args_list[0].kwargs["paginate"])

    def test_preview_never_sends_delete_requests(self):
        with patch("cleanup_runs.gh_api", return_value=[{
            "workflow_runs": [run(i) for i in range(1, 14)]
        }]) as api:
            result = cleanup_runs.cleanup("owner/repo")
        api.assert_called_once()
        self.assertEqual(result["candidates"], [3, 2, 1])
        self.assertEqual(result["deleted"], [])
        self.assertFalse(result["applied"])

    def test_current_and_unfinished_runs_are_protected_even_outside_latest_ten(self):
        runs = [run(i) for i in range(1, 15)] + [run(15, "in_progress")]
        runs[0] = run(1, "queued")
        plan = cleanup_runs.plan_cleanup(runs, current_run_id=2)
        self.assertEqual(plan["retained"], list(range(15, 5, -1)))
        self.assertEqual(plan["candidates"], [5, 4, 3])
        self.assertEqual(plan["protected"], [2, 1])

    def test_restarted_candidate_is_skipped_before_deletion(self):
        with patch("cleanup_runs.gh_api", side_effect=[
            [{"workflow_runs": [run(1), run(2)]}], run(1, "in_progress"),
        ]) as api:
            result = cleanup_runs.cleanup("owner/repo", keep=1, apply=True)
        self.assertEqual(api.call_count, 2)
        self.assertEqual(result["deleted"], [])
        self.assertEqual(result["skipped_after_recheck"], [1])

    def test_explicit_zero_retention_clears_completed_history_but_keeps_active_run(self):
        plan = cleanup_runs.plan_cleanup([run(1), run(2, "in_progress"), run(3)], keep=0)
        self.assertEqual(plan["retained"], [])
        self.assertEqual(plan["candidates"], [3, 1])
        self.assertEqual(plan["protected"], [2])

    def test_invalid_scope_is_rejected_before_api_calls(self):
        with patch("cleanup_runs.gh_api") as api:
            for repository, keep in (("owner/repo/other", 10), ("owner/repo", -1)):
                with self.subTest(repository=repository, keep=keep), self.assertRaises(ValueError):
                    cleanup_runs.cleanup(repository, keep=keep, apply=True)
        api.assert_not_called()

    def test_api_failure_stops_cleanup_without_deleting_unchecked_runs(self):
        with patch("cleanup_runs.gh_api", side_effect=[
            [{"workflow_runs": [run(1), run(2), run(3)]}],
            subprocess.CalledProcessError(1, ["gh"], stderr="permission denied"),
        ]) as api:
            with self.assertRaises(subprocess.CalledProcessError):
                cleanup_runs.cleanup("owner/repo", keep=1, apply=True)
        self.assertEqual(api.call_count, 2)


if __name__ == "__main__":
    unittest.main()
