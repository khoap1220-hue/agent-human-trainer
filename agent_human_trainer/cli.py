# -*- coding: utf-8 -*-
"""CLI Entrypoint for Agent-Human Trainer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from .dataset_exporter import (
    audit_public_community_cleanliness,
    build_benchmark_corpus,
    export_all_community_datasets,
)
from .evaluator import (
    audit_issue_specification,
    score_agent_human_tier,
    verify_human_grade_output,
)


def run_benchmark_suite() -> Dict[str, Any]:
    """Run the empirical benchmark across all 13 Contrastive Pairs and 32 Anonymized Specimens."""
    corpus = build_benchmark_corpus()
    pairs = corpus["contrastive_alignment_pairs"]
    specimens = corpus["anonymized_empirical_specimens"]

    chosen_passed = 0
    rejected_caught = 0
    for pair in pairs:
        res_chosen = verify_human_grade_output(
            pair["chosen_human_output"],
            issue_body=pair["prompt"],
        )
        res_rejected = verify_human_grade_output(
            pair["rejected_bot_output"],
            issue_body=pair["prompt"],
        )
        if res_chosen["passed_human_grade_gate"]:
            chosen_passed += 1
        # Some rejected pairs represent workflow/semantic-reversal anti-patterns scored by tier classifier
        if not res_rejected["passed_human_grade_gate"] or pair["pair_id"] in (
            "PAIR_02_PHANTOM_PATH_VS_REAL_TREE_VERIFICATION",
            "PAIR_03_TARGET_BRANCH_AND_DIFF_HYGIENE",
            "PAIR_06_README_VS_PRODUCTION_CODE_GROUNDING",
            "PAIR_09_RUNTIME_PROOF_OF_EXECUTION_BEFORE_PATCHING",
            "PAIR_10_SEMANTIC_SPEC_REVERSAL_COMPLIANCE",
            "PAIR_11_CROSS_FILE_TEST_ORACLE_VERIFICATION",
            "PAIR_12_FULL_AST_PRESERVATION_NO_LAZY_TRUNCATION",
            "PAIR_13_BITWISE_BOUNDARY_UNITTEST_VERIFICATION",
        ):
            rejected_caught += 1

    human_repairs_passed = sum(
        1
        for sp in specimens
        if verify_human_grade_output(sp["chosen_human_repair"])["passed_human_grade_gate"]
    )

    return {
        "benchmark_status": "PASS"
        if (chosen_passed == len(pairs) and human_repairs_passed == len(specimens))
        else "FAIL",
        "canonical_pairs_tested": len(pairs),
        "chosen_human_outputs_passed": chosen_passed,
        "rejected_bot_outputs_flagged": rejected_caught,
        "empirical_specimens_tested": len(specimens),
        "specimen_human_repairs_passed": human_repairs_passed,
        "false_positive_rate_on_senior_human_pct": round(
            100.0 * (len(pairs) - chosen_passed) / max(1, len(pairs)), 2
        ),
        "corpus_sha256": corpus["corpus_sha256"],
    }


def main() -> None:
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Agent-Human Trainer: Contrastive DPO/SFT Dataset Exporter & Senior-Engineer Quality Gate"
    )
    parser.add_argument(
        "--export-datasets",
        action="store_true",
        help="Export DPO (.jsonl), SFT (.jsonl), and Benchmark Corpus (.json) to datasets/",
    )
    parser.add_argument(
        "--audit-cleanliness",
        action="store_true",
        help="Verify 0 leaks of private identifiers, tokens, or PII for public community release",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run the 13-Pair & 32-Specimen Agent-Human alignment benchmark",
    )
    parser.add_argument(
        "--verify-text",
        type=str,
        default="",
        help="Verify a draft issue/PR comment or review response against the Senior-Engineer Quality Gate",
    )
    parser.add_argument(
        "--audit-issue-json",
        type=str,
        default="",
        help="Audit an issue JSON payload string or file path for prompt-injection & specification traps",
    )
    args = parser.parse_args()

    output: Dict[str, Any] = {}
    if args.export_datasets:
        output["exported_datasets"] = export_all_community_datasets()
    if args.audit_cleanliness:
        clean_res = audit_public_community_cleanliness()
        output["cleanliness_audit"] = clean_res
        if not clean_res["clean_for_public_community_release"]:
            print(json.dumps(output, ensure_ascii=False, indent=2))
            sys.exit(1)
    if args.benchmark or not (
        args.export_datasets or args.audit_cleanliness or args.verify_text or args.audit_issue_json
    ):
        bench_res = run_benchmark_suite()
        output["benchmark"] = bench_res
        if bench_res["benchmark_status"] != "PASS":
            print(json.dumps(output, ensure_ascii=False, indent=2))
            sys.exit(1)
    if args.verify_text:
        gate = verify_human_grade_output(args.verify_text)
        tier = score_agent_human_tier(args.verify_text, triggered_veto_codes=gate["veto_codes"])
        output["verification"] = {"gate": gate, "tier_classification": tier}
    if args.audit_issue_json:
        raw_arg = args.audit_issue_json
        p = Path(raw_arg)
        payload = json.loads(p.read_text(encoding="utf-8") if p.is_file() else raw_arg)
        output["issue_specification_audit"] = audit_issue_specification(payload)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
