import smartpy as sp

from contracts.contract import bet_contract
from contracts.simulation import run_batched_simulation


def make_commitment(player_address, secret, salt):
    payload = sp.record(player=player_address, secret=secret, salt=salt)
    return sp.blake2b(sp.pack(payload))


@sp.add_test()
def test_happy_path_small_batched_game():
    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")

    total_bits = 16
    total_rounds = 8
    init_batch_size = 4
    sim_batch_size = 4

    contract = bet_contract.BinaryAutomatonBet(
        100,
        100,
        total_bits,
        total_rounds,
        init_batch_size,
        sim_batch_size,
    )
    scenario += contract

    alice_secret = 42
    bob_secret = 99
    alice_salt = sp.bytes("0x11111111111111111111111111111111")
    bob_salt = sp.bytes("0x22222222222222222222222222222222")

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
    contract.reveal(
        sp.record(secret=bob_secret, salt=bob_salt),
        _sender=bob,
        _now=sp.timestamp(3),
    )

    for _ in range((total_bits + init_batch_size - 1) // init_batch_size):
        contract.initialize_batch(_sender=alice, _now=sp.timestamp(4))

    for _ in range((total_bits * total_rounds + sim_batch_size - 1) // sim_batch_size):
        contract.simulate_batch(_sender=bob, _now=sp.timestamp(5))

    _, expected = run_batched_simulation(
        alice_secret,
        bob_secret,
        total_bits,
        total_rounds,
        init_batch_size,
        sim_batch_size,
    )
    expected_winner = alice.address if expected == 0 else bob.address

    scenario.verify(contract.data.finished)
    scenario.verify(contract.data.outcome_bit.unwrap_some() == expected)
    scenario.verify(contract.data.winner.unwrap_some() == expected_winner)
    scenario.verify(contract.balance == sp.tez(0))


@sp.add_test()
def test_timeout_refund_before_second_player():
    scenario = sp.test_scenario()

    alice = sp.test_account("alice")

    contract = bet_contract.BinaryAutomatonBet(
        10,
        100,
        16,
        8,
        4,
        4,
    )
    scenario += contract

    secret = 5
    salt = sp.bytes("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    commitment = make_commitment(alice.address, secret, salt)

    contract.join(
        commitment,
        _sender=alice,
        _amount=sp.tez(10),
        _now=sp.timestamp(0),
    )

    contract.claim_timeout(
        _sender=alice,
        _now=sp.timestamp(11),
    )

    scenario.verify(contract.data.finished)
    scenario.verify(contract.data.winner.unwrap_some() == alice.address)
    scenario.verify(contract.balance == sp.tez(0))
