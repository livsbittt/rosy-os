from __future__ import annotations

import re
from uuid import UUID

import pytest

from deploy.sd.personalization import (
    SHORT_CODE_ALPHABET,
    generate_device_identity,
    generate_short_code,
    validate_device_identity,
)


class DeterministicRng:
    def __init__(self, values: str = "k7m4") -> None:
        self._values = iter(values)

    def choice(self, alphabet: str) -> str:
        value = next(self._values)
        assert value in alphabet
        return value


def test_pinky_name_is_short_human_identity():
    generated = generate_device_identity("pinky_pro", rng=DeterministicRng())

    assert re.fullmatch(r"rosy-pinky-[a-hj-km-np-z2-9]{4}", generated.device_name)
    assert generated.hostname == generated.device_name
    assert UUID(generated.device_uid).version == 4
    assert validate_device_identity(generated) is generated


def test_short_code_alphabet_is_unambiguous_and_complete():
    assert len(SHORT_CODE_ALPHABET) == 31
    assert len(set(SHORT_CODE_ALPHABET)) == 31
    assert set("01ilo").isdisjoint(SHORT_CODE_ALPHABET)


def test_collision_is_regenerated_with_a_bounded_attempt_count():
    rng = DeterministicRng("aaaa" + "k7m4")

    identity = generate_device_identity(
        "pinky_pro",
        rng=rng,
        registered_names={"rosy-pinky-aaaa"},
        max_attempts=2,
    )

    assert identity.device_name == "rosy-pinky-k7m4"


def test_exhausted_collisions_fail_clearly():
    with pytest.raises(RuntimeError, match="unique Pinky device name"):
        generate_device_identity(
            "pinky_pro",
            rng=DeterministicRng("aaaa"),
            registered_names={"rosy-pinky-aaaa"},
            max_attempts=1,
        )


def test_uuid_is_not_derived_from_the_short_name():
    first = generate_device_identity("pinky_pro", rng=DeterministicRng())
    second = generate_device_identity("pinky_pro", rng=DeterministicRng())

    assert first.device_name == second.device_name
    assert first.device_uid != second.device_uid


def test_short_code_rejects_non_positive_length():
    with pytest.raises(ValueError, match="positive"):
        generate_short_code(length=0)
