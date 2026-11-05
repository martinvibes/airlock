"""Typed claims: the only things that may cross the airlock.

There is no free-text field anywhere. Every field is an enum, a bounded int,
or a strict pattern. A message is either exactly one valid claim or it is
refused. Customs calls `validate` on everything it sends and everything it
receives, so a claim is checked twice: once leaving, once arriving.

Wire format, one claim per message:

    AIRLOCK/1 {"kind":"finding","code":"merchant_holds_old_secret_only"}

The JSON after the prefix is canonical (sorted keys, no spaces).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable

WIRE_PREFIX = "AIRLOCK/1 "
MAX_TEXT = 4096
MAX_INT = 10_000_000

PARTIES = ("merchant", "provider")


class ClaimError(ValueError):
    """Why a message is not a valid claim. The text is safe to post: it never
    echoes the input back."""


# ── field types ──────────────────────────────────────────────────────────────

Validator = Callable[[Any], Any]

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ID_RE = re.compile(r"^[a-z0-9-]{1,40}$")
_VERSION_RE = re.compile(r"^v\d{1,3}\.\d{1,3}\.\d{1,3}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DOC_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MENTION_RE = re.compile(r"^\s*@[A-Za-z0-9._-]+[:,]?\s*")


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ClaimError(f"{field} must be a string")
    return value


def _pattern(regex: re.Pattern[str], what: str) -> Validator:
    def check(value: Any, field: str) -> str:
        if not regex.fullmatch(_string(value, field)):
            raise ClaimError(f"{field} must be {what}")
        return value

    return check


def enum(*values: str) -> Validator:
    allowed = frozenset(values)

    def check(value: Any, field: str) -> str:
        if _string(value, field) not in allowed:
            raise ClaimError(f"{field} is not an allowed value")
        return value

    check.allowed = allowed  # type: ignore[attr-defined]
    return check


def count(value: Any, field: str) -> int:
    # bool is a subclass of int in Python; true/false are not counts.
    if type(value) is not int:
        raise ClaimError(f"{field} must be an integer")
    if not 0 <= value <= MAX_INT:
        raise ClaimError(f"{field} must be between 0 and {MAX_INT}")
    return value


def timestamp(value: Any, field: str) -> str:
    if not _TS_RE.fullmatch(_string(value, field)):
        raise ClaimError(f"{field} must look like 2026-11-03T09:40:00Z")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ClaimError(f"{field} is not a real date and time") from None
    return value


ident = _pattern(_ID_RE, "lowercase letters, digits and hyphens, at most 40")
version = _pattern(_VERSION_RE, "a version like v2.14.1")
sha256 = _pattern(_SHA256_RE, "64 lowercase hex characters")
document_id = _pattern(_DOC_ID_RE, "a document id")
party = enum(*PARTIES)

# ── vocabularies ─────────────────────────────────────────────────────────────

# Which side may assert each value. A company's Customs only lets it make
# claims about itself: Paylane cannot "find" something about KudiMart's code.
METRIC_PARTY = {
    "webhook_attempts": "provider",
    "webhook_delivered": "provider",
    "webhook_rejected_401": "provider",
    "webhook_gave_up": "provider",
    "signature_check_failures": "merchant",
    "orders_pending": "merchant",
}
EVENT_PARTY = {
    "signing_secret_rotated": "provider",
    "secret_overlap_window_opened": "provider",
    "verifier_deployed": "merchant",
    "verifier_fix_deployed": "merchant",
}
FINDING_PARTY = {
    "provider_signs_primary_with_new_secret": "provider",
    "provider_still_signs_secondary_with_old_secret": "provider",
    "merchant_verifier_reads_primary_header_only": "merchant",
    "merchant_holds_old_secret_only": "merchant",
    "merchant_verifier_accepts_either_header": "merchant",
}

# ── claim kinds ──────────────────────────────────────────────────────────────

SCHEMA: dict[str, dict[str, Validator]] = {
    "metric": {
        "name": enum(*METRIC_PARTY),
        "value": count,
        "window_start": timestamp,
        "window_end": timestamp,
    },
    "timeline_event": {
        "event": enum(*EVENT_PARTY),
        "at": timestamp,
        "version": version,
    },
    "finding": {"code": enum(*FINDING_PARTY)},
    "reconcile_request": {
        "run_id": ident,
        "window_start": timestamp,
        "window_end": timestamp,
    },
    "reconcile_consent": {"run_id": ident},
    "psi_round1": {
        "run_id": ident,
        "document_id": document_id,
        "sha256": sha256,
        "count": count,
    },
    "psi_round2": {
        "run_id": ident,
        "document_id": document_id,
        "sha256": sha256,
        "count": count,
    },
    "reconcile_result": {"run_id": ident, "stuck_count": count},
    "replay_proposal": {"proposal_id": ident, "run_id": ident, "stuck_count": count},
    "signoff": {"proposal_id": ident, "party": party},
    "replay_result": {
        "proposal_id": ident,
        "attempted": count,
        "delivered": count,
        "rejected": count,
    },
    "incident_closed": {"proposal_id": ident, "run_id": ident, "stuck_count": count},
}

# Kinds only one side may send. Others depend on a field (see `sender_party`).
KIND_PARTY = {
    "reconcile_request": "provider",
    "reconcile_consent": "merchant",
    "psi_round1": "provider",
    "psi_round2": "merchant",
    "reconcile_result": "provider",
    "replay_proposal": "provider",
    "replay_result": "provider",
    "incident_closed": "provider",
}

# Kinds an investigator or engineer may `propose`. The rest are protocol
# messages that only Customs itself creates.
EVIDENCE_KINDS = frozenset({"metric", "timeline_event", "finding"})


def sender_party(claim: dict[str, Any]) -> str:
    """The only party allowed to send this claim."""
    kind = claim["kind"]
    if kind in KIND_PARTY:
        return KIND_PARTY[kind]
    if kind == "metric":
        return METRIC_PARTY[claim["name"]]
    if kind == "timeline_event":
        return EVENT_PARTY[claim["event"]]
    if kind == "finding":
        return FINDING_PARTY[claim["code"]]
    if kind == "signoff":
        return claim["party"]
    raise ClaimError("unknown kind")


# ── parsing ──────────────────────────────────────────────────────────────────


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ClaimError("duplicate field")
        out[key] = value
    return out


def _no_constants(_: str) -> Any:
    raise ClaimError("NaN and Infinity are not allowed")


def _no_floats(_: str) -> Any:
    raise ClaimError("numbers must be integers")


def parse_json(text: str) -> dict[str, Any]:
    """Parse exactly one JSON object and nothing else."""
    if len(text) > MAX_TEXT:
        raise ClaimError("message is too long")
    try:
        obj = json.loads(
            text,
            object_pairs_hook=_no_duplicates,
            parse_constant=_no_constants,
            parse_float=_no_floats,
        )
    except ClaimError:
        raise
    except (ValueError, RecursionError):
        raise ClaimError("not a single JSON object") from None
    if not isinstance(obj, dict):
        raise ClaimError("not a JSON object")
    return obj


def validate(obj: Any, *, sent_by: str | None = None) -> dict[str, Any]:
    """Return a clean copy of `obj` if it is a valid claim, else raise.

    `sent_by` ("merchant" or "provider") additionally checks that this side
    is allowed to make the claim."""
    if not isinstance(obj, dict):
        raise ClaimError("not a JSON object")
    kind = obj.get("kind")
    if not isinstance(kind, str) or kind not in SCHEMA:
        raise ClaimError("unknown kind")
    fields = SCHEMA[kind]
    keys = set(obj) - {"kind"}
    if keys - set(fields):
        raise ClaimError(f"unexpected field for {kind}")
    if set(fields) - keys:
        raise ClaimError(f"missing field for {kind}")
    clean = {"kind": kind}
    for name, check in fields.items():
        clean[name] = check(obj[name], name)
    if "window_start" in clean and clean["window_start"] >= clean["window_end"]:
        raise ClaimError("window_start must be before window_end")
    if kind == "replay_result" and (
        clean["delivered"] + clean["rejected"] > clean["attempted"]
    ):
        raise ClaimError("delivered plus rejected exceeds attempted")
    if sent_by is not None and sender_party(clean) != sent_by:
        raise ClaimError(f"the {sent_by} side cannot make this claim")
    return clean


def strip_mention(text: str) -> str:
    """Drop one leading @mention, as chat apps prepend it when you address
    an agent. Nothing else is tolerated around a claim."""
    return _MENTION_RE.sub("", text, count=1)


def canonical(claim: dict[str, Any]) -> str:
    return json.dumps(claim, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def encode(claim: dict[str, Any]) -> str:
    """The wire form. Always re-validates, so nothing unvalidated is encoded."""
    return WIRE_PREFIX + canonical(validate(claim))


def decode(text: str, *, sent_by: str | None = None) -> dict[str, Any]:
    """Parse a wire message: optional leading mention, the prefix, one object."""
    body = strip_mention(text).strip()
    if not body.startswith(WIRE_PREFIX):
        raise ClaimError("not a typed claim")
    return validate(parse_json(body[len(WIRE_PREFIX) :]), sent_by=sent_by)


def parse_proposal(text: str, *, sent_by: str) -> dict[str, Any]:
    """Parse the claim part of `propose ...`: a JSON object, with or without
    the wire prefix. Only evidence kinds may be proposed by people or agents."""
    body = text.strip()
    if body.startswith(WIRE_PREFIX):
        body = body[len(WIRE_PREFIX) :]
    claim = validate(parse_json(body), sent_by=sent_by)
    if claim["kind"] not in EVIDENCE_KINDS:
        raise ClaimError(f"{claim['kind']} is created by Customs, not proposed")
    return claim
