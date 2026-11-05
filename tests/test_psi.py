import random

import pytest

from airlock import psi
from airlock.psi import P, PSIError


def items(n, start=0):
    return [psi.item(f"PL-{i:06d}", 100_000 + i) for i in range(start, start + n)]


def test_finds_exactly_the_missing_items():
    paid = items(60)
    stuck = set(random.Random(1).sample(paid, 7))
    credited = [i for i in paid if i not in stuck] + items(15, start=1000)  # other providers
    prov = psi.Provider(paid)
    a_prime, b = psi.merchant_round2(prov.round1(), credited)
    assert set(prov.finish(a_prime, b)) == stuck


def test_zero_stuck_after_fix():
    paid = items(20)
    prov = psi.Provider(paid)
    assert prov.finish(*psi.merchant_round2(prov.round1(), paid)) == []


def test_amount_is_part_of_the_item():
    prov = psi.Provider([psi.item("PL-1", 500)])
    a_prime, b = psi.merchant_round2(prov.round1(), [psi.item("PL-1", 499)])
    assert prov.finish(a_prime, b) == [psi.item("PL-1", 500)]


def test_round1_hides_order_and_values():
    paid = items(10)
    a = psi.Provider(paid).round1()
    assert a == sorted(a)
    assert all(psi.hash_to_group(i) not in a for i in paid)


def test_fresh_secret_each_run():
    paid = items(5)
    assert psi.Provider(paid).round1() != psi.Provider(paid).round1()


def test_elements_are_in_the_subgroup():
    for i in items(5):
        h = psi.hash_to_group(i)
        assert 1 < h < P - 1 and pow(h, psi.Q, P) == 1


@pytest.mark.parametrize("bad", [0, 1, P - 1, P, P + 5, -3, True, "5"])
def test_invalid_elements_rejected(bad):
    with pytest.raises(PSIError):
        psi.check_element(bad)


def test_legendre_matches_eulers_criterion():
    rng = random.Random(7)
    for _ in range(40):
        v = rng.randrange(2, P - 1)
        assert (psi.legendre(v) == 1) == (pow(v, psi.Q, P) == 1)


def test_non_residue_rejected():
    # 2 is not a QR mod this p? find any non-residue to prove the check bites.
    v = next(x for x in range(2, 100) if pow(x, psi.Q, P) != 1)
    with pytest.raises(PSIError):
        psi.check_element(v)


def test_count_mismatch_rejected():
    prov = psi.Provider(items(5))
    a_prime, b = psi.merchant_round2(prov.round1(), items(5))
    with pytest.raises(PSIError, match="expected 5"):
        prov.finish(a_prime[:-1], b)


def test_hex_encoding_round_trip_and_length_check():
    vals = psi.Provider(items(3)).round1()
    enc = psi.encode_elements(vals)
    assert all(len(h) == psi.ELEMENT_HEX for h in enc)
    assert psi.decode_elements(enc, expected=3) == vals
    with pytest.raises(PSIError):
        psi.decode_elements([enc[0][1:]])
    with pytest.raises(PSIError):
        psi.decode_elements(enc, expected=4)


def test_duplicate_items_rejected():
    with pytest.raises(PSIError):
        psi.Provider([psi.item("PL-1", 1)] * 2)
