from contracts.utils import SECRET_BITS


def commitment_payload(player_address, secret, salt):
    return {"player": player_address, "secret": secret, "salt": salt}


def result_commitment_payload(player_address, final_bit, salt):
    return {"player": player_address, "final_bit": final_bit, "salt": salt}


def extract_bit(value: int, shift: int) -> int:
    return (value >> shift) & 1


def reduce_shift_128(value: int) -> int:
    return value % SECRET_BITS


def initial_bit(secret1: int, secret2: int, index: int, total_bits: int) -> int:
    half_bits = total_bits // 2

    if index < half_bits:
        return extract_bit(secret1, reduce_shift_128(index))

    return extract_bit(secret2, reduce_shift_128(index - half_bits))


def build_initial_state(secret1: int, secret2: int, total_bits: int) -> list[int]:
    if total_bits <= 0 or total_bits % 2 != 0:
        raise ValueError("total_bits must be a positive even integer")

    return [initial_bit(secret1, secret2, i, total_bits) for i in range(total_bits)]


def step_rule150_ring(state: list[int]) -> list[int]:
    n = len(state)
    out = [0] * n

    for i in range(n):
        out[i] = state[(i - 1) % n] ^ state[i] ^ state[(i + 1) % n]

    return out


def final_result_bit(state: list[int]) -> int:
    center_index = len(state) // 2
    return state[center_index]


def run_full_simulation(
    secret1: int,
    secret2: int,
    total_bits: int,
    total_rounds: int,
) -> tuple[list[int], int]:
    state = build_initial_state(secret1, secret2, total_bits)

    for _ in range(total_rounds):
        state = step_rule150_ring(state)

    return state, final_result_bit(state)


def run_batched_simulation(
    secret1: int,
    secret2: int,
    total_bits: int,
    total_rounds: int,
    init_batch_size: int,
    sim_batch_size: int,
) -> tuple[list[int], int]:
    if init_batch_size <= 0:
        raise ValueError("init_batch_size must be positive")

    if sim_batch_size <= 0:
        raise ValueError("sim_batch_size must be positive")

    state0 = [0] * total_bits
    state1 = [0] * total_bits

    init_cursor = 0
    while init_cursor < total_bits:
        for _ in range(init_batch_size):
            if init_cursor < total_bits:
                state0[init_cursor] = initial_bit(
                    secret1, secret2, init_cursor, total_bits
                )
                init_cursor += 1

    active = 0
    current_round = 0
    current_index = 0

    while current_round < total_rounds:
        for _ in range(sim_batch_size):
            if current_round < total_rounds:
                src = state0 if active == 0 else state1
                dst = state1 if active == 0 else state0

                left_index = total_bits - 1 if current_index == 0 else current_index - 1
                right_index = (
                    0 if current_index + 1 == total_bits else current_index + 1
                )

                dst[current_index] = (
                    src[left_index] ^ src[current_index] ^ src[right_index]
                )
                current_index += 1

                if current_index == total_bits:
                    current_index = 0
                    current_round += 1
                    active = 1 - active

    final_state = state0 if active == 0 else state1
    return final_state, final_result_bit(final_state)
