import smartpy as sp

from contracts.contract import bet_contract
from contracts.simulation import run_batched_simulation
from contracts.utils import (
    JOIN_WINDOW_SECONDS,
    PROGRESS_WINDOW_SECONDS,
    REVEAL_WINDOW_SECONDS,
)
from utils.logs import info, section, success


TEST_TOTAL_BITS = 16
TEST_TOTAL_ROUNDS = 8
TEST_INIT_BATCH_SIZE = 4
TEST_SIM_BATCH_SIZE = 8


def make_commitment(player_address, secret, salt):
    payload = sp.record(player=player_address, secret=secret, salt=salt)
    return sp.blake2b(sp.pack(payload))


def make_result_commitment(player_address, final_bit, salt):
    payload = sp.record(player=player_address, final_bit=final_bit, salt=salt)
    return sp.blake2b(sp.pack(payload))


@sp.add_test()
def test_happy_path_batched_game():
    section("Smart contract happy-path test")
    info("Creating SmartPy scenario for a complete and aligned game flow.")

    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")

    contract = bet_contract.BinaryAutomatonBet(
        JOIN_WINDOW_SECONDS,
        REVEAL_WINDOW_SECONDS,
        PROGRESS_WINDOW_SECONDS,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
    )
    scenario += contract

    alice_secret = 42
    bob_secret = 99
    alice_salt = sp.bytes("0x11111111111111111111111111111111")
    bob_salt = sp.bytes("0x22222222222222222222222222222222")
    alice_result_salt = sp.bytes("0x33333333333333333333333333333333")
    bob_result_salt = sp.bytes("0x44444444444444444444444444444444")

    info("Building commitments for both players.")
    alice_commitment = make_commitment(alice.address, alice_secret, alice_salt)
    bob_commitment = make_commitment(bob.address, bob_secret, bob_salt)

    info("Joining both players with the required 10 tez stake.")
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

    info("Revealing both secrets within the reveal window.")
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

    info("Computing the result off-chain.")
    _, expected = run_batched_simulation(
        alice_secret,
        bob_secret,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
    )
    expected_winner = alice.address if expected == 0 else bob.address

    info("Committing the off-chain result from both players.")
    alice_result_commitment = make_result_commitment(
        alice.address, expected, alice_result_salt
    )
    bob_result_commitment = make_result_commitment(
        bob.address, expected, bob_result_salt
    )
    contract.commit_result(
        alice_result_commitment,
        _sender=alice,
        _now=sp.timestamp(10),
    )
    contract.commit_result(
        bob_result_commitment,
        _sender=bob,
        _now=sp.timestamp(11),
    )

    info("Revealing the off-chain result from both players.")
    contract.reveal_result(
        sp.record(final_bit=expected, salt=alice_result_salt),
        _sender=alice,
        _now=sp.timestamp(12),
    )
    contract.reveal_result(
        sp.record(final_bit=expected, salt=bob_result_salt),
        _sender=bob,
        _now=sp.timestamp(13),
    )

    scenario.verify(contract.data.finished)
    scenario.verify(contract.data.outcome_bit.unwrap_some() == expected)
    scenario.verify(contract.data.winner.unwrap_some() == expected_winner)

    if expected == 0:
        scenario.verify(contract.data.player1_credit == sp.nat(20))
        scenario.verify(contract.data.player2_credit == sp.nat(0))
        contract.claim(
            _sender=alice,
            _now=sp.timestamp(300),
        )
    else:
        scenario.verify(contract.data.player1_credit == sp.nat(0))
        scenario.verify(contract.data.player2_credit == sp.nat(20))
        contract.claim(
            _sender=bob,
            _now=sp.timestamp(300),
        )

    scenario.verify(contract.balance == sp.tez(0))

    success("Happy-path SmartPy test completed successfully.")


@sp.add_test()
def test_timeout_refund_before_second_player():
    section("Smart contract join-timeout test")
    info("Creating SmartPy scenario for the single-player timeout refund case.")

    scenario = sp.test_scenario()
    alice = sp.test_account("alice")

    contract = bet_contract.BinaryAutomatonBet(
        10,
        REVEAL_WINDOW_SECONDS,
        PROGRESS_WINDOW_SECONDS,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
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
    scenario.verify(contract.data.player1_credit == sp.nat(10))

    contract.claim(
        _sender=alice,
        _now=sp.timestamp(12),
    )

    scenario.verify(contract.balance == sp.tez(0))

    success("Single-player timeout refund test completed successfully.")


if __name__ == "__main__":
    success("test_contract.py executed. SmartPy registered the contract test scenarios.")
