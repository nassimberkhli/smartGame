import smartpy as sp


@sp.module
def bet_contract():
    def commitment_of(params):
        payload = sp.record(
            player=params.player,
            secret=params.secret,
            salt=params.salt,
        )
        return sp.blake2b(sp.pack(payload))

    def result_commitment_of(params):
        payload = sp.record(
            player=params.player,
            final_bit=params.final_bit,
            salt=params.salt,
        )
        return sp.blake2b(sp.pack(payload))

    def credit_to_tez(credit):
        amount = sp.tez(0)
        if credit == sp.nat(10):
            amount = sp.tez(10)
        else:
            if credit == sp.nat(20):
                amount = sp.tez(20)
        return amount

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
            self.data.player1_result_commitment = None
            self.data.player2_result_commitment = None
            self.data.player1_result_revealed = False
            self.data.player2_result_revealed = False
            self.data.player1_result = None
            self.data.player2_result = None
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
            self.data.player1_credit = sp.nat(0)
            self.data.player2_credit = sp.nat(0)

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
                    player1_result_commitment=sp.option[sp.bytes],
                    player2_result_commitment=sp.option[sp.bytes],
                    player1_result_revealed=sp.bool,
                    player2_result_revealed=sp.bool,
                    player1_result=sp.option[sp.nat],
                    player2_result=sp.option[sp.nat],
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
                    player1_credit=sp.nat,
                    player2_credit=sp.nat,
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
        def commit_result(self, commitment):
            sp.cast(commitment, sp.bytes)

            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(1), "BAD_PHASE"
            assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
            assert sp.now <= self.data.progress_deadline.unwrap_some(), (
                "REVEAL_PHASE_OVER"
            )

            if sp.sender == self.data.player1.unwrap_some():
                assert self.data.player1_result_commitment.is_none(), "ALREADY_REVEALED"
                self.data.player1_result_commitment = sp.Some(commitment)
            else:
                assert sp.sender == self.data.player2.unwrap_some(), (
                    "PLAYER_NOT_REGISTERED"
                )
                assert self.data.player2_result_commitment.is_none(), "ALREADY_REVEALED"
                self.data.player2_result_commitment = sp.Some(commitment)

            self.data.progress_deadline = sp.Some(
                sp.add_seconds(sp.now, self.data.progress_window_seconds)
            )

            if self.data.player1_result_commitment.is_some():
                if self.data.player2_result_commitment.is_some():
                    self.data.phase = sp.nat(2)

        @sp.entrypoint
        def reveal_result(self, params):
            sp.cast(params, sp.record(final_bit=sp.nat, salt=sp.bytes))

            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(2), "BAD_PHASE"
            assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
            assert sp.now <= self.data.progress_deadline.unwrap_some(), (
                "REVEAL_PHASE_OVER"
            )
            assert params.final_bit == sp.nat(0) or params.final_bit == sp.nat(1), (
                "INVALID_FINAL_BIT"
            )

            if sp.sender == self.data.player1.unwrap_some():
                assert not self.data.player1_result_revealed, "ALREADY_REVEALED"
                assert (
                    result_commitment_of(
                        sp.record(
                            player=sp.sender,
                            final_bit=params.final_bit,
                            salt=params.salt,
                        )
                    )
                    == self.data.player1_result_commitment.unwrap_some()
                ), "INVALID_COMMITMENT"
                self.data.player1_result = sp.Some(params.final_bit)
                self.data.player1_result_revealed = True
            else:
                assert sp.sender == self.data.player2.unwrap_some(), (
                    "PLAYER_NOT_REGISTERED"
                )
                assert not self.data.player2_result_revealed, "ALREADY_REVEALED"
                assert (
                    result_commitment_of(
                        sp.record(
                            player=sp.sender,
                            final_bit=params.final_bit,
                            salt=params.salt,
                        )
                    )
                    == self.data.player2_result_commitment.unwrap_some()
                ), "INVALID_COMMITMENT"
                self.data.player2_result = sp.Some(params.final_bit)
                self.data.player2_result_revealed = True

            self.data.progress_deadline = sp.Some(
                sp.add_seconds(sp.now, self.data.progress_window_seconds)
            )

            if self.data.player1_result_revealed:
                if self.data.player2_result_revealed:
                    assert (
                        self.data.player1_result.unwrap_some()
                        == self.data.player2_result.unwrap_some()
                    ), "RESULT_MISMATCH"

                    final_bit = self.data.player1_result.unwrap_some()

                    self.data.finished = True
                    self.data.phase = sp.nat(3)
                    self.data.outcome_bit = sp.Some(final_bit)
                    self.data.progress_deadline = None

                    if final_bit == sp.nat(0):
                        self.data.winner = self.data.player1
                        self.data.player1_credit = sp.nat(20)
                    else:
                        self.data.winner = self.data.player2
                        self.data.player2_credit = sp.nat(20)

        @sp.entrypoint
        def claim(self):
            assert self.data.finished, "NOTHING_TO_CLAIM"

            if sp.sender == self.data.player1.unwrap_some():
                assert self.data.player1_credit > 0, "NOTHING_TO_CLAIM"
                amount = credit_to_tez(self.data.player1_credit)
                self.data.player1_credit = sp.nat(0)
                sp.send(sp.sender, amount)
            else:
                assert self.data.player2.is_some(), "PLAYER_NOT_REGISTERED"
                assert sp.sender == self.data.player2.unwrap_some(), (
                    "PLAYER_NOT_REGISTERED"
                )
                assert self.data.player2_credit > 0, "NOTHING_TO_CLAIM"
                amount = credit_to_tez(self.data.player2_credit)
                self.data.player2_credit = sp.nat(0)
                sp.send(sp.sender, amount)

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
                    self.data.player1_credit = sp.nat(10)
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
                            self.data.player1_credit = sp.nat(20)
                    else:
                        if self.data.player2_revealed:
                            self.data.finished = True
                            self.data.phase = sp.nat(3)
                            self.data.winner = self.data.player2
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            self.data.player2_credit = sp.nat(20)
                        else:
                            self.data.finished = True
                            self.data.phase = sp.nat(3)
                            self.data.winner = None
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            self.data.player1_credit = sp.nat(10)
                            self.data.player2_credit = sp.nat(10)
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
                self.data.player1_credit = sp.nat(10)
                self.data.player2_credit = sp.nat(10)
