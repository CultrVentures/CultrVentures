#!/usr/bin/env python3
"""
Grounding Validator Script
Validates that vault .md files produced by agents have proper grounding metadata.

Usage:
    python validate-grounding.py <file_or_directory>
    python validate-grounding.py --all          # Validate entire vault
    python validate-grounding.py --report       # Generate validation report

Checks:
    1. YAML frontmatter exists with required fields
    2. Source references are non-empty and formatted correctly
    3. Confidence scores are within valid range
    4. Grounding status is a valid enum value
    5. Inline source citations exist for factual claims
    6. Assumption fencing is properly formatted
    7. Freshness windows are respected
"""

import sys
import os
import re
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional


# --- Configuration ---

REQUIRED_FRONTMATTER = [
    "agent", "skill", "timestamp", "source_type",
    "source_ref", "confidence", "grounding_status", "review_status"
]

VALID_SOURCE_TYPES = [
    "api_response", "vault_file", "web_search", "computation", "human_input"
]

VALID_GROUNDING_STATUS = ["verified", "derived", "assumption"]

VALID_REVIEW_STATUS = ["pending", "approved", "rejected", "flagged"]

FRESHNESS_WINDOWS = {
    "stripe": timedelta(hours=1),
    "supabase": timedelta(hours=1),
    "posthog": timedelta(hours=24),
    "google_analytics": timedelta(hours=24),
    "plausible": timedelta(hours=24),
    "ahrefs": timedelta(days=7),
    "dataforseo": timedelta(days=7),
    "serpapi": timedelta(days=7),
    "similarweb": timedelta(days=7),
    "lighthouse": timedelta(hours=0),  # Real-time, always fresh
}

# Patterns that likely indicate factual claims needing sources
FACTUAL_PATTERNS = [
    r'\d+%',                          # Percentages
    r'\$[\d,]+',                      # Dollar amounts
    r'\d{1,3}(,\d{3})+',             # Large numbers with commas
    r'increased|decreased|grew|dropped|rose|fell',  # Trend claims
    r'ranked? #?\d+',                 # Rankings
    r'according to|based on|data shows',  # Attribution phrases (good)
]

SOURCE_CITATION_PATTERN = r'\[source:\s*[^\]]+\]'
ASSUMPTION_FENCE_PATTERN = r'⚠️|## Assumptions|> ⚠️'


@dataclass
class ValidationResult:
    file_path: str
    passed: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def parse_frontmatter(content: str) -> tuple[Optional[dict], str]:
    """Extract YAML frontmatter and body from markdown file."""
    if not content.startswith("---"):
        return None, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    try:
        fm = yaml.safe_load(parts[1])
        body = parts[2]
        return fm, body
    except yaml.YAMLError:
        return None, content


def validate_frontmatter(fm: Optional[dict], result: ValidationResult) -> None:
    """Validate YAML frontmatter has all required fields with valid values."""
    if fm is None:
        result.passed = False
        result.errors.append("STAGE 1 FAIL: No YAML frontmatter found")
        return

    # Check required fields
    for field_name in REQUIRED_FRONTMATTER:
        if field_name not in fm:
            result.passed = False
            result.errors.append(f"STAGE 1 FAIL: Missing required field: {field_name}")

    # Validate source_type
    if "source_type" in fm and fm["source_type"] not in VALID_SOURCE_TYPES:
        result.passed = False
        result.errors.append(
            f"STAGE 1 FAIL: Invalid source_type: {fm['source_type']}. "
            f"Must be one of: {VALID_SOURCE_TYPES}"
        )

    # Validate grounding_status
    if "grounding_status" in fm and fm["grounding_status"] not in VALID_GROUNDING_STATUS:
        result.passed = False
        result.errors.append(
            f"STAGE 1 FAIL: Invalid grounding_status: {fm['grounding_status']}. "
            f"Must be one of: {VALID_GROUNDING_STATUS}"
        )

    # Validate review_status
    if "review_status" in fm and fm["review_status"] not in VALID_REVIEW_STATUS:
        result.passed = False
        result.errors.append(
            f"STAGE 1 FAIL: Invalid review_status: {fm['review_status']}. "
            f"Must be one of: {VALID_REVIEW_STATUS}"
        )

    # Validate confidence range
    if "confidence" in fm:
        conf = fm["confidence"]
        if not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
            result.passed = False
            result.errors.append(
                f"STAGE 1 FAIL: confidence must be 0.0-1.0, got: {conf}"
            )

    # Validate source_ref is non-empty
    if "source_ref" in fm and (not fm["source_ref"] or str(fm["source_ref"]).strip() == ""):
        result.passed = False
        result.errors.append("STAGE 1 FAIL: source_ref is empty")

    # Validate timestamp format
    if "timestamp" in fm:
        ts = str(fm["timestamp"])
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            result.warnings.append(f"STAGE 1 WARN: timestamp not valid ISO-8601: {ts}")


