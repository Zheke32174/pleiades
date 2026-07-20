"""Pure Google Drive artifact-bridge contracts for Pleiades.

This module performs no HTTP request, reads no OAuth credential or environment, invokes
no shell or JuiceFS command, and grants no execution or promotion authority. It plans
bounded Drive operations and reduces trusted metadata/notification inputs into
authority-free proposals.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping
from urllib.parse import quote, urlsplit

DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
MAX_ARTIFACT_BYTES = 5 * 1024**4
MAX_NAME_BYTES = 255
MAX_MIME_BYTES = 255
MAX_PROPERTIES = 30
MAX_PROPERTY_BYTES = 124
MAX_HEADER_BYTES = 4096
MAX_PAGE_TOKEN_BYTES = 4096

_SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{8,256}$")
_CHANNEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f\x7f]+$")
_MIME_TYPE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
_GOOGLE_EDITOR_PREFIX = "application/vnd.google-apps."
_ALLOWED_CHANGE_STATES = frozenset({"sync", "change"})
_UPLOAD_FIELDS = (
    "id,name,mimeType,size,sha256Checksum,version,parents,appProperties,"
    "createdTime,modifiedTime"
)
_CHANGE_FIELDS = (
    "nextPageToken,newStartPageToken,"
    "changes(fileId,removed,time,file("
    "id,name,mimeType,size,sha256Checksum,version,parents,appProperties,"
    "createdTime,modifiedTime,trashed))"
)


class DriveBridgeError(ValueError):
    """A Drive bridge contract was violated."""


class DriveNotificationError(DriveBridgeError):
    """A Drive push-notification contract was violated."""


@dataclass(frozen=True)
class DriveArtifactManifest:
    schemaVersion: str
    artifactDigest: str
    sizeBytes: int
    mimeType: str
    fileName: str
    logicalArtifactUri: str
    receiptDigest: str
    bridgeFolderId: str
    authorityCeiling: str
    driveIsMetadataAuthority: bool
    juicefsTargetUri: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_artifact_manifest(
    *,
    artifact_digest: str,
    size_bytes: int,
    mime_type: str,
    file_name: str,
    receipt_digest: str,
    bridge_folder_id: str,
) -> DriveArtifactManifest:
    """Build an immutable artifact identity independent of mutable Drive names."""
    artifact_digest = _sha256_id(artifact_digest, "artifact_digest")
    receipt_digest = _sha256_id(receipt_digest, "receipt_digest")
    size_bytes = _size(size_bytes, "size_bytes")
    mime_type = _mime_type(mime_type, "mime_type")
    file_name = _file_name(file_name)
    bridge_folder_id = _drive_id(bridge_folder_id, "bridge_folder_id")
    checksum = artifact_digest.removeprefix("sha256:")
    logical_uri = f"artifact://sha256/{checksum[:2]}/{checksum}"
    return DriveArtifactManifest(
        schemaVersion="pleiades.drive-artifact-manifest/v1",
        artifactDigest=artifact_digest,
        sizeBytes=size_bytes,
        mimeType=mime_type,
        fileName=file_name,
        logicalArtifactUri=logical_uri,
        receiptDigest=receipt_digest,
        bridgeFolderId=bridge_folder_id,
        authorityCeiling="none",
        driveIsMetadataAuthority=False,
        juicefsTargetUri=logical_uri,
    )


def plan_resumable_upload(
    manifest: DriveArtifactManifest | Mapping[str, Any],
    *,
    pregenerated_file_id: str,
) -> dict[str, Any]:
    """Plan a safely reconcilable Drive files.create resumable upload."""
    manifest_value = _manifest_dict(manifest)
    file_id = _drive_id(pregenerated_file_id, "pregenerated_file_id")
    checksum = manifest_value["artifactDigest"].removeprefix("sha256:")
    receipt = manifest_value["receiptDigest"].removeprefix("sha256:")
    properties = {
        "p.schema": "artifact-v1",
        "p.role": "juicefs-bridge",
        "p.sha256": checksum,
        "p.size": str(manifest_value["sizeBytes"]),
        "p.receipt": receipt,
    }
    _app_properties(properties)
    metadata = {
        "id": file_id,
        "name": manifest_value["fileName"],
        "mimeType": manifest_value["mimeType"],
        "parents": [manifest_value["bridgeFolderId"]],
        "appProperties": properties,
    }
    return {
        "schemaVersion": "pleiades.drive-resumable-upload-request/v1",
        "authority": "transport-only",
        "oauthScope": DRIVE_FILE_SCOPE,
        "method": "POST",
        "path": "/upload/drive/v3/files",
        "query": {
            "uploadType": "resumable",
            "supportsAllDrives": "true",
            "fields": _UPLOAD_FIELDS,
        },
        "headers": {
            "X-Upload-Content-Type": manifest_value["mimeType"],
            "X-Upload-Content-Length": str(manifest_value["sizeBytes"]),
        },
        "body": metadata,
        "artifact": manifest_value,
        "pregeneratedFileId": file_id,
        "safeCreateRetryIdentity": True,
        "performsNetworkRequest": False,
        "storesCredential": False,
    }


def plan_change_feed_poll(
    page_token: str,
    *,
    page_size: int = 1000,
    drive_id: str | None = None,
) -> dict[str, Any]:
    """Plan the exact changes.list request needed after a wake-up notification."""
    token = _bounded_text(page_token, "page_token", maximum=MAX_PAGE_TOKEN_BYTES)
    if (
        not isinstance(page_size, int)
        or isinstance(page_size, bool)
        or not 1 <= page_size <= 1000
    ):
        raise DriveBridgeError("page_size must be an integer in 1..=1000")
    query = {
        "pageToken": token,
        "pageSize": str(page_size),
        "spaces": "drive",
        "includeRemoved": "true",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
        "fields": _CHANGE_FIELDS,
    }
    if drive_id is not None:
        query["driveId"] = _drive_id(drive_id, "drive_id")
    return {
        "schemaVersion": "pleiades.drive-change-feed-request/v1",
        "authority": "observation-only",
        "oauthScope": DRIVE_FILE_SCOPE,
        "method": "GET",
        "path": "/drive/v3/changes",
        "query": query,
        "performsNetworkRequest": False,
        "storesCredential": False,
    }


def admit_change_notification(
    headers: Mapping[str, str],
    *,
    expected_channel_id: str,
    expected_channel_token: str | bytes | None = None,
    expected_resource_id: str | None = None,
) -> dict[str, Any]:
    """Reduce a Drive changes.watch notification to a non-authoritative wake signal."""
    normalized = _normalize_headers(headers)
    expected_channel_id = _channel_id(expected_channel_id, "expected_channel_id")
    channel_id = _channel_id(
        _required_header(normalized, "x-goog-channel-id"),
        "X-Goog-Channel-ID",
    )
    if not hmac.compare_digest(channel_id, expected_channel_id):
        raise DriveNotificationError("Drive notification channel ID does not match")

    resource_id = _channel_id(
        _required_header(normalized, "x-goog-resource-id"),
        "X-Goog-Resource-ID",
    )
    state = _bounded_text(
        _required_header(normalized, "x-goog-resource-state"),
        "X-Goog-Resource-State",
        maximum=32,
    )
    if state not in _ALLOWED_CHANGE_STATES:
        raise DriveNotificationError("only sync/change notifications are accepted in v1")
    if expected_resource_id is not None:
        expected_resource_id = _channel_id(expected_resource_id, "expected_resource_id")
        if not hmac.compare_digest(resource_id, expected_resource_id):
            raise DriveNotificationError("Drive notification resource ID does not match")
    elif state != "sync":
        raise DriveNotificationError(
            "non-sync notification requires a prebound resource ID"
        )

    resource_uri = _changes_resource_uri(
        _required_header(normalized, "x-goog-resource-uri")
    )
    message_number = _positive_int(
        _required_header(normalized, "x-goog-message-number"),
        "X-Goog-Message-Number",
    )

    delivered_token = normalized.get("x-goog-channel-token")
    token_digest: str | None
    if expected_channel_token is None:
        if delivered_token is not None:
            raise DriveNotificationError(
                "unexpected Drive channel token without configured expectation"
            )
        token_digest = None
    else:
        expected_bytes = (
            expected_channel_token.encode("utf-8")
            if isinstance(expected_channel_token, str)
            else expected_channel_token
        )
        if not isinstance(expected_bytes, bytes) or not expected_bytes:
            raise DriveNotificationError("expected channel token is empty")
        if len(expected_bytes) > MAX_HEADER_BYTES:
            raise DriveNotificationError("expected channel token exceeds local bound")
        if delivered_token is None:
            raise DriveNotificationError("Drive channel token is missing")
        delivered_bytes = delivered_token.encode("utf-8")
        if not hmac.compare_digest(delivered_bytes, expected_bytes):
            raise DriveNotificationError("Drive channel token does not match")
        token_digest = _sha256_bytes(expected_bytes)

    expiration = normalized.get("x-goog-channel-expiration")
    if expiration is not None:
        expiration = _bounded_text(
            expiration, "X-Goog-Channel-Expiration", maximum=256
        )

    identity_material = {
        "channelId": channel_id,
        "resourceId": resource_id,
        "resourceUri": resource_uri,
        "resourceState": state,
        "messageNumber": message_number,
        "channelTokenDigest": token_digest,
    }
    return {
        "schemaVersion": "pleiades.drive-change-signal/v1",
        "signalId": _sha256_bytes(_canonical_json_bytes(identity_material)),
        "authorityCeiling": "none",
        "source": "google-drive-changes-watch",
        **identity_material,
        "channelExpiration": expiration,
        "resourceIdentityPrebound": expected_resource_id is not None,
        "notificationContainsChangeDetails": False,
        "notificationOrderAuthoritative": False,
        "requiresChangeFeedReconciliation": True,
    }


def reduce_file_to_ingest_proposal(
    file_resource: Mapping[str, Any],
    *,
    bridge_folder_id: str,
) -> dict[str, Any]:
    """Reduce one fetched Drive file resource to a download-and-rehash proposal."""
    if not isinstance(file_resource, Mapping):
        raise DriveBridgeError("file_resource must be an object")
    bridge_folder_id = _drive_id(bridge_folder_id, "bridge_folder_id")
    file_id = _drive_id(file_resource.get("id"), "file.id")
    name = _file_name(file_resource.get("name"))
    mime_type = _mime_type(file_resource.get("mimeType"), "file.mimeType")
    if mime_type.startswith(_GOOGLE_EDITOR_PREFIX):
        raise DriveBridgeError(
            "native Google Workspace files require a separate export contract"
        )
    if file_resource.get("trashed") is not False:
        raise DriveBridgeError("Drive file must explicitly be non-trashed")

    parents = file_resource.get("parents")
    if (
        not isinstance(parents, list)
        or any(not isinstance(item, str) for item in parents)
        or bridge_folder_id not in parents
    ):
        raise DriveBridgeError("Drive file is not directly parented by bridge folder")

    size = _size(file_resource.get("size"), "file.size")
    checksum = file_resource.get("sha256Checksum")
    if not isinstance(checksum, str) or not _SHA256_HEX.fullmatch(checksum):
        raise DriveBridgeError("file.sha256Checksum must be 64 lowercase hex")
    version = _positive_int(file_resource.get("version"), "file.version")

    properties = _app_properties(file_resource.get("appProperties"))
    required = {
        "p.schema": "artifact-v1",
        "p.role": "juicefs-bridge",
        "p.sha256": checksum,
        "p.size": str(size),
    }
    for key, expected in required.items():
        if properties.get(key) != expected:
            raise DriveBridgeError(f"file.appProperties {key} does not match")
    receipt_hex = properties.get("p.receipt")
    if not isinstance(receipt_hex, str) or not _SHA256_HEX.fullmatch(receipt_hex):
        raise DriveBridgeError("file.appProperties p.receipt is missing or malformed")

    artifact_digest = f"sha256:{checksum}"
    target_uri = f"artifact://sha256/{checksum[:2]}/{checksum}"
    source_uri = f"drive://{quote(file_id, safe='')}@{version}"
    identity = {
        "driveFileId": file_id,
        "driveVersion": version,
        "artifactDigest": artifact_digest,
        "sizeBytes": size,
        "bridgeFolderId": bridge_folder_id,
    }
    return {
        "schemaVersion": "pleiades.drive-ingest-proposal/v1",
        "proposalId": _sha256_bytes(_canonical_json_bytes(identity)),
        "authorityCeiling": "none",
        "source": "google-drive",
        "driveFileId": file_id,
        "driveVersion": version,
        "driveFileName": name,
        "mimeType": mime_type,
        "sizeBytes": size,
        "artifactDigest": artifact_digest,
        "receiptDigest": f"sha256:{receipt_hex}",
        "sourceUri": source_uri,
        "futureJuicefsTargetUri": target_uri,
        "driveIsMetadataAuthority": False,
        "downloadAndRehashRequired": True,
        "localStreamHashMustMatch": [artifact_digest],
        "canonicalMutationAuthorized": False,
    }


def plan_juicefs_handoff(
    ingest_proposal: Mapping[str, Any],
    *,
    staging_root_uri: str = "file:///var/lib/pleiades/drive-staging",
) -> dict[str, Any]:
    """Describe, but do not execute, the later verified Drive-to-JuiceFS handoff."""
    if not isinstance(ingest_proposal, Mapping):
        raise DriveBridgeError("ingest_proposal must be an object")
    if ingest_proposal.get("schemaVersion") != "pleiades.drive-ingest-proposal/v1":
        raise DriveBridgeError("unsupported ingest proposal schema")
    artifact_digest = _sha256_id(
        ingest_proposal.get("artifactDigest"), "ingest_proposal.artifactDigest"
    )
    target_uri = ingest_proposal.get("futureJuicefsTargetUri")
    if not isinstance(target_uri, str) or not target_uri.startswith(
        "artifact://sha256/"
    ):
        raise DriveBridgeError("ingest proposal target URI is invalid")
    if ingest_proposal.get("downloadAndRehashRequired") is not True:
        raise DriveBridgeError("ingest proposal must require local rehash")
    staging_root = _file_uri(staging_root_uri)
    checksum = artifact_digest.removeprefix("sha256:")
    return {
        "schemaVersion": "pleiades.drive-juicefs-handoff-plan/v1",
        "authorityCeiling": "none",
        "performsExecution": False,
        "canonicalMutationAuthorized": False,
        "sourceUri": ingest_proposal.get("sourceUri"),
        "stagingObjectUri": f"{staging_root.rstrip('/')}/{checksum}.part",
        "targetArtifactUri": target_uri,
        "requiredVerification": {
            "expectedArtifactDigest": artifact_digest,
            "expectedSizeBytes": ingest_proposal.get("sizeBytes"),
            "streamHashRequired": True,
            "atomicPublishRequired": True,
            "receiptBeforeDriveCleanup": True,
        },
        "metadataAuthority": "pleiades-sql-pdk",
        "driveRole": "artifact-bridge",
        "juicefsRole": "logical-filesystem",
        "underlyingObjectStoreRole": "r2-or-other-supported-backend",
    }


def _manifest_dict(
    manifest: DriveArtifactManifest | Mapping[str, Any],
) -> dict[str, Any]:
    value = manifest.to_dict() if isinstance(manifest, DriveArtifactManifest) else manifest
    if not isinstance(value, Mapping):
        raise DriveBridgeError("manifest must be an object")
    if value.get("schemaVersion") != "pleiades.drive-artifact-manifest/v1":
        raise DriveBridgeError("unsupported manifest schema")
    rebuilt = build_artifact_manifest(
        artifact_digest=value.get("artifactDigest"),
        size_bytes=value.get("sizeBytes"),
        mime_type=value.get("mimeType"),
        file_name=value.get("fileName"),
        receipt_digest=value.get("receiptDigest"),
        bridge_folder_id=value.get("bridgeFolderId"),
    ).to_dict()
    if dict(value) != rebuilt:
        raise DriveBridgeError("manifest contains altered or unsupported fields")
    return rebuilt


def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        raise DriveNotificationError("headers must be a mapping")
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise DriveNotificationError("header names and values must be strings")
        lowered = key.casefold()
        if lowered in normalized:
            raise DriveNotificationError(
                f"duplicate notification header after case folding: {key}"
            )
        if len(value.encode("utf-8")) > MAX_HEADER_BYTES:
            raise DriveNotificationError(f"notification header {key} exceeds bound")
        normalized[lowered] = value
    return normalized


def _required_header(headers: Mapping[str, str], name: str) -> str:
    value = headers.get(name)
    if value is None:
        raise DriveNotificationError(f"required notification header is missing: {name}")
    return value


def _changes_resource_uri(value: Any) -> str:
    text = _bounded_text(value, "X-Goog-Resource-URI", maximum=2048)
    parsed = urlsplit(text)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.googleapis.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or parsed.path != "/drive/v3/changes"
        or parsed.fragment
    ):
        raise DriveNotificationError("Drive resource URI is not a v3 changes endpoint")
    return text


def _app_properties(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise DriveBridgeError("appProperties must be an object")
    if len(value) > MAX_PROPERTIES:
        raise DriveBridgeError("appProperties exceeds Drive's private-property bound")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str) or not key or not item:
            raise DriveBridgeError("appProperties keys and values must be nonempty strings")
        if len((key + item).encode("utf-8")) > MAX_PROPERTY_BYTES:
            raise DriveBridgeError(
                f"appProperties entry exceeds Drive's byte bound: {key}"
            )
        if not _SAFE_TEXT.fullmatch(key) or not _SAFE_TEXT.fullmatch(item):
            raise DriveBridgeError("appProperties contain control characters")
        result[key] = item
    return result


def _drive_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _DRIVE_ID.fullmatch(value):
        raise DriveBridgeError(f"{label} has an unsupported Drive ID shape")
    return value


def _channel_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _CHANNEL_ID.fullmatch(value):
        raise DriveNotificationError(f"{label} has an unsupported identity shape")
    return value


def _file_name(value: Any) -> str:
    text = _bounded_text(value, "file_name", maximum=MAX_NAME_BYTES)
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise DriveBridgeError("file_name contains a path component")
    return text


def _mime_type(value: Any, label: str) -> str:
    text = _bounded_text(value, label, maximum=MAX_MIME_BYTES)
    if not _MIME_TYPE.fullmatch(text):
        raise DriveBridgeError(f"{label} is not a bounded media type")
    return text


def _sha256_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_ID.fullmatch(value):
        raise DriveBridgeError(f"{label} must be sha256:<64 lowercase hex>")
    return value


def _size(value: Any, label: str) -> int:
    if isinstance(value, str):
        if not value.isdecimal():
            raise DriveBridgeError(f"{label} must be a nonnegative integer")
        value = int(value)
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value > MAX_ARTIFACT_BYTES
    ):
        raise DriveBridgeError(f"{label} is outside the supported artifact bound")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, str):
        if not value.isdecimal():
            raise DriveBridgeError(f"{label} must be a positive integer")
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise DriveBridgeError(f"{label} must be a positive integer")
    return value


def _bounded_text(value: Any, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value:
        raise DriveBridgeError(f"{label} must be a nonempty string")
    if len(value.encode("utf-8")) > maximum:
        raise DriveBridgeError(f"{label} exceeds its byte bound")
    if not _SAFE_TEXT.fullmatch(value):
        raise DriveBridgeError(f"{label} contains control characters")
    return value


def _file_uri(value: Any) -> str:
    text = _bounded_text(value, "staging_root_uri", maximum=2048)
    parsed = urlsplit(text)
    if parsed.scheme != "file" or parsed.netloc or not parsed.path.startswith("/"):
        raise DriveBridgeError("staging_root_uri must be an absolute file URI")
    if parsed.query or parsed.fragment:
        raise DriveBridgeError("staging_root_uri cannot contain query or fragment")
    return text.rstrip("/")


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
