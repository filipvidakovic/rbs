#!/usr/bin/env python3

import json
import os
import subprocess
import sys


# ── Configuration ────────────────────────────────────────────────────────────

VALID_LEVELS = {"LOW", "MEDIUM", "HIGH"}
_LEVEL_ORDER  = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

MIN_SEVERITY   = os.environ.get("OBLAK_MIN_SEVERITY",   "MEDIUM").upper()
MIN_CONFIDENCE = os.environ.get("OBLAK_MIN_CONFIDENCE", "MEDIUM").upper()

if MIN_SEVERITY not in VALID_LEVELS or MIN_CONFIDENCE not in VALID_LEVELS:
    print(
        f"[verifier] Invalid threshold configuration: "
        f"OBLAK_MIN_SEVERITY={MIN_SEVERITY}, "
        f"OBLAK_MIN_CONFIDENCE={MIN_CONFIDENCE}",
        file=sys.stderr,
    )
    sys.exit(2)


# ── Helpers ──────────────────────────────────────────────────────────────────

def severity_gte(level: str, threshold: str) -> bool:
    """Return True when *level* is at or above *threshold*."""
    return _LEVEL_ORDER.get(level, -1) >= _LEVEL_ORDER[threshold]


def validate_target(path: str) -> None:
    """
    Reject obviously invalid paths before passing them to bandit.

    Raises SystemExit(2) on failure so the caller always gets a non-zero exit.
    """
    if not path or not path.strip():
        print("[verifier] ERROR: No file path supplied.", file=sys.stderr)
        sys.exit(2)

    if not os.path.isabs(path):
        # Require absolute paths so there is no ambiguity about what is analysed.
        print(
            f"[verifier] ERROR: Path must be absolute, got: {path!r}",
            file=sys.stderr,
        )
        sys.exit(2)

    if not os.path.isfile(path):
        print(
            f"[verifier] ERROR: Target is not a regular file: {path!r}",
            file=sys.stderr,
        )
        sys.exit(2)

    if not path.endswith(".py"):
        print(
            f"[verifier] ERROR: Only .py files are accepted: {path!r}",
            file=sys.stderr,
        )
        sys.exit(2)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    if len(sys.argv) != 2:
        print(
            f"Usage: {sys.argv[0]} <absolute-path-to-script.py>",
            file=sys.stderr,
        )
        return 2

    target_path = sys.argv[1]
    validate_target(target_path)

    print(
        f"[verifier] Analysing {target_path!r} "
        f"(min_severity={MIN_SEVERITY}, min_confidence={MIN_CONFIDENCE})",
        file=sys.stderr,
    )

    # ── Run bandit ───────────────────────────────────────────────────────────
    # -f json        → machine-readable output for reliable parsing
    # -l             → report all severity levels (we filter below)
    # -i             → report all confidence levels (we filter below)
    # --quiet        → suppress progress messages to stderr
    # No shell=True – arguments are passed as a list.

    cmd = [
        sys.executable, "-m", "bandit",
        "-f", "json",
        "-l",       # include LOW severity
        "-i",       # include LOW confidence
        "--quiet",
        target_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=25,  # seconds – hard kill if bandit hangs
        )
    except FileNotFoundError:
        print(
            "[verifier] ERROR: 'bandit' executable not found. "
            "Install it with: pip install bandit",
            file=sys.stderr,
        )
        return 2
    except subprocess.TimeoutExpired:
        print("[verifier] ERROR: bandit timed out.", file=sys.stderr)
        return 2

    # bandit exits 0 = no issues found, 1 = issues found, anything else = error.
    # We parse the JSON to apply our own thresholds rather than relying on bandit's
    # exit code, which uses LOW as its baseline.
    if result.returncode not in (0, 1):
        print(
            f"[verifier] ERROR: bandit returned unexpected exit code {result.returncode}.\n"
            f"stderr: {result.stderr}",
            file=sys.stderr,
        )
        return 2

    # ── Parse JSON output ────────────────────────────────────────────────────
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(
            f"[verifier] ERROR: Could not parse bandit JSON output: {exc}\n"
            f"raw stdout: {result.stdout[:500]}",
            file=sys.stderr,
        )
        return 2

    issues = report.get("results", [])
    metrics = report.get("metrics", {}).get("_totals", {})

    print(
        f"[verifier] bandit found {len(issues)} total issue(s). "
        f"Metrics: {metrics}",
        file=sys.stderr,
    )

    # ── Apply thresholds ─────────────────────────────────────────────────────
    blocking_issues = [
        issue for issue in issues
        if severity_gte(issue.get("issue_severity", ""), MIN_SEVERITY)
        and severity_gte(issue.get("issue_confidence", ""), MIN_CONFIDENCE)
    ]

    if blocking_issues:
        print(
            f"[verifier] REJECTED – {len(blocking_issues)} blocking issue(s) "
            f"(severity>={MIN_SEVERITY}, confidence>={MIN_CONFIDENCE}):",
            file=sys.stderr,
        )
        for issue in blocking_issues:
            print(
                f"  [{issue.get('issue_severity','?')}/{issue.get('issue_confidence','?')}] "
                f"line {issue.get('line_number','?')}: "
                f"{issue.get('issue_text','(no description)')} "
                f"[{issue.get('test_id','?')}]",
                file=sys.stderr,
            )
        return 1  # REJECTED

    print("[verifier] ACCEPTED – no blocking issues found.", file=sys.stderr)
    return 0  # SAFE


if __name__ == "__main__":
    sys.exit(main())
