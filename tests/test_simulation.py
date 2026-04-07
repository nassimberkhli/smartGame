from contracts.simulation import run_batched_simulation, run_full_simulation


def test_reference_equivalence():
    cases = [
        (0, 0, 8, 4, 2, 2),
        (1, 0, 8, 5, 3, 2),
        (7, 9, 16, 8, 4, 4),
        (42, 1337, 32, 12, 5, 7),
        (123456789, 987654321, 24, 10, 4, 3),
    ]

    for secret1, secret2, total_bits, total_rounds, init_batch_size, sim_batch_size in cases:
        full_state, full_bit = run_full_simulation(secret1, secret2, total_bits, total_rounds)
        batched_state, batched_bit = run_batched_simulation(
            secret1,
            secret2,
            total_bits,
            total_rounds,
            init_batch_size,
            sim_batch_size,
        )
        assert full_state == batched_state
        assert full_bit == batched_bit


def test_output_is_binary():
    _, bit = run_batched_simulation(5, 6, 16, 8, 4, 4)
    assert bit in (0, 1)


if __name__ == "__main__":
    test_reference_equivalence()
    test_output_is_binary()
    print("test_simulation.py: OK")
