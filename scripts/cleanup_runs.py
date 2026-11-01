#!/usr/bin/env python3
"""Retain recent Actions runs; preview by default, delete only with --apply."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def gh_api(endpoint, method="GET", paginate=False):
    command = ["gh", "api", "--method", method, endpoint]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def list_runs(repository):
    pages = gh_api(f"repos/{repository}/actions/runs?per_page=100", paginate=True)
    return [run for page in pages for run in page["workflow_runs"]]


def plan_cleanup(runs, keep=10, current_run_id=None):
    if keep < 0:
        raise ValueError("Retention count cannot be negative")
    # An inserted run can shift page boundaries; deduplicate before ranking.
    unique = {run["id"]: run for run in runs}
    for run in unique.values():
        if type(run["id"]) is not int or run["id"] <= 0:
            raise ValueError("Invalid workflow run ID")
    ordered = sorted(unique.values(), key=lambda run: (
        datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")), run["id"]
    ), reverse=True)
    older = ordered[keep:]
    return {
        "total": len(ordered),
        "keep": keep,
        "retained": [run["id"] for run in ordered[:keep]],
        "candidates": [run["id"] for run in older
                       if run["status"] == "completed" and run["id"] != current_run_id],
        "protected": [run["id"] for run in older
                      if run["status"] != "completed" or run["id"] == current_run_id],
    }


def cleanup(repository, keep=10, apply=False, current_run_id=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    if keep < 0:
        raise ValueError("Retention count cannot be negative")
    plan = plan_cleanup(list_runs(repository), keep, current_run_id)
    result = {"repository": repository, "applied": apply, **plan,
              "deleted": [], "skipped_after_recheck": []}
    if apply:
        for run_id in plan["candidates"]:
            endpoint = f"repos/{repository}/actions/runs/{run_id}"
            # A completed run may have been re-run since the initial listing.
            run = gh_api(endpoint)
            if run["id"] != run_id:
                raise ValueError("Workflow run ID changed during recheck")
            if run["status"] != "completed":
                result["skipped_after_recheck"].append(run_id)
                continue
            gh_api(endpoint, method="DELETE")
            result["deleted"].append(run_id)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--keep", type=int, default=10, help="Recent runs to retain (default: 10)")
    parser.add_argument("--current-run-id", type=int, default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--apply", action="store_true", help="Delete completed runs outside retention")
    args = parser.parse_args()
    try:
        result = cleanup(args.repository, args.keep, args.apply, args.current_run_id)
        print(json.dumps(result, indent=2))
        if args.apply and os.environ.get("GITHUB_STEP_SUMMARY"):
            skipped = len(result["protected"]) + len(result["skipped_after_recheck"])
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
                summary.write(
                    f"### Actions 历史记录清理\n\n"
                    f"保留最近 {args.keep} 次运行；删除 {len(result['deleted'])} 次已完成运行；"
                    f"额外保护 {skipped} 次当前或未完成运行。\n"
                )
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        print(f"Workflow cleanup failed: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
