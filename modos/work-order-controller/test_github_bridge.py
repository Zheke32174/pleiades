from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import unittest

from github_bridge import (
    AdmissionError,
    GitHubBridgeError,
    SignatureError,
    admit_workflow_job,
    project_commit_status,
    verify_webhook_signature,
)

SECRET = b"test-webhook-secret"
SHA = "a" * 40


def payload(**overrides):
    value = {
        "action": "queued",
        "repository": {
            "id": 123,
            "full_name": "Zheke32174/pleiades",
            "owner": {"login": "Zheke32174"},
        },
        "workflow_job": {
            "id": 456,
            "run_id": 789,
            "run_attempt": 2,
            "name": "checked-in-closure",
            "workflow_name": "Validate ecology",
            "head_branch": "feature/test",
            "head_sha": SHA,
            "labels": ["self-hosted", "pleiades", "linux"],
        },
    }
    for key, item in overrides.items():
        if key == "repository":
            value["repository"].update(item)
        elif key == "workflow_job":
            value["workflow_job"].update(item)
        else:
            value[key] = item
    return value


def delivery(value=None, *, secret=SECRET, event="workflow_job"):
    body = json.dumps(
        value or payload(), sort_keys=True, separators=(",", ":")
    ).encode()
    signature = "sha256=" + hmac.new(
        secret, body, hashlib.sha256
    ).hexdigest()
    return body, {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": "72d3162e-cc78-11e3-81ab-4c9367dc0958",
        "X-GitHub-Hook-ID": "292430182",
        "Content-Type": "application/json",
    }


class GitHubWebhookAdmissionTests(unittest.TestCase):
    def test_github_published_signature_vector(self):
        verify_webhook_signature(
            b"Hello, World!",
            "It's a Secret to Everybody",
            "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17",
        )

    def test_queued_job_becomes_deterministic_authority_free_proposal(self):
        body, headers = delivery()
        first = admit_workflow_job(body, headers, SECRET)
        second = admit_workflow_job(body, headers, SECRET)
        self.assertEqual(first, second)
        self.assertEqual(first.authorityCeiling, "none")
        self.assertEqual(first.commitSha, SHA)
        self.assertFalse(first.arrivalOrderAuthoritative)
        self.assertFalse(first.workflowContentExecutable)
        self.assertEqual(first.labels, ("self-hosted", "pleiades", "linux"))

    def test_payload_change_changes_proposal_identity(self):
        body, headers = delivery()
        first = admit_workflow_job(body, headers, SECRET)
        altered_body, altered_headers = delivery(
            payload(
                workflow_job={
                    "labels": ["self-hosted", "pleiades", "linux", "gpu"]
                }
            )
        )
        second = admit_workflow_job(altered_body, altered_headers, SECRET)
        self.assertNotEqual(first.payloadDigest, second.payloadDigest)
        self.assertNotEqual(first.proposalId, second.proposalId)

    def test_signature_is_checked_before_json_and_tampering_fails(self):
        body, headers = delivery()
        with self.assertRaises(SignatureError):
            admit_workflow_job(body + b" ", headers, SECRET)
        missing = dict(headers)
        missing.pop("X-Hub-Signature-256")
        with self.assertRaises(SignatureError):
            admit_workflow_job(b"not-json", missing, SECRET)

    def test_content_type_and_duplicate_json_keys_fail_closed(self):
        body, headers = delivery()
        with self.assertRaises(AdmissionError):
            admit_workflow_job(
                body,
                {**headers, "Content-Type": "application/x-www-form-urlencoded"},
                SECRET,
            )
        ordinary = json.dumps(payload(), sort_keys=True, separators=(",", ":"))
        duplicate_body = (
            '{"action":"queued","action":"completed",' + ordinary[1:]
        ).encode()
        duplicate_headers = dict(headers)
        duplicate_headers["X-Hub-Signature-256"] = (
            "sha256="
            + hmac.new(SECRET, duplicate_body, hashlib.sha256).hexdigest()
        )
        with self.assertRaisesRegex(AdmissionError, "duplicate key"):
            admit_workflow_job(duplicate_body, duplicate_headers, SECRET)

    def test_unsupported_event_action_and_oversize_fail_closed(self):
        body, headers = delivery()
        with self.assertRaises(AdmissionError):
            admit_workflow_job(
                body,
                {**headers, "X-GitHub-Event": "push"},
                SECRET,
            )
        completed_body, completed_headers = delivery(payload(action="completed"))
        with self.assertRaises(AdmissionError):
            admit_workflow_job(completed_body, completed_headers, SECRET)
        with self.assertRaises(AdmissionError):
            admit_workflow_job(
                body,
                headers,
                SECRET,
                max_body_bytes=len(body) - 1,
            )

    def test_malformed_repository_sha_and_labels_fail_closed(self):
        for changed in (
            payload(repository={"full_name": "not-a-repository"}),
            payload(workflow_job={"head_sha": "A" * 40}),
            payload(workflow_job={"labels": ["pleiades", "PLEIADES"]}),
            payload(workflow_job={"labels": ["bad\nlabel"]}),
        ):
            body, headers = delivery(changed)
            with self.assertRaises(GitHubBridgeError):
                admit_workflow_job(body, headers, SECRET)


