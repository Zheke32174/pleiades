"""Pure GitHub coordination adapters for Pleiades runner proposals and status display.

This module performs no network request, reads no credential environment, and executes
no workflow content. It verifies and reduces one GitHub webhook delivery into an
authority-free proposal, or projects an authoritative Pleiades receipt into a bounded
commit-status request descriptor.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping
from urllib.parse import quote, urlsplit

MAX_WEBHOOK_BYTES = 1_048_576
MAX_LABELS = 32
MAX_LABEL_LENGTH = 64
MAX_TEXT_LENGTH = 256
MAX_DESCRIPTION_LENGTH = 140
MAX_CONTEXT_LENGTH = 100
MAX_TARGET_URL_LENGTH = 2_048

_SHA256_HEADER = re.compile(r"^sha256=[0-9a-f]{64}$")
_SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_DELIVERY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REPOSITORY = re.compile(
    r"^(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"(?P<name>[A-Za-z0-9._-]{1,100})$"
)
_JOB_CLASS = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")

_DETERMINISTIC_FAILURES = frozenset(
    {
        "assembler-failed",
        "contract-failed",
        "policy-denied",
        "tests-failed",
        "validation-failed",
        "validator-failed",
    }
)


class GitHubBridgeError(ValueError):
    """A GitHub bridge contract was violated."""


class SignatureError(GitHubBridgeError):
    """The webhook signature was missing or invalid."""


class AdmissionError(GitHubBridgeError):
    """The authenticated delivery is not an admissible v1 proposal."""


@dataclass(frozen=True)
class GitHubJobProposal:
    schemaVersion: str
    proposalId: str
    authorityCeiling: str
    source: str
    event: str
    action: str
    deliveryId: str
    hookId: int
    payloadDigest: str
    repositoryId: int
    repositoryFullName: str
    commitSha: str
    jobId: int
    runId: int
    runAttempt: int
    jobName: str
    workflowName: str
    headBranch: str | None
    labels: tuple[str, ...]
    arrivalOrderAuthoritative: bool
    workflowContentExecutable: bool

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["labels"] = list(self.labels)
        return value


def verify_webhook_signature(
    raw_body: bytes,
    secret: str | bytes,
    signature_header: str | None,
) -> None:
    """Verify GitHub's HMAC-SHA-256 signature over the unmodified raw body."""
    if not isinstance(raw_body, bytes):
        raise TypeError("raw_body must be bytes")
    secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
    if not isinstance(secret_bytes, bytes) or not secret_bytes:
        raise SignatureError("webhook secret is missing")
    if len(secret_bytes) > 4_096:
        raise SignatureError("webhook secret exceeds the accepted bound")
    if not isinstance(signature_header, str) or not _SHA256_HEADER.fullmatch(
        signature_header
    ):
        raise SignatureError("X-Hub-Signature-256 is missing or malformed")
    expected = "sha256=" + hmac.new(
        secret_bytes, raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise SignatureError("webhook signature does not match the raw body")


def admit_workflow_job(
    raw_body: bytes,
    headers: Mapping[str, str],
    secret: str | bytes,
    *,
    max_body_bytes: int = MAX_WEBHOOK_BYTES,
) -> GitHubJobProposal:
    """Authenticate and reduce a queued workflow job to an authority-free proposal."""
    if not isinstance(raw_body, bytes):
        raise TypeError("raw_body must be bytes")
    if not 1 <= max_body_bytes <= 25 * 1024 * 1024:
        raise AdmissionError("max_body_bytes is outside the supported range")
    if not raw_body:
        raise AdmissionError("webhook body is empty")
    if len(raw_body) > max_body_bytes:
        raise AdmissionError("webhook body exceeds the local admission bound")

    normalized_headers = _normalize_headers(headers)
    verify_webhook_signature(
        raw_body,
        secret,
        normalized_headers.get("x-hub-signature-256"),
    )

    event = _bounded_text(
        normalized_headers.get("x-github-event"),
        "X-GitHub-Event",
        maximum=64,
    )
    delivery_id = _bounded_text(
        normalized_headers.get("x-github-delivery"),
        "X-GitHub-Delivery",
        maximum=128,
    )
    if not _DELIVERY_ID.fullmatch(delivery_id):
        raise AdmissionError("X-GitHub-Delivery has an unsupported identity shape")
    hook_id = _positive_int(
        normalized_headers.get("x-github-hook-id"),
        "X-GitHub-Hook-ID",
    )
    if event != "workflow_job":
        raise AdmissionError("only workflow_job deliveries are admitted in v1")

    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdmissionError("webhook body is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise AdmissionError("webhook payload must be a JSON object")
    if payload.get("action") != "queued":
        raise AdmissionError("only queued workflow_job actions are admitted in v1")

    repository = _object(payload.get("repository"), "repository")
    job = _object(payload.get("workflow_job"), "workflow_job")

    repository_id = _positive_int(repository.get("id"), "repository.id")
    repository_full_name = _repository_name(
        repository.get("full_name"), "repository.full_name"
    )
    owner = repository.get("owner")
    if isinstance(owner, dict) and owner.get("login") is not None:
        owner_login = _bounded_text(
            owner.get("login"), "repository.owner.login", maximum=39
        )
        expected_owner = repository_full_name.split("/", 1)[0]
        if owner_login.casefold() != expected_owner.casefold():
            raise AdmissionError("repository owner login disagrees with full_name")

    commit_sha = _commit_sha(job.get("head_sha"), "workflow_job.head_sha")
    job_id = _positive_int(job.get("id"), "workflow_job.id")
    run_id = _positive_int(job.get("run_id"), "workflow_job.run_id")
    run_attempt = _positive_int(
        job.get("run_attempt", 1), "workflow_job.run_attempt"
    )
    job_name = _bounded_text(job.get("name"), "workflow_job.name")
    workflow_name = _bounded_text(
        job.get("workflow_name"), "workflow_job.workflow_name"
    )
    head_branch = job.get("head_branch")
    if head_branch is not None:
        head_branch = _bounded_text(
            head_branch, "workflow_job.head_branch", maximum=256
        )
    labels = _labels(job.get("labels", []))

    payload_digest = _sha256_id(raw_body)
    proposal_id = _sha256_id(
        (delivery_id + "\0" + payload_digest).encode("utf-8")
    )
    return GitHubJobProposal(
        schemaVersion="pleiades.github-job-proposal/v1",
        proposalId=proposal_id,
        authorityCeiling="none",
        source="github-workflow-job",
        event=event,
        action="queued",
        deliveryId=delivery_id,
        hookId=hook_id,
        payloadDigest=payload_digest,
        repositoryId=repository_id,
        repositoryFullName=repository_full_name,
        commitSha=commit_sha,
        jobId=job_id,
        runId=run_id,
        runAttempt=run_attempt,
        jobName=job_name,
        workflowName=workflow_name,
        headBranch=head_branch,
        labels=labels,
        arrivalOrderAuthoritative=False,
        workflowContentExecutable=False,
    )


def project_commit_status(
    repository_full_name: str,
    commit_sha: str,
    receipt: Mapping[str, Any],
    *,
    target_url: str | None = None,
) -> dict[str, Any]:
    """Project an authoritative receipt into a credential-free status request."""
    repository_full_name = _repository_name(
        repository_full_name, "repository_full_name"
    )
    commit_sha = _commit_sha(commit_sha, "commit_sha")
    if not isinstance(receipt, Mapping):
        raise GitHubBridgeError("receipt must be an object")

    job_class = _bounded_text(
        receipt.get("jobClass"), "receipt.jobClass", maximum=64
    )
    if not _JOB_CLASS.fullmatch(job_class):
        raise GitHubBridgeError("receipt.jobClass has an unsupported shape")
    context = "pleiades/" + job_class
    if len(context) > MAX_CONTEXT_LENGTH:
        raise GitHubBridgeError("commit-status context exceeds GitHub's bound")

    state, description = _status_state_and_description(receipt)
    description = _bounded_description(description)
    receipt_digest = receipt.get("receiptDigest")
    if receipt_digest is None:
        receipt_digest = _sha256_id(_canonical_json_bytes(receipt))
    elif not isinstance(receipt_digest, str) or not _SHA256_ID.fullmatch(
        receipt_digest
    ):
        raise GitHubBridgeError(
            "receipt.receiptDigest must be sha256:<lowercase-hex>"
        )

    body: dict[str, str] = {
        "state": state,
        "context": context,
        "description": description,
    }
    if target_url is not None:
        body["target_url"] = _https_url(target_url)

    owner, name = repository_full_name.split("/", 1)
    return {
        "schemaVersion": "pleiades.github-status-request/v1",
        "authority": "presentation-only",
        "method": "POST",
        "path": (
            f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}/"
            f"statuses/{commit_sha}"
        ),
        "repositoryFullName": repository_full_name,
        "commitSha": commit_sha,
        "receiptDigest": receipt_digest,
        "body": body,
    }


def _status_state_and_description(
    receipt: Mapping[str, Any],
) -> tuple[str, str]:
    status = receipt.get("status")
    if status in {"admitted", "pending", "queued", "running"}:
        return "pending", f"{receipt.get('jobClass', 'job')} is {status}"
    if status in {"success", "succeeded"}:
        return "success", f"{receipt.get('jobClass', 'job')} succeeded"
    if status in {"error", "infrastructure-error"}:
        return "error", f"{receipt.get('jobClass', 'job')} infrastructure error"
    if status in {"failure", "failed"}:
        failure = receipt.get("failure")
        failure_class = (
            failure.get("class")
            if isinstance(failure, Mapping)
            else "unspecified-failure"
        )
        failure_class = _bounded_text(
            failure_class, "receipt.failure.class", maximum=64
        )
        if failure_class in _DETERMINISTIC_FAILURES:
            return (
                "failure",
                f"{receipt.get('jobClass', 'job')} failed: {failure_class}",
            )
        return "error", f"{receipt.get('jobClass', 'job')} error: {failure_class}"
    raise GitHubBridgeError("receipt.status is not projectable")


def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        raise AdmissionError("headers must be a mapping")
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise AdmissionError("header names and values must be strings")
        lowered = key.casefold()
        if lowered in normalized:
            raise AdmissionError(f"duplicate header after case folding: {key}")
        normalized[lowered] = value
    return normalized


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdmissionError(f"{label} must be an object")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise AdmissionError(f"{label} must be a positive integer")
    if isinstance(value, str):
        if not value.isascii() or not value.isdigit():
            raise AdmissionError(f"{label} must be a positive integer")
        value = int(value)
    if not isinstance(value, int) or value <= 0:
        raise AdmissionError(f"{label} must be a positive integer")
    if value > 2**63 - 1:
        raise AdmissionError(f"{label} exceeds the supported integer range")
    return value


def _bounded_text(
    value: Any,
    label: str,
    *,
    maximum: int = MAX_TEXT_LENGTH,
) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise AdmissionError(f"{label} must contain 1..={maximum} characters")
    if not _SAFE_TEXT.fullmatch(value):
        raise AdmissionError(f"{label} contains control characters")
    return value


def _repository_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _REPOSITORY.fullmatch(value):
        raise GitHubBridgeError(
            f"{label} is not a canonical owner/repository identity"
        )
    owner, name = value.split("/", 1)
    if owner.endswith("-") or "--" in owner or name in {".", ".."}:
        raise GitHubBridgeError(
            f"{label} is not a canonical owner/repository identity"
        )
    return value


def _commit_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _COMMIT_SHA.fullmatch(value):
        raise GitHubBridgeError(
            f"{label} must be exactly 40 lowercase hexadecimal characters"
        )
    return value


def _labels(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_LABELS:
        raise AdmissionError(
            f"workflow_job.labels must contain at most {MAX_LABELS} items"
        )
    labels: list[str] = []
    seen: set[str] = set()
    for item in value:
        label = _bounded_text(
            item, "workflow_job.labels[]", maximum=MAX_LABEL_LENGTH
        )
        folded = label.casefold()
        if folded in seen:
            raise AdmissionError(
                "workflow_job.labels contains a duplicate identity"
            )
        seen.add(folded)
        labels.append(label)
    return tuple(labels)


def _bounded_description(value: str) -> str:
    if len(value) > MAX_DESCRIPTION_LENGTH:
        value = value[: MAX_DESCRIPTION_LENGTH - 1] + "…"
    if not value or not _SAFE_TEXT.fullmatch(value):
        raise GitHubBridgeError("commit-status description is invalid")
    return value


def _https_url(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_TARGET_URL_LENGTH
    ):
        raise GitHubBridgeError("target_url is missing or too long")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise GitHubBridgeError(
            "target_url must be an absolute HTTPS URL without user-info or fragment"
        )
    return value


def _sha256_id(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise GitHubBridgeError(
            "receipt is not canonical-JSON encodable"
        ) from error