def validate_source_attribution(body: str, result: ValidationResult) -> None:
    """Check that factual claims have inline source citations."""
    lines = body.split("\n")
    total_claims = 0
    sourced_claims = 0
    unsourced_claims = []
    in_assumption_fence = False

    for i, line in enumerate(lines, 1):
        # Track assumption fencing
        if re.search(ASSUMPTION_FENCE_PATTERN, line):
            in_assumption_fence = True
            continue
        if in_assumption_fence and line.strip() == "" and not line.startswith(">"):
            in_assumption_fence = False

        # Skip headings, empty lines, code blocks, metadata
        if (line.strip().startswith("#") or line.strip() == "" or
                line.strip().startswith("```") or line.strip().startswith("|") or
                line.strip().startswith("---") or line.strip().startswith(">")):
            continue

        # Check if this line contains factual claims
        has_factual = any(re.search(p, line, re.IGNORECASE) for p in FACTUAL_PATTERNS)

        if has_factual and not in_assumption_fence:
            total_claims += 1
            if re.search(SOURCE_CITATION_PATTERN, line) or re.search(SOURCE_CITATION_PATTERN, lines[min(i, len(lines)-1)] if i < len(lines) else ""):
                sourced_claims += 1
            else:
                unsourced_claims.append((i, line.strip()[:80]))

    result.stats["total_factual_claims"] = total_claims
    result.stats["sourced_claims"] = sourced_claims
    result.stats["unsourced_claims"] = len(unsourced_claims)

    if unsourced_claims:
        for line_num, claim in unsourced_claims:
            result.warnings.append(
                f"STAGE 2 WARN: Potential unsourced claim on line {line_num}: \"{claim}...\""
            )
        if len(unsourced_claims) > total_claims * 0.3:  # >30% unsourced
            result.passed = False
            result.errors.append(
                f"STAGE 2 FAIL: {len(unsourced_claims)}/{total_claims} factual claims lack sources"
            )


def validate_freshness(fm: Optional[dict], result: ValidationResult) -> None:
    """Check if source data is within freshness windows."""
    if fm is None or "source_ref" not in fm or "timestamp" not in fm:
        return

    source_ref = str(fm["source_ref"]).lower()
    try:
        ts = datetime.fromisoformat(str(fm["timestamp"]).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return

    now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()

    for service, window in FRESHNESS_WINDOWS.items():
        if service in source_ref:
            age = now - ts
            if window.total_seconds() > 0 and age > window:
                result.warnings.append(
                    f"STAGE 3 WARN: Source '{source_ref}' is {age} old, "
                    f"freshness window for {service} is {window}"
                )
            break


def validate_file(file_path: str) -> ValidationResult:
    """Run full validation pipeline on a single file."""
    result = ValidationResult(file_path=file_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        result.passed = False
        result.errors.append(f"Cannot read file: {e}")
        return result

    fm, body = parse_frontmatter(content)

    # Stage 1: Schema validation
    validate_frontmatter(fm, result)

    # Stage 2: Source attribution
    validate_source_attribution(body, result)

    # Stage 3: Freshness
    validate_freshness(fm, result)

    # Stage 4: Contradiction check (requires vault context — simplified here)
    # Full contradiction checking requires loading related vault files
    # This is handled by the grounding-validator SKILL.md at runtime

    # Stage 5: Confidence scoring
    if fm and "confidence" in fm:
        conf = fm["confidence"]
        if conf < 0.4:
            result.errors.append(f"STAGE 5: Confidence {conf} < 0.4 — BLOCKED")
            result.passed = False
        elif conf < 0.7:
            result.warnings.append(f"STAGE 5: Confidence {conf} < 0.7 — HITL required")

    # Stage 6: Routing
    if fm and "review_status" in fm:
        if fm["review_status"] == "pending" and fm.get("confidence", 0) < 0.7:
            result.warnings.append("STAGE 6: Output requires HITL review before delivery")

    return result


def find_agent_files(directory: str) -> list[str]:
    """Find all .md files with agent frontmatter in a directory."""
    agent_files = []
    for root, _, files in os.walk(directory):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    first_line = f.readline()
                    if first_line.strip() == "---":
                        content = f.read(500)
                        if "agent:" in content and "skill:" in content:
                            agent_files.append(fpath)
            except Exception:
                continue
    return agent_files


def print_result(result: ValidationResult) -> None:
    """Print validation result in a readable format."""
    status = "✅ PASSED" if result.passed else "❌ FAILED"
    print(f"\n{'='*60}")
    print(f"  {status}  {result.file_path}")
    print(f"{'='*60}")

    if result.stats:
        claims = result.stats.get("total_factual_claims", 0)
        sourced = result.stats.get("sourced_claims", 0)
        unsourced = result.stats.get("unsourced_claims", 0)
        print(f"  Claims: {claims} total, {sourced} sourced, {unsourced} unsourced")

    for err in result.errors:
        print(f"  ❌ {err}")
    for warn in result.warnings:
        print(f"  ⚠️  {warn}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate-grounding.py <file_or_directory>")
        print("       python validate-grounding.py --all")
        print("       python validate-grounding.py --report")
        sys.exit(1)

    target = sys.argv[1]

    if target == "--all":
        vault_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = find_agent_files(vault_dir)
    elif os.path.isdir(target):
        files = find_agent_files(target)
    elif os.path.isfile(target):
        files = [target]
    else:
        print(f"Error: {target} is not a valid file or directory")
        sys.exit(1)

    if not files:
        print("No agent-produced .md files found.")
        sys.exit(0)

    results = [validate_file(f) for f in files]

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    for r in results:
        print_result(r)

    print(f"\n{'='*60}")
    print(f"  SUMMARY: {passed}/{total} passed, {failed}/{total} failed")
    print(f"{'='*60}")

    if target == "--report":
        report_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "memory", "system", "validation-report.md"
        )
        with open(report_path, "w") as f:
            f.write(f"# Grounding Validation Report\n\n")
            f.write(f"**Date:** {datetime.now().isoformat()}\n")
            f.write(f"**Files checked:** {total}\n")
            f.write(f"**Passed:** {passed}\n")
            f.write(f"**Failed:** {failed}\n\n")
            for r in results:
                status = "PASS" if r.passed else "FAIL"
                f.write(f"## {status} — {r.file_path}\n")
                for err in r.errors:
                    f.write(f"- ❌ {err}\n")
                for warn in r.warnings:
                    f.write(f"- ⚠️ {warn}\n")
                f.write("\n")
        print(f"\nReport written to: {report_path}")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
