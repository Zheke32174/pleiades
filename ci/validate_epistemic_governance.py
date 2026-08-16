#!/usr/bin/env python3
"""Validate MODOS distinction registries and epistemic ledgers.

The validator is deliberately network-independent. It assimilates a practical
subset of several established ideas:

* shape validation (JSON Schema now; SHACL-compatible graph projection later),
* provenance-bearing evidence records,
* Doyle-style dependency and revision tracking,
* Dung-style argument attack graphs,
* paraconsistent preservation of unresolved disagreement,
* competency questions as executable ontology requirements.

It does not decide truth. It proves that the ecology has not silently erased
the distinctions, dependencies, provenance, alternatives, or dissent required
for later truth-seeking.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


PROMOTED_STATUSES = {"accepted", "canonical"}
DEAD_DEPENDENCY_STATUSES = {"rejected", "superseded"}
DISSENT_STANCES = {"attack", "qualify"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def schema_errors(instance: Any, schema: dict[str, Any], label: str) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    rows = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    errors: list[str] = []
    for error in rows:
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{label} schema {location}: {error.message}")
    return errors


def duplicate_values(values: Iterable[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def detect_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for target in sorted(edges.get(node, ())):
            if state.get(target, 0) == 0:
                cycle = visit(target)
                if cycle:
                    return cycle
            elif state.get(target) == 1:
                index = stack.index(target)
                return stack[index:] + [target]
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def grounded_extension(arguments: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """Return the grounded extension and unresolved active arguments.

    Dung attack cycles are legal. They remain unresolved unless defended by
    already accepted arguments; the validator never deletes them to manufacture
    consistency.
    """
    active = {row["id"]: row for row in arguments if row["status"] == "active"}
    attackers: dict[str, set[str]] = defaultdict(set)
    for argument in active.values():
        for target in argument["attacks"]:
            if target in active:
                attackers[target].add(argument["id"])

    accepted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for argument_id in sorted(active):
            if argument_id in accepted:
                continue
            is_defended = all(
                any(attacker in active.get(defender, {}).get("attacks", []) for defender in accepted)
                for attacker in attackers.get(argument_id, set())
            )
            if is_defended:
                accepted.add(argument_id)
                changed = True

    return accepted, set(active) - accepted


def validate_distinctions(
    registry: dict[str, Any],
) -> tuple[list[str], list[str], dict[str, Any], set[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = registry["spec"]["distinctions"]
    distinction_ids = [row["id"] for row in rows]

    duplicates = duplicate_values(distinction_ids)
    if duplicates:
        errors.append("duplicate distinction ids: " + ", ".join(duplicates))

    pair_index: dict[frozenset[str], str] = {}
    for index, distinction in enumerate(rows):
        term_ids = [term["id"] for term in distinction["terms"]]
        duplicate_terms = duplicate_values(term_ids)
        if duplicate_terms:
            errors.append(
                f"distinction[{index}] {distinction['id']} has duplicate term ids: "
                + ", ".join(duplicate_terms)
            )

        middle_ids = [entry["id"] for entry in distinction["middleSpace"]]
        duplicate_middle = duplicate_values(middle_ids)
        if duplicate_middle:
            errors.append(
                f"distinction[{index}] {distinction['id']} has duplicate middle-space ids: "
                + ", ".join(duplicate_middle)
            )

        overlap = sorted(set(term_ids) & set(middle_ids))
        if overlap:
            errors.append(
                f"distinction[{index}] {distinction['id']} reuses term ids in middleSpace: "
                + ", ".join(overlap)
            )

        for collapse_index, collapse in enumerate(distinction["forbiddenCollapses"]):
            if collapse["from"] not in term_ids:
                errors.append(
                    f"distinction[{index}] forbiddenCollapses[{collapse_index}] unknown from term: "
                    f"{collapse['from']}"
                )
            if collapse["to"] not in term_ids:
                errors.append(
                    f"distinction[{index}] forbiddenCollapses[{collapse_index}] unknown to term: "
                    f"{collapse['to']}"
                )
            if collapse["from"] == collapse["to"]:
                errors.append(
                    f"distinction[{index}] forbiddenCollapses[{collapse_index}] collapses a term "
                    "into itself"
                )

        if any(not question.rstrip().endswith("?") for question in distinction["competencyQuestions"]):
            warnings.append(
                f"distinction {distinction['id']} has a competency question without a trailing '?'"
            )

        pair = frozenset(term_ids)
        if len(term_ids) == 2 and pair in pair_index:
            errors.append(
                f"distinctions {pair_index[pair]} and {distinction['id']} describe the same term pair"
            )
        elif len(term_ids) == 2:
            pair_index[pair] = distinction["id"]

    report = {
        "registry": registry["metadata"]["name"],
        "version": registry["metadata"]["version"],
        "distinctionCount": len(rows),
        "termCount": sum(len(row["terms"]) for row in rows),
        "middleSpaceCount": sum(len(row["middleSpace"]) for row in rows),
        "competencyQuestionCount": sum(len(row["competencyQuestions"]) for row in rows),
        "counterexampleCount": sum(len(row["counterexamples"]) for row in rows),
    }
    return errors, warnings, report, set(distinction_ids)


def validate_ledger(
    ledger: dict[str, Any], distinction_ids: set[str]
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    spec = ledger["spec"]

    evidence = spec["evidence"]
    claims = spec["claims"]
    arguments = spec["arguments"]
    decisions = spec["decisions"]

    evidence_ids = [row["id"] for row in evidence]
    claim_ids = [row["id"] for row in claims]
    argument_ids = [row["id"] for row in arguments]
    decision_ids = [row["id"] for row in decisions]

    for label, values in (
        ("evidence", evidence_ids),
        ("claim", claim_ids),
        ("argument", argument_ids),
        ("decision", decision_ids),
    ):
        duplicates = duplicate_values(values)
        if duplicates:
            errors.append(f"duplicate {label} ids: " + ", ".join(duplicates))

    evidence_index = {row["id"]: row for row in evidence}
    claim_index = {row["id"]: row for row in claims}
    argument_index = {row["id"]: row for row in arguments}

    evidence_edges: dict[str, set[str]] = defaultdict(set)
    for row in evidence:
        for parent in row.get("derivedFrom", []):
            if parent not in evidence_index:
                errors.append(f"evidence {row['id']} derives from unknown evidence: {parent}")
            elif parent == row["id"]:
                errors.append(f"evidence {row['id']} derives from itself")
            else:
                evidence_edges[row["id"]].add(parent)
    cycle = detect_cycle(evidence_edges)
    if cycle:
        errors.append("evidence derivation graph contains a cycle: " + " -> ".join(cycle))

    dependency_edges: dict[str, set[str]] = defaultdict(set)
    supersession_edges: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        for evidence_ref in claim["evidenceRefs"]:
            if evidence_ref not in evidence_index:
                errors.append(f"claim {claim['id']} cites unknown evidence: {evidence_ref}")

        for dependency in claim["dependsOn"]:
            if dependency not in claim_index:
                errors.append(f"claim {claim['id']} depends on unknown claim: {dependency}")
            elif dependency == claim["id"]:
                errors.append(f"claim {claim['id']} depends on itself")
            else:
                dependency_edges[claim["id"]].add(dependency)

        for superseded in claim["revision"]["supersedes"]:
            if superseded not in claim_index:
                errors.append(f"claim {claim['id']} supersedes unknown claim: {superseded}")
            elif superseded == claim["id"]:
                errors.append(f"claim {claim['id']} supersedes itself")
            else:
                supersession_edges[claim["id"]].add(superseded)

        for distinction_ref in claim["preservesDistinctions"]:
            if distinction_ref not in distinction_ids:
                errors.append(
                    f"claim {claim['id']} preserves unknown distinction: {distinction_ref}"
                )
        for collapse in claim.get("potentialCollapses", []):
            if collapse["distinctionId"] not in distinction_ids:
                errors.append(
                    f"claim {claim['id']} declares unknown collapse risk: "
                    f"{collapse['distinctionId']}"
                )

        if claim["categorySensitive"]:
            if not claim["preservesDistinctions"]:
                errors.append(
                    f"category-sensitive claim {claim['id']} preserves no registered distinction"
                )
            if not claim["alternatives"]:
                errors.append(
                    f"category-sensitive claim {claim['id']} records no alternative interpretation"
                )
            if not claim.get("potentialCollapses"):
                errors.append(
                    f"category-sensitive claim {claim['id']} records no collapse risk or mitigation"
                )

        if claim["status"] in PROMOTED_STATUSES:
            if not claim["evidenceRefs"]:
                errors.append(f"promoted claim {claim['id']} has no evidence")
            dead_dependencies = sorted(
                dependency
                for dependency in claim["dependsOn"]
                if dependency in claim_index
                and claim_index[dependency]["status"] in DEAD_DEPENDENCY_STATUSES
            )
            if dead_dependencies:
                errors.append(
                    f"promoted claim {claim['id']} depends on dead claims: "
                    + ", ".join(dead_dependencies)
                )

        if claim["confidence"] >= 0.8 and claim["evidenceRefs"]:
            source_groups = {
                evidence_index[ref]["sourceGroup"]
                for ref in claim["evidenceRefs"]
                if ref in evidence_index
            }
            if len(source_groups) < 2:
                warnings.append(
                    f"high-confidence claim {claim['id']} relies on fewer than two independent "
                    "source groups"
                )

        review_after = claim.get("reviewAfter")
        if review_after:
            timestamp = datetime.fromisoformat(review_after.replace("Z", "+00:00"))
            if timestamp < datetime.now(timezone.utc) and claim["status"] in PROMOTED_STATUSES:
                warnings.append(f"promoted claim {claim['id']} is overdue for review")

    for label, graph in (
        ("claim dependency", dependency_edges),
        ("claim supersession", supersession_edges),
    ):
        cycle = detect_cycle(graph)
        if cycle:
            errors.append(f"{label} graph contains a cycle: " + " -> ".join(cycle))

    for argument in arguments:
        if argument["claimId"] not in claim_index:
            errors.append(
                f"argument {argument['id']} targets unknown claim: {argument['claimId']}"
            )
        for ground in argument["grounds"]:
            if ground not in evidence_index:
                errors.append(f"argument {argument['id']} cites unknown evidence: {ground}")
        for target in argument["attacks"]:
            if target not in argument_index:
                errors.append(f"argument {argument['id']} attacks unknown argument: {target}")
            elif target == argument["id"]:
                warnings.append(f"argument {argument['id']} attacks itself and will remain unresolved")
            elif argument_index[target]["claimId"] != argument["claimId"]:
                warnings.append(
                    f"argument {argument['id']} attacks {target} across claim boundaries"
                )

    decision_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        claim_id = decision["claimId"]
        if claim_id not in claim_index:
            errors.append(f"decision {decision['id']} targets unknown claim: {claim_id}")
            continue
        decision_by_claim[claim_id].append(decision)

        selected = set(decision["selectedArguments"])
        dissent = set(decision["dissentingArguments"])
        overlap = sorted(selected & dissent)
        if overlap:
            errors.append(
                f"decision {decision['id']} lists arguments as both selected and dissenting: "
                + ", ".join(overlap)
            )

        referenced = selected | dissent
        for argument_ref in sorted(referenced):
            if argument_ref not in argument_index:
                errors.append(
                    f"decision {decision['id']} references unknown argument: {argument_ref}"
                )
            elif argument_index[argument_ref]["claimId"] != claim_id:
                errors.append(
                    f"decision {decision['id']} references argument {argument_ref} "
                    f"for another claim"
                )

        if decision["status"] == "accept":
            active_dissent = {
                argument["id"]
                for argument in arguments
                if argument["claimId"] == claim_id
                and argument["status"] == "active"
                and argument["stance"] in DISSENT_STANCES
            }
            omitted = sorted(active_dissent - selected - dissent)
            if omitted:
                errors.append(
                    f"decision {decision['id']} silently omits active dissent: "
                    + ", ".join(omitted)
                )

    for claim in claims:
        if claim["status"] in PROMOTED_STATUSES:
            accepting = [
                decision
                for decision in decision_by_claim.get(claim["id"], [])
                if decision["status"] == "accept"
            ]
            if not accepting:
                errors.append(
                    f"promoted claim {claim['id']} has no explicit accepting decision"
                )

    grounded, unresolved = grounded_extension(arguments)
    report = {
        "ledger": ledger["metadata"]["name"],
        "mindId": ledger["metadata"]["mindId"],
        "evidenceCount": len(evidence),
        "claimCount": len(claims),
        "argumentCount": len(arguments),
        "decisionCount": len(decisions),
        "promotedClaimCount": sum(
            claim["status"] in PROMOTED_STATUSES for claim in claims
        ),
        "categorySensitiveClaimCount": sum(claim["categorySensitive"] for claim in claims),
        "groundedAcceptedArguments": sorted(grounded),
        "unresolvedActiveArguments": sorted(unresolved),
    }
    return errors, warnings, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--distinctions", type=Path, required=True)
    parser.add_argument("--distinction-schema", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--ledger-schema", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    registry = load_json(args.distinctions)
    distinction_schema = load_json(args.distinction_schema)
    ledger = load_json(args.ledger)
    ledger_schema = load_json(args.ledger_schema)

    errors = schema_errors(registry, distinction_schema, "distinction registry")
    errors.extend(schema_errors(ledger, ledger_schema, "epistemic ledger"))
    warnings: list[str] = []
    report: dict[str, Any] = {}

    if not errors:
        distinction_errors, distinction_warnings, distinction_report, distinction_ids = (
            validate_distinctions(registry)
        )
        ledger_errors, ledger_warnings, ledger_report = validate_ledger(
            ledger, distinction_ids
        )
        errors.extend(distinction_errors)
        errors.extend(ledger_errors)
        warnings.extend(distinction_warnings)
        warnings.extend(ledger_warnings)
        report = {
            "valid": not errors,
            "distinctions": distinction_report,
            "ledger": ledger_report,
            "warningCount": len(warnings),
            "errorCount": len(errors),
        }
    else:
        report = {
            "valid": False,
            "warningCount": 0,
            "errorCount": len(errors),
        }

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if errors:
        return 1

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
