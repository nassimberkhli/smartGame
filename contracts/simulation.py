from contracts.utils import MASK_128, MIX_A, MIX_B, MIX_C


def commitment_payload(player_address, secret, salt):
    return {"player": player_address, "secret": secret, "salt": salt}


def initial_bit(secret1: int, secret2: int, index: int) -> int:
    x = (
        (secret1 & MASK_128)
        ^ ((secret2 & MASK_128) << 1)
        ^ ((index + 1) * MIX_A)
        ^ (((index + 7) * MIX_B) << 1)
        ^ ((secret1 + secret2 + index) * MIX_C)
    )
    x ^= x >> 17
    x ^= x >> 43
    x ^= x >> 71
    x ^= x >> 97
    return x & 1


def build_initial_state(secret1: int, secret2: int, total_bits: int) -> list[int]:
    return [initial_bit(secret1, secret2, i) for i in range(total_bits)]


def step_rule90_ring(state: list[int]) -> list[int]:
    n = len(state)
    out = [0] * n
    for i in range(n):
        out[i] = state[(i - 1) % n] ^ state[(i + 1) % n]
    return out


def run_full_simulation(secret1: int, secret2: int, total_bits: int, total_rounds: int) -> tuple[list[int], int]:
    state = build_initial_state(secret1, secret2, total_bits)
    for _ in range(total_rounds):
        state = step_rule90_ring(state)
    center_index = total_bits // 2
    return state, state[center_index]


def run_batched_simulation(
    secret1: int,
    secret2: int,
    total_bits: int,
    total_rounds: int,
    init_batch_size: int,
    sim_batch_size: int,
) -> tuple[list[int], int]:
    state0 = [0] * total_bits
    state1 = [0] * total_bits

    init_cursor = 0
    while init_cursor < total_bits:
        for _ in range(init_batch_size):
            if init_cursor < total_bits:
                state0[init_cursor] = initial_bit(secret1, secret2, init_cursor)
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
                right_index = 0 if current_index + 1 == total_bits else current_index + 1

                dst[current_index] = src[left_index] ^ src[right_index]
                current_index += 1

                if current_index == total_bits:
                    current_index = 0
                    current_round += 1
                    active = 1 - active

    final_state = state0 if active == 0 else state1
    center_index = total_bits // 2
    return final_state, final_state[center_index]
