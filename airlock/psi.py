"""Private set intersection: find stuck payments without swapping records.

One-sided Diffie-Hellman PSI, standard library only. Semi-honest model: both
sides are assumed to follow the protocol. A side that lies about its inputs
can make the result wrong; it cannot read the other side's records.

The group is the RFC 3526 2048-bit MODP group. p is a safe prime, p = 2q + 1,
and we work only in the subgroup of quadratic residues, which has prime
order q. Squaring a number lands it in that subgroup.

Items are "reference|amount_kobo" strings.

    Paylane (provider, set Y, secret b)       KudiMart (merchant, set X, secret x)
    A  = sorted [H(y)^b]            ------>
                                    <------   A' = [a^x for a in A]  (same order)
                                              B  = shuffled [H(x)^x]  (credited only)
    S  = {v^b for v in B}
    y_i is stuck  <=>  A'_i not in S

Why it works: H(y)^(b*x) == H(x)^(x*b) exactly when y == x.
What each side learns: Paylane learns which of ITS OWN payments KudiMart has
not credited, and how many credited orders KudiMart has. KudiMart learns only
how many payments Paylane has. Neither sees the other's records.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field

P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74"
    "020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F1437"
    "4FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF05"
    "98DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB"
    "9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF695581718"
    "3995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF",
    16,
)
Q = (P - 1) // 2
ELEMENT_BYTES = 256
ELEMENT_HEX = ELEMENT_BYTES * 2
SECRET_BITS = 320
_DOMAIN = b"airlock-psi-v1"


class PSIError(ValueError):
    pass


def item(reference: str, amount_kobo: int) -> str:
    return f"{reference}|{amount_kobo}"


def hash_to_group(value: str) -> int:
    """Hash an item into the prime-order subgroup.

    Counter-mode SHA-512 gives 2304 bits, reduced mod p (the extra 256 bits
    make the reduction bias negligible), then squared."""
    data = value.encode()
    stream = b"".join(
        hashlib.sha512(_DOMAIN + counter.to_bytes(4, "big") + data).digest()
        for counter in range(5)
    )[: ELEMENT_BYTES + 32]
    h = pow(int.from_bytes(stream, "big") % P, 2, P)
    if h in (0, 1):  # probability ~2^-2000; refuse rather than leak structure
        raise PSIError("item hashed to a degenerate element")
    return h


def new_secret() -> int:
    """A fresh 320-bit exponent. New for every run, never reused."""
    return secrets.randbits(SECRET_BITS) | (1 << (SECRET_BITS - 1))


def check_element(v: object) -> int:
    """Refuse anything that isn't a proper subgroup element.

    pow(v, q, p) == 1 means v is a quadratic residue, so it lies in the
    prime-order subgroup. This blocks small-subgroup attacks, where a
    malicious peer sends an element of tiny order to learn bits of a secret."""
    if type(v) is not int or not 1 < v < P - 1 or pow(v, Q, P) != 1:
        raise PSIError("received an invalid group element")
    return v


def check_elements(values: object, expected: int | None = None) -> list[int]:
    if not isinstance(values, list):
        raise PSIError("expected a list of elements")
    if expected is not None and len(values) != expected:
        raise PSIError(f"expected {expected} elements, got {len(values)}")
    return [check_element(v) for v in values]


def encode_elements(values: list[int]) -> list[str]:
    return [format(v, f"0{ELEMENT_HEX}x") for v in values]


def decode_elements(hexes: object, expected: int | None = None) -> list[int]:
    if not isinstance(hexes, list):
        raise PSIError("expected a list of elements")
    out = []
    for h in hexes:
        if not isinstance(h, str) or len(h) != ELEMENT_HEX:
            raise PSIError("element has the wrong length")
        try:
            out.append(int(h, 16))
        except ValueError:
            raise PSIError("element is not hex") from None
    return check_elements(out, expected)


@dataclass
class Provider:
    """Paylane's side. Holds the secret b and the mapping back to its items."""

    items: list[str]
    secret: int = field(default_factory=new_secret)

    def __post_init__(self) -> None:
        if len(set(self.items)) != len(self.items):
            raise PSIError("duplicate items")
        blinded = [(pow(hash_to_group(i), self.secret, P), i) for i in self.items]
        blinded.sort()  # sorted order hides the original order of the records
        self._a = [v for v, _ in blinded]
        self._order = [i for _, i in blinded]

    def round1(self) -> list[int]:
        return list(self._a)

    def finish(self, a_prime: object, b: object) -> list[str]:
        """Return Paylane's items that KudiMart has not credited."""
        a_prime = check_elements(a_prime, expected=len(self._a))
        b = check_elements(b)
        if len(set(b)) != len(b):
            raise PSIError("duplicate elements in B")
        seen = {pow(v, self.secret, P) for v in b}
        return [i for i, v in zip(self._order, a_prime) if v not in seen]


def merchant_round2(
    a: object, credited: list[str], secret: int | None = None
) -> tuple[list[int], list[int]]:
    """KudiMart's only step. Returns (A', B). B is shuffled so its order
    reveals nothing about KudiMart's records."""
    a = check_elements(a)
    x = secret if secret is not None else new_secret()
    a_prime = [pow(v, x, P) for v in a]
    b = [pow(hash_to_group(i), x, P) for i in set(credited)]
    secrets.SystemRandom().shuffle(b)
    return a_prime, b
