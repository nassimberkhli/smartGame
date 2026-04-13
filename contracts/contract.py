import smartpy as sp


@sp.module
def bet_contract():
    def state_key(params):
        return params.buffer * params.total_bits + params.index

    def nat_bit_from_raw(raw_value):
        bit = sp.nat(0)
        if raw_value == 0:
            bit = sp.nat(0)
        else:
            bit = sp.nat(1)
        return bit

    def extract_bit(params):
        shifted_value = params.value >> params.shift
        reduced = shifted_value - ((shifted_value >> 1) << 1)
        return nat_bit_from_raw(reduced)

    def reduce_shift_128(value):
        return sp.as_nat(value - ((value >> 7) << 7))

    def initial_bit(params):
        half_bits = params.total_bits >> 1

        bit = sp.nat(0)
        if params.index < half_bits:
            bit = extract_bit(
                sp.record(
                    value=params.secret1,
                    shift=reduce_shift_128(params.index),
                )
            )
        else:
            bit = extract_bit(
                sp.record(
                    value=params.secret2,
                    shift=reduce_shift_128(sp.as_nat(params.index - half_bits)),
                )
            )

        return bit

    def commitment_of(params):
        payload = sp.record(
            player=params.player,
            secret=params.secret,
            salt=params.salt,
        )
        return sp.blake2b(sp.pack(payload))

    class BinaryAutomatonBet(sp.Contract):
        def __init__(
            self,
            join_window_seconds,
            reveal_window_seconds,
            progress_window_seconds,
            total_bits,
            total_rounds,
            init_batch_size,
            sim_batch_size,
        ):
            self.data.player1 = None
            self.data.player2 = None
            self.data.player1_commitment = None
            self.data.player2_commitment = None
            self.data.player1_secret = None
            self.data.player2_secret = None
            self.data.player1_revealed = False
            self.data.player2_revealed = False
            self.data.join_deadline = None
            self.data.reveal_deadline = None
            self.data.progress_deadline = None
            self.data.join_window_seconds = join_window_seconds
            self.data.reveal_window_seconds = reveal_window_seconds
            self.data.progress_window_seconds = progress_window_seconds
            self.data.phase = sp.nat(0)
            self.data.finished = False
            self.data.winner = None
            self.data.outcome_bit = None
            self.data.total_bits = total_bits
            self.data.total_rounds = total_rounds
            self.data.init_batch_size = init_batch_size
            self.data.sim_batch_size = sim_batch_size
            self.data.init_cursor = sp.nat(0)
            self.data.current_round = sp.nat(0)
            self.data.current_index = sp.nat(0)
            self.data.active_buffer = sp.nat(0)
            self.data.states = sp.big_map()

            sp.cast(
                self.data,
                sp.record(
                    player1=sp.option[sp.address],
                    player2=sp.option[sp.address],
                    player1_commitment=sp.option[sp.bytes],
                    player2_commitment=sp.option[sp.bytes],
                    player1_secret=sp.option[sp.nat],
                    player2_secret=sp.option[sp.nat],
                    player1_revealed=sp.bool,
                    player2_revealed=sp.bool,
                    join_deadline=sp.option[sp.timestamp],
                    reveal_deadline=sp.option[sp.timestamp],
                    progress_deadline=sp.option[sp.timestamp],
                    join_window_seconds=sp.int,
                    reveal_window_seconds=sp.int,
                    progress_window_seconds=sp.int,
                    phase=sp.nat,
                    finished=sp.bool,
                    winner=sp.option[sp.address],
                    outcome_bit=sp.option[sp.nat],
                    total_bits=sp.nat,
                    total_rounds=sp.nat,
                    init_batch_size=sp.nat,
                    sim_batch_size=sp.nat,
                    init_cursor=sp.nat,
                    current_round=sp.nat,
                    current_index=sp.nat,
                    active_buffer=sp.nat,
                    states=sp.big_map[sp.nat, sp.nat],
                ),
            )

        @sp.entrypoint
        def join(self, commitment):
            sp.cast(commitment, sp.bytes)

            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(0), "BAD_PHASE"
            assert sp.amount == sp.tez(10), "INVALID_STAKE"
            assert self.data.total_bits > 0, "INVALID_TOTAL_BITS"
            assert ((self.data.total_bits >> 1) << 1) == self.data.total_bits, (
                "INVALID_TOTAL_BITS"
            )
            assert self.data.total_rounds > 0, "INVALID_TOTAL_ROUNDS"
            assert self.data.init_batch_size > 0, "INVALID_BATCH_SIZE"
            assert self.data.sim_batch_size > 0, "INVALID_BATCH_SIZE"

            if self.data.player1.is_none():
                self.data.player1 = sp.Some(sp.sender)
                self.data.player1_commitment = sp.Some(commitment)
                self.data.join_deadline = sp.Some(
                    sp.add_seconds(sp.now, self.data.join_window_seconds)
                )
            else:
                assert self.data.player2.is_none(), "GAME_FULL"
                assert sp.now <= self.data.join_deadline.unwrap_some(), (
                    "JOIN_PHASE_OVER"
                )
                assert sp.sender != self.data.player1.unwrap_some(), "SAME_PLAYER"

                self.data.player2 = sp.Some(sp.sender)
                self.data.player2_commitment = sp.Some(commitment)
                self.data.reveal_deadline = sp.Some(
                    sp.add_seconds(sp.now, self.data.reveal_window_seconds)
                )

        @sp.entrypoint
        def reveal(self, params):
            sp.cast(params, sp.record(secret=sp.nat, salt=sp.bytes))

            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(0), "BAD_PHASE"
            assert params.secret < (1 << 128), "SECRET_TOO_LARGE"
            assert self.data.player2.is_some(), "SECOND_PLAYER_MISSING"
            assert self.data.reveal_deadline.is_some(), "SECOND_PLAYER_MISSING"
            assert sp.now <= self.data.reveal_deadline.unwrap_some(), (
                "REVEAL_PHASE_OVER"
            )

            if sp.sender == self.data.player1.unwrap_some():
                assert not self.data.player1_revealed, "ALREADY_REVEALED"
                assert (
                    commitment_of(
                        sp.record(
                            player=sp.sender, secret=params.secret, salt=params.salt
                        )
                    )
                    == self.data.player1_commitment.unwrap_some()
                ), "INVALID_COMMITMENT"
                self.data.player1_secret = sp.Some(params.secret)
                self.data.player1_revealed = True
            else:
                assert sp.sender == self.data.player2.unwrap_some(), (
                    "PLAYER_NOT_REGISTERED"
                )
                assert not self.data.player2_revealed, "ALREADY_REVEALED"
                assert (
                    commitment_of(
                        sp.record(
                            player=sp.sender, secret=params.secret, salt=params.salt
                        )
                    )
                    == self.data.player2_commitment.unwrap_some()
                ), "INVALID_COMMITMENT"
                self.data.player2_secret = sp.Some(params.secret)
                self.data.player2_revealed = True

            if self.data.player1_revealed:
                if self.data.player2_revealed:
                    self.data.phase = sp.nat(1)
                    self.data.progress_deadline = sp.Some(
                        sp.add_seconds(sp.now, self.data.progress_window_seconds)
                    )

        @sp.entrypoint
        def initialize_batch(self):
            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(1), "BAD_PHASE"
            assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
            assert sp.now <= self.data.progress_deadline.unwrap_some(), (
                "REVEAL_PHASE_OVER"
            )

            for _ in range(self.data.init_batch_size):
                if self.data.init_cursor < self.data.total_bits:
                    raw_bit = initial_bit(
                        sp.record(
                            secret1=self.data.player1_secret.unwrap_some(),
                            secret2=self.data.player2_secret.unwrap_some(),
                            index=self.data.init_cursor,
                            total_bits=self.data.total_bits,
                        )
                    )

                    bit = sp.nat(0)
                    if raw_bit == 0:
                        bit = sp.nat(0)
                    else:
                        bit = sp.nat(1)

                    key0 = state_key(
                        sp.record(
                            buffer=sp.nat(0),
                            total_bits=self.data.total_bits,
                            index=self.data.init_cursor,
                        )
                    )

                    self.data.states[key0] = bit
                    self.data.init_cursor += 1

            self.data.progress_deadline = sp.Some(
                sp.add_seconds(sp.now, self.data.progress_window_seconds)
            )

            if self.data.init_cursor == self.data.total_bits:
                self.data.phase = sp.nat(2)
                self.data.current_round = sp.nat(0)
                self.data.current_index = sp.nat(0)
                self.data.active_buffer = sp.nat(0)

        @sp.entrypoint
        def simulate_batch(self):
            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(2), "BAD_PHASE"
            assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
            assert sp.now <= self.data.progress_deadline.unwrap_some(), (
                "REVEAL_PHASE_OVER"
            )

            for _ in range(self.data.sim_batch_size):
                if self.data.current_round < self.data.total_rounds:
                    source_buffer = self.data.active_buffer

                    target_buffer = sp.nat(0)
                    if self.data.active_buffer == sp.nat(0):
                        target_buffer = sp.nat(1)
                    else:
                        target_buffer = sp.nat(0)

                    left_index = sp.nat(0)
                    if self.data.current_index == sp.nat(0):
                        left_index = sp.as_nat(self.data.total_bits - 1)
                    else:
                        left_index = sp.as_nat(self.data.current_index - 1)

                    center_index = self.data.current_index
                    next_index = self.data.current_index + 1

                    right_index = sp.nat(0)
                    if next_index == self.data.total_bits:
                        right_index = sp.nat(0)
                    else:
                        right_index = next_index

                    left_key = state_key(
                        sp.record(
                            buffer=source_buffer,
                            total_bits=self.data.total_bits,
                            index=left_index,
                        )
                    )
                    center_key = state_key(
                        sp.record(
                            buffer=source_buffer,
                            total_bits=self.data.total_bits,
                            index=center_index,
                        )
                    )
                    right_key = state_key(
                        sp.record(
                            buffer=source_buffer,
                            total_bits=self.data.total_bits,
                            index=right_index,
                        )
                    )

                    left_value = self.data.states.get(left_key, default=sp.nat(0))
                    center_value = self.data.states.get(center_key, default=sp.nat(0))
                    right_value = self.data.states.get(right_key, default=sp.nat(0))

                    left_center_value = sp.nat(0)
                    if left_value == center_value:
                        left_center_value = sp.nat(0)
                    else:
                        left_center_value = sp.nat(1)

                    new_value = sp.nat(0)
                    if left_center_value == right_value:
                        new_value = sp.nat(0)
                    else:
                        new_value = sp.nat(1)

                    target_key = state_key(
                        sp.record(
                            buffer=target_buffer,
                            total_bits=self.data.total_bits,
                            index=self.data.current_index,
                        )
                    )

                    self.data.states[target_key] = new_value
                    self.data.current_index = next_index

                    if self.data.current_index == self.data.total_bits:
                        self.data.current_index = sp.nat(0)
                        self.data.current_round += 1
                        self.data.active_buffer = target_buffer

                        if self.data.current_round == self.data.total_rounds:
                            center_index = self.data.total_bits >> 1
                            center_key = state_key(
                                sp.record(
                                    buffer=self.data.active_buffer,
                                    total_bits=self.data.total_bits,
                                    index=center_index,
                                )
                            )

                            final_bit_raw = self.data.states.get(
                                center_key,
                                default=sp.nat(0),
                            )

                            final_bit = sp.nat(0)
                            if final_bit_raw == 0:
                                final_bit = sp.nat(0)
                            else:
                                final_bit = sp.nat(1)

                            self.data.finished = True
                            self.data.phase = sp.nat(3)
                            self.data.outcome_bit = sp.Some(final_bit)
                            self.data.progress_deadline = None

                            if final_bit == sp.nat(0):
                                self.data.winner = self.data.player1
                                sp.send(self.data.player1.unwrap_some(), sp.balance)
                            else:
                                self.data.winner = self.data.player2
                                sp.send(self.data.player2.unwrap_some(), sp.balance)

            if not self.data.finished:
                self.data.progress_deadline = sp.Some(
                    sp.add_seconds(sp.now, self.data.progress_window_seconds)
                )

        @sp.entrypoint
        def claim_timeout(self):
            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.player1.is_some(), "NOTHING_TO_CLAIM"

            if self.data.phase == sp.nat(0):
                if self.data.player2.is_none():
                    assert self.data.join_deadline.is_some(), "NOTHING_TO_CLAIM"
                    assert sp.now > self.data.join_deadline.unwrap_some(), (
                        "NOTHING_TO_CLAIM"
                    )

                    self.data.finished = True
                    self.data.phase = sp.nat(3)
                    self.data.winner = self.data.player1
                    self.data.outcome_bit = None
                    self.data.progress_deadline = None
                    sp.send(self.data.player1.unwrap_some(), sp.balance)
                else:
                    assert self.data.reveal_deadline.is_some(), "NOTHING_TO_CLAIM"
                    assert sp.now > self.data.reveal_deadline.unwrap_some(), (
                        "NOTHING_TO_CLAIM"
                    )

                    if self.data.player1_revealed:
                        if self.data.player2_revealed:
                            assert False, "NOTHING_TO_CLAIM"
                        else:
                            self.data.finished = True
                            self.data.phase = sp.nat(3)
                            self.data.winner = self.data.player1
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            sp.send(self.data.player1.unwrap_some(), sp.balance)
                    else:
                        if self.data.player2_revealed:
                            self.data.finished = True
                            self.data.phase = sp.nat(3)
                            self.data.winner = self.data.player2
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            sp.send(self.data.player2.unwrap_some(), sp.balance)
                        else:
                            self.data.finished = True
                            self.data.phase = sp.nat(3)
                            self.data.winner = None
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            sp.send(self.data.player1.unwrap_some(), sp.tez(10))
                            sp.send(self.data.player2.unwrap_some(), sp.tez(10))
            else:
                assert self.data.phase == sp.nat(1) or self.data.phase == sp.nat(2), (
                    "BAD_PHASE"
                )
                assert self.data.player2.is_some(), "NOTHING_TO_CLAIM"
                assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
                assert sp.now > self.data.progress_deadline.unwrap_some(), (
                    "PROGRESS_TIMEOUT_NOT_REACHED"
                )

                self.data.finished = True
                self.data.phase = sp.nat(3)
                self.data.winner = None
                self.data.outcome_bit = None
                self.data.progress_deadline = None
                sp.send(self.data.player1.unwrap_some(), sp.tez(10))
                sp.send(self.data.player2.unwrap_some(), sp.tez(10))
