from __future__ import annotations

import copy
import inspect
import unittest

from drive_bridge import (
    DRIVE_FILE_SCOPE,
    DriveBridgeError,
    DriveNotificationError,
    admit_change_notification,
    build_artifact_manifest,
    plan_change_feed_poll,
    plan_juicefs_handoff,
    plan_resumable_upload,
    reduce_file_to_ingest_proposal,
)

FOLDER_ID = "1D8u3_kY3uOag5LjSkKNI3-Byep2iZ35u"
FILE_ID = "1AbCDefGhij_KLMnop-QRstuVWxyz012345"
DIGEST = "sha256:" + "a" * 64
RECEIPT = "sha256:" + "b" * 64


def manifest():
    return build_artifact_manifest(
        artifact_digest=DIGEST,
        size_bytes=12345,
        mime_type="application/octet-stream",
        file_name="artifact.bin",
        receipt_digest=RECEIPT,
        bridge_folder_id=FOLDER_ID,
    )


def notification_headers(*, state="change", token="secret-token", message="23"):
    return {
        "X-Goog-Channel-ID": "channel-123",
        "X-Goog-Channel-Token": token,
        "X-Goog-Resource-ID": "resource-123",
        "X-Goog-Resource-URI": (
            "https://www.googleapis.com/drive/v3/changes?pageToken=opaque"
        ),
        "X-Goog-Resource-State": state,
        "X-Goog-Message-Number": message,
    }


def drive_file():
    return {
        "id": FILE_ID,
        "name": "artifact.bin",
        "mimeType": "application/octet-stream",
        "size": "12345",
        "sha256Checksum": "a" * 64,
        "version": "7",
        "parents": [FOLDER_ID],
        "trashed": False,
        "appProperties": {
            "p.schema": "artifact-v1",
            "p.role": "juicefs-bridge",
            "p.sha256": "a" * 64,
            "p.size": "12345",
            "p.receipt": "b" * 64,
        },
    }


