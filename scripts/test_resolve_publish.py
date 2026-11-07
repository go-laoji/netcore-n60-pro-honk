#!/usr/bin/env python3
"""Publication source checks with paginated API fixtures; no builds or writes."""

import copy
import unittest

import resolve_publish


class PublicationSourceTests(unittest.TestCase):
    def setUp(self):
        self.repository = "owner/repo"
        self.run_id = 123
        self.commit = "a" * 40
        self.run = {
            "id": 123, "status": "completed", "conclusion": "failure",
            "path": resolve_publish.WORKFLOW, "event": "push", "run_attempt": 2,
            "head_sha": self.commit, "repository": {"id": 1, "full_name": self.repository},
            "head_repository": {"id": 1, "full_name": self.repository},
        }
        self.build = {
            "id": 10, "name": "build", "run_id": 123, "head_sha": self.commit,
            "status": "completed", "conclusion": "success",
            "steps": [{"name": name, "conclusion": "success"} for name in resolve_publish.REQUIRED_STEPS],
        }
        self.artifact = {
            "id": 20, "name": "netcore-n60-pro-honk-go-laoji-11-07-123-2",
            "expired": False, "size_in_bytes": 100,
            "workflow_run": {"id": 123, "head_sha": self.commit,
                             "repository_id": 1, "head_repository_id": 1},
        }
        self.jobs = [{"jobs": [self.build]}]
        self.artifacts = [{"artifacts": [self.artifact]}]
        self.calls = []
        self.recheck = None

    def api(self, endpoint, paginate=False):
        self.calls.append((endpoint, paginate))
        if "/jobs?" in endpoint:
            return copy.deepcopy(self.jobs)
        if "/artifacts?" in endpoint:
            return copy.deepcopy(self.artifacts)
        if self.recheck is not None and len(self.calls) > 1:
            return copy.deepcopy(self.recheck)
        return copy.deepcopy(self.run)

    def resolve(self):
        return resolve_publish.resolve_source(self.repository, self.run_id, self.api)

    def test_failed_overall_run_with_verified_build_can_be_published(self):
        self.assertEqual(self.resolve(), {"artifact_id": 20, "source_run_id": 123,
                                         "source_attempt": 2, "target_sha": self.commit})
        self.assertIn(("repos/owner/repo/actions/runs/123/attempts/2/jobs?per_page=100", True), self.calls)

    def test_successful_overall_run_remains_supported(self):
        self.run["conclusion"] = "success"
        self.assertEqual(self.resolve()["artifact_id"], 20)

    def test_failed_or_skipped_build_is_rejected(self):
        for conclusion in ("failure", "skipped", "cancelled"):
            with self.subTest(conclusion=conclusion):
                self.build["conclusion"] = conclusion
                with self.assertRaisesRegex(ValueError, "build job must succeed"):
                    self.resolve()

    def test_missing_or_failed_verification_step_is_rejected(self):
        self.build["steps"][-1]["conclusion"] = "skipped"
        with self.assertRaisesRegex(ValueError, "verification step must succeed"):
            self.resolve()
        self.build["steps"] = []
        with self.assertRaisesRegex(ValueError, "verification step must succeed"):
            self.resolve()

    def test_wrong_workflow_fork_event_or_running_source_is_rejected(self):
        original = copy.deepcopy(self.run)
        cases = ({"path": ".github/workflows/other.yml"},
                 {"head_repository": {"full_name": "fork/repo"}},
                 {"event": "pull_request"}, {"status": "in_progress"})
        for changes in cases:
            with self.subTest(changes=changes):
                self.run = {**copy.deepcopy(original), **changes}
                with self.assertRaises(ValueError):
                    self.resolve()

    def test_expired_old_attempt_or_duplicate_artifact_is_rejected(self):
        self.artifact["expired"] = True
        with self.assertRaisesRegex(ValueError, "exactly one unexpired"):
            self.resolve()
        self.artifact["expired"] = False
        self.artifact["name"] = self.artifact["name"].removesuffix("-2") + "-1"
        with self.assertRaisesRegex(ValueError, "latest attempt"):
            self.resolve()
        self.artifact["name"] = self.artifact["name"].removesuffix("-1") + "-2"
        self.artifacts[0]["artifacts"].append({**self.artifact, "id": 21})
        with self.assertRaisesRegex(ValueError, "exactly one unexpired"):
            self.resolve()

    def test_artifact_from_other_commit_or_repository_is_rejected(self):
        for key, value in (("head_sha", "b" * 40), ("id", 999), ("repository_id", 999),
                           ("head_repository_id", 999)):
            original = self.artifact["workflow_run"][key]
            with self.subTest(key=key):
                self.artifact["workflow_run"][key] = value
                with self.assertRaisesRegex(ValueError, "does not match"):
                    self.resolve()
            self.artifact["workflow_run"][key] = original

    def test_pagination_is_read_and_duplicate_page_entries_are_deduplicated(self):
        self.jobs.insert(0, {"jobs": [{**self.build, "id": 11, "name": "publish"}]})
        self.artifacts.insert(0, {"artifacts": [{**self.artifact, "id": 21, "name": "build-logs"}]})
        self.artifacts.append(copy.deepcopy(self.artifacts[-1]))
        self.assertEqual(self.resolve()["artifact_id"], 20)

    def test_latest_attempt_with_skipped_build_cannot_reuse_older_build(self):
        self.jobs = [{"jobs": [{**self.build, "conclusion": "skipped"}]}]
        with self.assertRaisesRegex(ValueError, "build job must succeed"):
            self.resolve()

    def test_rerun_started_during_resolution_is_rejected(self):
        self.recheck = {**self.run, "run_attempt": 3, "status": "in_progress"}
        with self.assertRaisesRegex(ValueError, "Source run changed"):
            self.resolve()

    def test_invalid_run_ids_fail_before_requesting_api(self):
        for value in ("", "0", "-1", "1/attempts/1", "123\n"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "positive run ID"):
                resolve_publish.resolve_source(self.repository, value, self.api)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
