"""Scan release inputs for embedded secrets.

The ROSY OS v1 release contract forbids per-device secrets in anything that
ships: no shared password, no shared API token, no Wi-Fi PSK, no SSH private
key in the repository, the container images or the SD image
(see the image/release design, sections 2.7, 12.1 and 12.2).

This module is the single scanner behind both checks. The repository check
runs in CI over tracked files; the image check (WP-6) will run the same
matchers over a mounted image tree. Keeping one implementation means a
pattern added for one check protects the other.

The scanner is deliberately conservative about placeholders: a config
template that says ``password: <your-wifi-password>`` is the correct thing
for a repository to contain, and flagging it would train people to ignore
the scanner.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    """One suspected secret."""

    path: str
    line_number: int
    kind: str
    excerpt: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.path}:{self.line_number}: {self.kind}: {self.excerpt}"


# A value that is obviously a stand-in rather than a live secret. These are
# what a template, an example config or a doc is supposed to contain.
_PLACEHOLDER = re.compile(
    r"""
    <[^>]*>                     # <your-password>
    | \$\{[^}]*\}               # ${ROSY_WIFI_PSK}
    | \$[A-Z_][A-Z0-9_]*        # $ROSY_WIFI_PSK
    | \bCHANGE_?ME\b
    | \bREPLACE_?ME\b
    | \bYOUR_[A-Z0-9_]+\b
    | \bEXAMPLE\b
    | \bPLACEHOLDER\b
    | \bTODO\b
    | \bFIXME\b
    | \bNone\b
    | \bnull\b
    | ^\s*$
    | ^[x*.\-_]+$               # xxxxxxxx / ******** / --------
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Assignment of a literal value to a secret-ish name. Group "value" is the
# literal; quotes are stripped by the caller.
_ASSIGNMENT = re.compile(
    r"""
    (?P<name>
        [A-Za-z0-9_.\-]*
        (?: passwo?rd | passwd | psk | passphrase | secret | api[_-]?key
          | api[_-]?token | auth[_-]?token | access[_-]?token | bearer )
        [A-Za-z0-9_.\-]*
    )
    \s* [:=] \s*
    (?P<quote>["']?)
    (?P<value>[^"'\s#,;]{6,})
    (?P=quote)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"
)

# wpa_supplicant.conf style, which does not always use a secret-ish name.
_WPA_PSK = re.compile(r"^\s*psk\s*=\s*(?P<value>\S+)", re.IGNORECASE | re.MULTILINE)

# A bare high-entropy token on its own, e.g. a leaked hex API token.
_BARE_TOKEN = re.compile(r"\b(?P<value>[A-Fa-f0-9]{40,}|[A-Za-z0-9+/]{50,}={0,2})\b")

# Public references, stripped before entropy matching: a long documentation URL
# is indistinguishable from base64 to a character-class matcher.
_URL = re.compile(r"\b(?:https?|ftp|git|ssh)://\S+")

# A type annotation, not an assignment of a literal. "bearer: Optional[str]" in
# a function signature is code, not a credential.
_TYPE_EXPRESSION = re.compile(
    r"^(?:Optional|Union|List|Dict|Sequence|Any|Iterable|Mapping|Tuple|Set|Callable"
    r"|str|int|bool|float|bytes|dict|list|set|tuple)\b",
)

# Files whose whole purpose is to describe or detect secrets.
DEFAULT_EXCLUDED_NAMES = frozenset({"secret_scan.py", "test_release_boundary_guards.py"})

DEFAULT_EXCLUDED_SUFFIXES = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".pyc",
        ".stl", ".dae",
        # RViz layouts are serialised Qt window geometry — long hex runs that
        # look like tokens, in a file type that holds no credentials.
        ".rviz",
    }
)


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER.search(value))


def scan_text(path: str, text: str) -> list[Finding]:
    """Return every suspected secret in ``text``.

    Split out from file walking so tests can prove the matchers fire on a
    planted sample — a scanner that only ever returns an empty list passes
    every repository check while protecting nothing.
    """
    findings: list[Finding] = []

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()

        if _PRIVATE_KEY.search(line):
            findings.append(Finding(path, number, "private-key", stripped[:120]))
            continue

        wpa = _WPA_PSK.match(line)
        if wpa and not _is_placeholder(wpa.group("value")):
            findings.append(Finding(path, number, "wifi-psk", stripped[:120]))
            continue

        matched_assignment = False
        for match in _ASSIGNMENT.finditer(line):
            value = match.group("value")
            if _is_placeholder(value) or _TYPE_EXPRESSION.match(value):
                continue
            # A reference to another variable or a path is not a literal secret.
            if value.startswith(("/", "./", "~", "@")):
                continue
            kind = "wifi-psk" if re.search(r"psk|passphrase", match.group("name"), re.IGNORECASE) else "credential"
            findings.append(Finding(path, number, kind, stripped[:120]))
            matched_assignment = True
        if matched_assignment:
            continue

        for match in _BARE_TOKEN.finditer(_URL.sub(" ", line)):
            value = match.group("value")
            # sha256 digests and git revisions are public integrity data, not
            # secrets, and the release manifest is full of them.
            if re.search(r"sha256|digest|revision|checksum|commit|oid|hash", line, re.IGNORECASE):
                continue
            findings.append(Finding(path, number, "high-entropy-token", stripped[:120]))
            break

    return findings


def scan_files(
    paths: Iterable[Path],
    *,
    root: Path,
    excluded_names: Sequence[str] = (),
) -> list[Finding]:
    """Scan each readable text file, reporting paths relative to ``root``."""
    excluded = set(DEFAULT_EXCLUDED_NAMES) | set(excluded_names)
    findings: list[Finding] = []

    for path in paths:
        if path.name in excluded or path.suffix.lower() in DEFAULT_EXCLUDED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: nothing to match against
        findings.extend(scan_text(str(path.relative_to(root)).replace("\\", "/"), text))

    return findings


def iter_tracked_files(root: Path) -> Iterator[Path]:
    """Yield files git tracks under ``root``.

    Tracked files are the right scope: an untracked scratch file is not
    shipped, and .gitignore already keeps build output out.
    """
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=True,
    )
    for name in result.stdout.decode("utf-8").split("\0"):
        if not name:
            continue
        path = root / name
        if path.is_file():
            yield path