class DriveBridgeTests(unittest.TestCase):
    def test_manifest_and_resumable_upload_are_deterministic(self):
        first = manifest()
        second = manifest()
        self.assertEqual(first, second)
        plan = plan_resumable_upload(first, pregenerated_file_id=FILE_ID)
        self.assertEqual(plan["oauthScope"], DRIVE_FILE_SCOPE)
        self.assertEqual(plan["query"]["uploadType"], "resumable")
        self.assertEqual(plan["body"]["id"], FILE_ID)
        self.assertEqual(plan["body"]["parents"], [FOLDER_ID])
        self.assertEqual(plan["body"]["appProperties"]["p.sha256"], "a" * 64)
        self.assertTrue(plan["safeCreateRetryIdentity"])
        self.assertFalse(plan["performsNetworkRequest"])
        self.assertEqual(
            first.logicalArtifactUri,
            "artifact://sha256/aa/" + "a" * 64,
        )

    def test_manifest_and_upload_validation_fail_closed(self):
        cases = [
            {"artifact_digest": "sha256:" + "A" * 64},
            {"size_bytes": -1},
            {"mime_type": "bad"},
            {"file_name": "../escape"},
            {"receipt_digest": "bad"},
            {"bridge_folder_id": "short"},
        ]
        base = {
            "artifact_digest": DIGEST,
            "size_bytes": 1,
            "mime_type": "application/octet-stream",
            "file_name": "artifact.bin",
            "receipt_digest": RECEIPT,
            "bridge_folder_id": FOLDER_ID,
        }
        for patch in cases:
            with self.subTest(patch=patch):
                args = dict(base)
                args.update(patch)
                with self.assertRaises(DriveBridgeError):
                    build_artifact_manifest(**args)
        with self.assertRaises(DriveBridgeError):
            plan_resumable_upload(manifest(), pregenerated_file_id="short")
        altered = manifest().to_dict()
        altered["authorityCeiling"] = "execute"
        with self.assertRaises(DriveBridgeError):
            plan_resumable_upload(altered, pregenerated_file_id=FILE_ID)

    def test_change_notification_exact_retry_is_deterministic(self):
        headers = notification_headers()
        first = admit_change_notification(
            headers,
            expected_channel_id="channel-123",
            expected_channel_token="secret-token",
            expected_resource_id="resource-123",
        )
        second = admit_change_notification(
            headers,
            expected_channel_id="channel-123",
            expected_channel_token="secret-token",
            expected_resource_id="resource-123",
        )
        self.assertEqual(first, second)
        self.assertFalse(first["notificationContainsChangeDetails"])
        self.assertFalse(first["notificationOrderAuthoritative"])
        self.assertTrue(first["requiresChangeFeedReconciliation"])
        self.assertNotIn("secret-token", repr(first))

    def test_sync_can_arrive_before_watch_response_resource_binding(self):
        headers = notification_headers(state="sync", message="1")
        signal = admit_change_notification(
            headers,
            expected_channel_id="channel-123",
            expected_channel_token="secret-token",
            expected_resource_id=None,
        )
        self.assertFalse(signal["resourceIdentityPrebound"])
        changed = notification_headers(state="change")
        with self.assertRaises(DriveNotificationError):
            admit_change_notification(
                changed,
                expected_channel_id="channel-123",
                expected_channel_token="secret-token",
                expected_resource_id=None,
            )

    def test_change_notification_mismatch_and_shape_fail_closed(self):
        mutators = [
            lambda h: h.__setitem__("X-Goog-Channel-ID", "other"),
            lambda h: h.__setitem__("X-Goog-Resource-ID", "other"),
            lambda h: h.__setitem__("X-Goog-Channel-Token", "wrong"),
            lambda h: h.__setitem__("X-Goog-Resource-State", "update"),
            lambda h: h.__setitem__("X-Goog-Message-Number", "0"),
            lambda h: h.__setitem__(
                "X-Goog-Resource-URI", "https://evil.example/drive/v3/changes"
            ),
        ]
        for mutate in mutators:
            with self.subTest(mutate=mutate):
                headers = notification_headers()
                mutate(headers)
                with self.assertRaises(DriveBridgeError):
                    admit_change_notification(
                        headers,
                        expected_channel_id="channel-123",
                        expected_channel_token="secret-token",
                        expected_resource_id="resource-123",
                    )

    def test_change_feed_plan_is_bounded_and_credential_free(self):
        plan = plan_change_feed_poll("opaque-page-token", page_size=500)
        self.assertEqual(plan["method"], "GET")
        self.assertEqual(plan["path"], "/drive/v3/changes")
        self.assertEqual(plan["query"]["pageToken"], "opaque-page-token")
        self.assertEqual(plan["query"]["pageSize"], "500")
        self.assertIn("sha256Checksum", plan["query"]["fields"])
        self.assertFalse(plan["performsNetworkRequest"])
        with self.assertRaises(DriveBridgeError):
            plan_change_feed_poll("token", page_size=1001)

    def test_valid_binary_file_becomes_ingest_proposal(self):
        proposal = reduce_file_to_ingest_proposal(
            drive_file(), bridge_folder_id=FOLDER_ID
        )
        self.assertEqual(proposal["artifactDigest"], DIGEST)
        self.assertEqual(proposal["receiptDigest"], RECEIPT)
        self.assertTrue(proposal["downloadAndRehashRequired"])
        self.assertFalse(proposal["driveIsMetadataAuthority"])
        self.assertEqual(
            proposal["futureJuicefsTargetUri"],
            "artifact://sha256/aa/" + "a" * 64,
        )
        renamed = drive_file()
        renamed["name"] = "renamed.bin"
        renamed_proposal = reduce_file_to_ingest_proposal(
            renamed, bridge_folder_id=FOLDER_ID
        )
        self.assertEqual(
            renamed_proposal["futureJuicefsTargetUri"],
            proposal["futureJuicefsTargetUri"],
        )
        self.assertEqual(renamed_proposal["proposalId"], proposal["proposalId"])

    def test_file_ingest_rejects_native_trashed_parent_and_metadata_mismatch(self):
        mutations = [
            lambda f: f.__setitem__(
                "mimeType", "application/vnd.google-apps.document"
            ),
            lambda f: f.__setitem__("trashed", True),
            lambda f: f.__setitem__("parents", ["1OtherFolder_123456789"]),
            lambda f: f.__setitem__("sha256Checksum", "c" * 64),
            lambda f: f["appProperties"].__setitem__("p.size", "999"),
            lambda f: f.__setitem__("version", "0"),
            lambda f: f["appProperties"].pop("p.receipt"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                value = drive_file()
                mutate(value)
                with self.assertRaises(DriveBridgeError):
                    reduce_file_to_ingest_proposal(
                        value, bridge_folder_id=FOLDER_ID
                    )

    def test_app_property_byte_and_count_bounds_are_enforced(self):
        value = drive_file()
        value["appProperties"]["x" * 100] = "y" * 30
        with self.assertRaises(DriveBridgeError):
            reduce_file_to_ingest_proposal(value, bridge_folder_id=FOLDER_ID)
        value = drive_file()
        for index in range(31):
            value["appProperties"][f"k{index}"] = "v"
        with self.assertRaises(DriveBridgeError):
            reduce_file_to_ingest_proposal(value, bridge_folder_id=FOLDER_ID)

    def test_handoff_plan_requires_rehash_and_performs_nothing(self):
        proposal = reduce_file_to_ingest_proposal(
            drive_file(), bridge_folder_id=FOLDER_ID
        )
        plan = plan_juicefs_handoff(proposal)
        self.assertFalse(plan["performsExecution"])
        self.assertTrue(plan["requiredVerification"]["streamHashRequired"])
        self.assertTrue(plan["requiredVerification"]["atomicPublishRequired"])
        self.assertEqual(plan["metadataAuthority"], "pleiades-sql-pdk")
        altered = copy.deepcopy(proposal)
        altered["downloadAndRehashRequired"] = False
        with self.assertRaises(DriveBridgeError):
            plan_juicefs_handoff(altered)

    def test_module_has_no_network_token_shell_or_juicefs_execution_surface(self):
        import drive_bridge

        source = inspect.getsource(drive_bridge)
        forbidden = (
            "import os",
            "subprocess",
            "requests",
            "httpx",
            "urllib.request",
            "googleapiclient",
            "refresh_token",
            "access_token",
            "Popen",
            "system(",
            "shell=True",
            "juicefs sync",
            "juicefs mount",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
