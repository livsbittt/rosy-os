"""Device-neutral helpers for per-card ROSY OS personalization."""

from __future__ import annotations

from dataclasses import dataclass
import re
import secrets
from typing import Collection, Protocol
from uuid import UUID, uuid4


SHORT_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
DEVICE_NAME_PATTERN = re.compile(r"^rosy-pinky-[a-hj-km-np-z2-9]{4}$")


class ChoiceSource(Protocol):
    def choice(self, alphabet: str) -> str: ...


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_uid: str
    device_name: str
    hostname: str
    model: str


def generate_short_code(
    *, length: int = 4, rng: ChoiceSource = secrets
) -> str:
    if length <= 0:
        raise ValueError("short-code length must be positive")
    return "".join(rng.choice(SHORT_CODE_ALPHABET) for _ in range(length))


def validate_device_identity(identity: DeviceIdentity) -> DeviceIdentity:
    if identity.model != "pinky_pro":
        raise ValueError("unsupported device model")
    if not DEVICE_NAME_PATTERN.fullmatch(identity.device_name):
        raise ValueError("invalid Pinky device name")
    if identity.hostname != identity.device_name:
        raise ValueError("hostname must equal the public device name")
    parsed = UUID(identity.device_uid)
    if parsed.version != 4:
        raise ValueError("device_uid must be UUIDv4")
    return identity


def generate_device_identity(
    model: str,
    *,
    rng: ChoiceSource = secrets,
    registered_names: Collection[str] = (),
    max_attempts: int = 32,
) -> DeviceIdentity:
    if model != "pinky_pro":
        raise ValueError("unsupported device model")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    existing = set(registered_names)
    for _ in range(max_attempts):
        device_name = f"rosy-pinky-{generate_short_code(rng=rng)}"
        if device_name in existing:
            continue
        return validate_device_identity(
            DeviceIdentity(
                device_uid=str(uuid4()),
                device_name=device_name,
                hostname=device_name,
                model=model,
            )
        )
    raise RuntimeError(
        f"could not allocate a unique Pinky device name after {max_attempts} attempts"
    )
