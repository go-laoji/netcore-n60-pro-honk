#!/usr/bin/env python3
"""Resolve verified firmware from a completed run, even when its publication failed."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from cleanup_runs import gh_api
from validate import require


WORKFLOW = ".github/workflows/build-honk.yml"
REQUIRED_STEPS = (
    "Compile firmware", "Verify actual kernel and installed packages",
    "Verify version embedded in the firmware rootfs", "Collect N60 Pro firmware",
    "Upload verified firmware",
)


def resolve_source(repository, run_id, api=gh_api):
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository), "Invalid repository")
    require(re.fullmatch(r"[1-9][0-9]*", str(run_id)), "publish_run_id must be a positive run ID")
    run_id = int(run_id)
    endpoint = f"repos/{repository}/actions/runs/{run_id}"
    run = api(endpoint)
    require(run["id"] == run_id and run["status"] == "completed", "Source run must be completed")
    require(run["path"] == WORKFLOW, "Unexpected source workflow")
    require(run["repository"]["full_name"].lower() == repository.lower() and
            (run.get("head_repository") or {}).get("full_name", "").lower() == repository.lower(),
            "Source run must build this repository, not a fork")
    require(run["event"] in ("push", "schedule", "workflow_dispatch"), "Unexpected source event")
    attempt = run["run_attempt"]
    require(type(attempt) is int and attempt > 0, "Invalid source run attempt")
    target = run["head_sha"]
    require(re.fullmatch(r"[0-9a-f]{40}", target), "Invalid source commit")

    pages = api(f"{endpoint}/attempts/{attempt}/jobs?per_page=100", paginate=True)
    jobs = {job["id"]: job for page in pages for job in page["jobs"]}
    builds = [job for job in jobs.values() if job["name"] == "build"]
    require(len(builds) == 1, "Expected exactly one build job in the latest source attempt")
    build = builds[0]
    require(build["run_id"] == run_id and build["head_sha"] == target,
            "Source build does not match the run commit")
    require(build["status"] == "completed" and build["conclusion"] == "success",
            "Source build job must succeed")
    steps = {step["name"]: step for step in build["steps"]}
    for name in REQUIRED_STEPS:
        require(steps.get(name, {}).get("conclusion") == "success",
                f"Source build verification step must succeed: {name}")

    pages = api(f"{endpoint}/artifacts?per_page=100", paginate=True)
    artifacts = {artifact["id"]: artifact for page in pages for artifact in page["artifacts"]}
    suffix = f"-{run_id}-{attempt}"
    candidates = [artifact for artifact in artifacts.values()
                  if artifact["name"].startswith("netcore-n60-pro-honk-")
                  and artifact["name"].endswith(suffix) and artifact["expired"] is False]
    require(len(candidates) == 1, "Expected exactly one unexpired firmware artifact for the latest attempt")
    artifact = candidates[0]
    require(type(artifact["id"]) is int and artifact["id"] > 0 and artifact["size_in_bytes"] > 0,
            "Invalid firmware artifact")
    source = artifact["workflow_run"]
    require(source["id"] == run_id and source["head_sha"] == target and
            source["repository_id"] == run["repository"]["id"] and
            source["head_repository_id"] == run["repository"]["id"],
            "Firmware artifact does not match the source run and commit")
    # A rerun may start while pages are being read; never mix attempts.
    current = api(endpoint)
    require(current["status"] == "completed" and current["run_attempt"] == attempt and
            current["head_sha"] == target, "Source run changed while resolving its artifact")
    return {"artifact_id": artifact["id"], "source_run_id": run_id,
            "source_attempt": attempt, "target_sha": target}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        source = resolve_source(args.repository, args.run_id)
        if args.github_output is not None:
            with args.github_output.open("a") as stream:
                for key, value in source.items():
                    stream.write(f"{key}={value}\n")
        print(json.dumps(source, indent=2))
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        print(f"Publication source resolution failed: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
