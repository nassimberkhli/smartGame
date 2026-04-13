import smartpy as sp

from contracts.contract import bet_contract
from contracts.simulation import run_batched_simulation
from contracts.utils import (
    JOIN_WINDOW_SECONDS,
    PROGRESS_WINDOW_SECONDS,
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
def test_security_failures():
    section("Smart contract security failure tests")
    info("Creating SmartPy scenario for invalid actions and commitment enforcement.")

    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    charlie = sp.test_account("charlie")

    contract = bet_contract.BinaryAutomatonBet(
        JOIN_WINDOW_SECONDS,
        10,
        PROGRESS_WINDOW_SECONDS,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
    )
    scenario += contract

    alice_secret = 12
    bob_secret = 34
    alice_salt = sp.bytes("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    bob_salt = sp.bytes("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    alice_result_salt = sp.bytes("0xcccccccccccccccccccccccccccccccc")
    bob_result_salt = sp.bytes("0xdddddddddddddddddddddddddddddddd")

    alice_commitment = make_commitment(alice.address, alice_secret, alice_salt)
    bob_commitment = make_commitment(bob.address, bob_secret, bob_salt)

    info("Alice joins first.")
    contract.join(
        alice_commitment,
        _sender=alice,
        _amount=sp.tez(10),
        _now=sp.timestamp(0),
    )

    info("Rejecting a second join attempt from the same player.")
    contract.join(
        make_commitment(alice.address, 77, sp.bytes("0x01")),
        _sender=alice,
        _amount=sp.tez(10),
        _now=sp.timestamp(1),
        _valid=False,
        _exception="SAME_PLAYER",
    )

    info("Rejecting an invalid stake amount.")
    contract.join(
        bob_commitment,
        _sender=bob,
        _amount=sp.tez(9),
        _now=sp.timestamp(1),
        _valid=False,
        _exception="INVALID_STAKE",
    )

    info("Bob joins successfully.")
    contract.join(
        bob_commitment,
        _sender=bob,
        _amount=sp.tez(10),
        _now=sp.timestamp(2),
    )

    info("Rejecting an invalid reveal from Alice.")
    contract.reveal(
        sp.record(secret=999, salt=alice_salt),
        _sender=alice,
        _now=sp.timestamp(3),
        _valid=False,
        _exception="INVALID_COMMITMENT",
    )

    info("Accepting Alice's valid reveal.")
    contract.reveal(
        sp.record(secret=alice_secret, salt=alice_salt),
        _sender=alice,
        _now=sp.timestamp(4),
    )

    info("Rejecting a duplicate reveal from Alice.")
    contract.reveal(
        sp.record(secret=alice_secret, salt=alice_salt),
        _sender=alice,
        _now=sp.timestamp(5),
        _valid=False,
        _exception="ALREADY_REVEALED",
    )

    info("Rejecting a reveal from a non-registered player.")
    contract.reveal(
        sp.record(secret=bob_secret, salt=bob_salt),
        _sender=charlie,
        _now=sp.timestamp(6),
        _valid=False,
        _exception="PLAYER_NOT_REGISTERED",
    )

    info("Rejecting a reveal after the reveal deadline.")
    contract.reveal(
        sp.record(secret=bob_secret, salt=bob_salt),
        _sender=bob,
        _now=sp.timestamp(20),
        _valid=False,
        _exception="REVEAL_PHASE_OVER",
    )

    info("Preparing a fresh game to check result commitment failures.")
    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    charlie = sp.test_account("charlie")

    contract = bet_contract.BinaryAutomatonBet(
        JOIN_WINDOW_SECONDS,
        60,
        PROGRESS_WINDOW_SECONDS,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
    )
    scenario += contract

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

    _, expected = run_batched_simulation(
        alice_secret,
        bob_secret,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
    )

    contract.commit_result(
        make_result_commitment(alice.address, expected, alice_result_salt),
        _sender=alice,
        _now=sp.timestamp(4),
    )
    contract.commit_result(
        make_result_commitment(bob.address, expected, bob_result_salt),
        _sender=bob,
        _now=sp.timestamp(5),
    )

    info("Rejecting an invalid result reveal from Alice.")
    contract.reveal_result(
        sp.record(final_bit=sp.nat(1), salt=alice_result_salt),
        _sender=alice,
        _now=sp.timestamp(6),
        _valid=False,
        _exception="INVALID_COMMITMENT",
    )

    info("Rejecting a result reveal from a non-registered player.")
    contract.reveal_result(
        sp.record(final_bit=expected, salt=bob_result_salt),
        _sender=charlie,
        _now=sp.timestamp(7),
        _valid=False,
        _exception="PLAYER_NOT_REGISTERED",
    )

    success("Security failure checks completed successfully.")


@sp.add_test()
def test_timeout_rewards_revealer():
    section("Smart contract reveal-timeout reward test")
    info("Creating SmartPy scenario where only one player reveals before timeout.")

    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")

    contract = bet_contract.BinaryAutomatonBet(
        JOIN_WINDOW_SECONDS,
        10,
        PROGRESS_WINDOW_SECONDS,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
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
    scenario.verify(contract.data.player1_credit == sp.nat(20))

    contract.claim(
        _sender=alice,
        _now=sp.timestamp(21),
    )

    scenario.verify(contract.balance == sp.tez(0))

    success("Reveal-timeout reward test completed successfully.")


@sp.add_test()
def test_progress_timeout_refunds_both_players():
    section("Smart contract progress-timeout refund test")
    info("Creating SmartPy scenario where both players reveal but the result workflow stops progressing.")

    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")

    contract = bet_contract.BinaryAutomatonBet(
        JOIN_WINDOW_SECONDS,
        60,
        10,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
    )
    scenario += contract

    alice_secret = 1
    bob_secret = 2
    alice_salt = sp.bytes("0x01")
    bob_salt = sp.bytes("0x02")

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

    contract.claim_timeout(
        _sender=alice,
        _now=sp.timestamp(20),
    )

    scenario.verify(contract.data.finished)
    scenario.verify(contract.data.winner.is_none())
    scenario.verify(contract.data.player1_credit == sp.nat(10))
    scenario.verify(contract.data.player2_credit == sp.nat(10))

    contract.claim(
        _sender=alice,
        _now=sp.timestamp(21),
    )
    contract.claim(
        _sender=bob,
        _now=sp.timestamp(22),
    )

    scenario.verify(contract.balance == sp.tez(0))

    success("Progress-timeout refund test completed successfully.")


@sp.add_test()
def test_result_mismatch_refund_path():
    section("Smart contract mismatch timeout test")
    info("Creating SmartPy scenario where players commit conflicting off-chain results.")

    scenario = sp.test_scenario()

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")

    contract = bet_contract.BinaryAutomatonBet(
        JOIN_WINDOW_SECONDS,
        60,
        10,
        TEST_TOTAL_BITS,
        TEST_TOTAL_ROUNDS,
        TEST_INIT_BATCH_SIZE,
        TEST_SIM_BATCH_SIZE,
    )
    scenario += contract

    alice_secret = 5
    bob_secret = 6
    alice_salt = sp.bytes("0x01010101010101010101010101010101")
    bob_salt = sp.bytes("0x02020202020202020202020202020202")
    alice_result_salt = sp.bytes("0x03030303030303030303030303030303")
    bob_result_salt = sp.bytes("0x04040404040404040404040404040404")

    contract.join(
        make_commitment(alice.address, alice_secret, alice_salt),
        _sender=alice,
        _amount=sp.tez(10),
        _now=sp.timestamp(0),
    )
    contract.join(
        make_commitment(bob.address, bob_secret, bob_salt),
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

    contract.commit_result(
        make_result_commitment(alice.address, 0, alice_result_salt),
        _sender=alice,
        _now=sp.timestamp(4),
    )
    contract.commit_result(
        make_result_commitment(bob.address, 1, bob_result_salt),
        _sender=bob,
        _now=sp.timestamp(5),
    )

    contract.reveal_result(
        sp.record(final_bit=0, salt=alice_result_salt),
        _sender=alice,
        _now=sp.timestamp(6),
    )
    contract.reveal_result(
        sp.record(final_bit=1, salt=bob_result_salt),
        _sender=bob,
        _now=sp.timestamp(7),
        _valid=False,
        _exception="RESULT_MISMATCH",
    )

    contract.claim_timeout(
        _sender=alice,
        _now=sp.timestamp(20),
    )

    scenario.verify(contract.data.finished)
    scenario.verify(contract.data.winner.is_none())
    scenario.verify(contract.data.player1_credit == sp.nat(10))
    scenario.verify(contract.data.player2_credit == sp.nat(10))

    success("Mismatch timeout path completed successfully.")


if __name__ == "__main__":
    success("test_security.py executed. SmartPy registered the security test scenarios.")