class GitHubStatusProjectionTests(unittest.TestCase):
    def test_status_mapping(self):
        cases = (
            ({"jobClass": "ecology-closure", "status": "running"}, "pending"),
            ({"jobClass": "ecology-closure", "status": "success"}, "success"),
            (
                {
                    "jobClass": "ecology-closure",
                    "status": "failure",
                    "failure": {"class": "validator-failed"},
                },
                "failure",
            ),
            (
                {
                    "jobClass": "ecology-closure",
                    "status": "failure",
                    "failure": {"class": "runner-startup"},
                },
                "error",
            ),
        )
        for receipt, expected in cases:
            with self.subTest(expected=expected):
                projection = project_commit_status(
                    "Zheke32174/pleiades",
                    SHA,
                    receipt,
                    target_url="https://evidence.example/run/1",
                )
                self.assertEqual(projection["body"]["state"], expected)
                self.assertEqual(
                    projection["body"]["context"], "pleiades/ecology-closure"
                )
                self.assertEqual(projection["authority"], "presentation-only")
                self.assertEqual(projection["method"], "POST")

    def test_exact_receipt_retry_is_deterministic(self):
        receipt = {"jobClass": "ecology-closure", "status": "success"}
        self.assertEqual(
            project_commit_status("Zheke32174/pleiades", SHA, receipt),
            project_commit_status("Zheke32174/pleiades", SHA, receipt),
        )

    def test_invalid_projection_inputs_are_rejected(self):
        receipt = {"jobClass": "ecology-closure", "status": "success"}
        bad_cases = (
            ("not-a-repository", SHA, receipt, None),
            ("Zheke32174/pleiades", "A" * 40, receipt, None),
            (
                "Zheke32174/pleiades",
                SHA,
                {"jobClass": "Bad Context", "status": "success"},
                None,
            ),
            (
                "Zheke32174/pleiades",
                SHA,
                receipt,
                "http://evidence.example/run/1",
            ),
            (
                "Zheke32174/pleiades",
                SHA,
                receipt,
                "https://user:pass@evidence.example/run/1",
            ),
        )
        for repository, sha, value, url in bad_cases:
            with self.subTest(repository=repository, sha=sha, url=url):
                with self.assertRaises(GitHubBridgeError):
                    project_commit_status(repository, sha, value, target_url=url)

    def test_module_has_no_execution_or_network_client_surface(self):
        import github_bridge

        source = inspect.getsource(github_bridge)
        for forbidden in (
            "subprocess",
            "requests",
            "http.client",
            "urllib.request",
            "socket",
            "os.environ",
            "GITHUB_TOKEN",
            "run_command",
            "shell=True",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
