import smartpy as sp

from contracts.contract import bet_contract


def make_commitment(player_address, secret, salt):
    payload = sp.record(player=player_address, secret=secret, salt=salt)
    return sp.blake2b(sp.pack(payload))


@sp.add_test()
def test_security_failures():
    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    charlie = sp.test_account("charlie")

    contract = bet_contract.BinaryAutomatonBet(
        100,
        50,
        16,
        8,
        4,
        4,
    )
    scenario += contract

    alice_secret = 12
    bob_secret = 34
    alice_salt = sp.bytes("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    bob_salt = sp.bytes("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    alice_commitment = make_commitment(alice.address, alice_secret, alice_salt)
    bob_commitment = make_commitment(bob.address, bob_secret, bob_salt)

    contract.join(
        alice_commitment,
        _sender=alice,
        _amount=sp.tez(10),
        _now=sp.timestamp(0),
    )

    contract.join(
        make_commitment(alice.address, 77, sp.bytes("0x01")),
        _sender=alice,
        _amount=sp.tez(10),
        _now=sp.timestamp(1),
        _valid=False,
        _exception="SAME_PLAYER",
    )

    contract.join(
        bob_commitment,
        _sender=bob,
        _amount=sp.tez(10),
        _now=sp.timestamp(2),
    )

    contract.reveal(
        sp.record(secret=999, salt=alice_salt),
        _sender=alice,
        _now=sp.timestamp(3),
        _valid=False,
        _exception="INVALID_COMMITMENT",
    )

    contract.reveal(
        sp.record(secret=alice_secret, salt=alice_salt),
        _sender=alice,
        _now=sp.timestamp(4),
    )

    contract.reveal(
        sp.record(secret=alice_secret, salt=alice_salt),
        _sender=alice,
        _now=sp.timestamp(5),
        _valid=False,
        _exception="ALREADY_REVEALED",
    )

    contract.reveal(
        sp.record(secret=bob_secret, salt=bob_salt),
        _sender=charlie,
        _now=sp.timestamp(6),
        _valid=False,
        _exception="PLAYER_NOT_REGISTERED",
    )


@sp.add_test()
def test_timeout_rewards_revealer():
    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")

    contract = bet_contract.BinaryAutomatonBet(
        100,
        10,
        16,
        8,
        4,
        4,
    )
    scenario += contract

    alice_secret = 123
    bob_secret = 456
    alice_salt = sp.bytes("0x01010101010101010101010101010101")
    bob_salt = sp.bytes("0x02020202020202020202020202020202")

    alice_commitment = make_commitment(alice.address, alice_secret, alice_salt)
    bob_commitment = make_commitment(bob.address, bob_secret, bob_salt)

    contract.join(
        alice_commitment,
        _sender=alice,
        _amount=sp.tez(10),
        _now=sp.timestamp(0),
    )
    contract.join(
        bob_commitment,
        _sender=bob,
        _amount=sp.tez(10),
        _now=sp.timestamp(1),
    )

    contract.reveal(
        sp.record(secret=alice_secret, salt=alice_salt),
        _sender=alice,
        _now=sp.timestamp(2),
    )

    contract.claim_timeout(
        _sender=alice,
        _now=sp.timestamp(20),
    )

    scenario.verify(contract.data.finished)
    scenario.verify(contract.data.winner.unwrap_some() == alice.address)
    scenario.verify(contract.balance == sp.tez(0))


@sp.add_test()
def test_timeout_refunds_both_if_nobody_reveals():
    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")

    contract = bet_contract.BinaryAutomatonBet(
        100,
        10,
        16,
        8,
        4,
        4,
    )
    scenario += contract

    alice_commitment = make_commitment(alice.address, 1, sp.bytes("0x01"))
    bob_commitment = make_commitment(bob.address, 2, sp.bytes("0x02"))

    contract.join(
        alice_commitment,
        _sender=alice,
        _amount=sp.tez(10),
        _now=sp.timestamp(0),
    )
    contract.join(
        bob_commitment,
        _sender=bob,
        _amount=sp.tez(10),
        _now=sp.timestamp(1),
    )

    contract.claim_timeout(
        _sender=alice,
        _now=sp.timestamp(20),
    )

    scenario.verify(contract.data.finished)
    scenario.verify(contract.data.winner.is_none())
    scenario.verify(contract.balance == sp.tez(0))
