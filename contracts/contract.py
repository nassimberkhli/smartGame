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

    def trace_commitment_of(params):
        payload = sp.record(
            player=params.player,
            final_bit=params.final_bit,
            checkpoint1=params.checkpoint1,
            checkpoint2=params.checkpoint2,
            checkpoint3=params.checkpoint3,
            checkpoint4=params.checkpoint4,
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

    def get_checkpoint_pair(idx, player1_cp1, player1_cp2, player1_cp3, player1_cp4,
                            player2_cp1, player2_cp2, player2_cp3, player2_cp4):
        """Retourne la paire de checkpoints à l'index donné"""
        result = (player1_cp1, player2_cp1)
        if idx == 0:
            result = (player1_cp1, player2_cp1)
        else:
            if idx == 1:
                result = (player1_cp2, player2_cp2)
            else:
                if idx == 2:
                    result = (player1_cp3, player2_cp3)
                else:
                    result = (player1_cp4, player2_cp4)
        return result

    def determine_dispute_range(checkpoint_index, checkpoints_match, 
                                checkpoint_round_1, checkpoint_round_2,
                               checkpoint_round_3, checkpoint_round_4, total_rounds):
        """Détermine la plage de dispute basée sur l'index du checkpoint différent"""
        low = sp.nat(0)
        high = checkpoint_round_1
        if checkpoint_index == 0:
            low = sp.nat(0)
            high = checkpoint_round_1
        else:
            if checkpoint_index == 1:
                low = checkpoint_round_1
                high = checkpoint_round_2
            else:
                if checkpoint_index == 2:
                    low = checkpoint_round_2
                    high = checkpoint_round_3
                else:
                    if checkpoint_index == 3:
                        low = checkpoint_round_3
                        high = checkpoint_round_4
                    else:
                        low = checkpoint_round_4
                        high = total_rounds
        return (low, high)

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
            checkpoint_round_1,
            checkpoint_round_2,
            checkpoint_round_3,
            checkpoint_round_4,
        ):
            self.data.player1 = None
            self.data.player2 = None
            self.data.player1_commitment = None
            self.data.player2_commitment = None
            self.data.player1_secret = None
            self.data.player2_secret = None
            self.data.player1_revealed = False
            self.data.player2_revealed = False
            self.data.player1_trace_commitment = None
            self.data.player2_trace_commitment = None
            self.data.player1_trace_revealed = False
            self.data.player2_trace_revealed = False
            self.data.player1_final_bit = None
            self.data.player2_final_bit = None
            self.data.player1_checkpoint1 = None
            self.data.player1_checkpoint2 = None
            self.data.player1_checkpoint3 = None
            self.data.player1_checkpoint4 = None
            self.data.player2_checkpoint1 = None
            self.data.player2_checkpoint2 = None
            self.data.player2_checkpoint3 = None
            self.data.player2_checkpoint4 = None
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
            self.data.checkpoint_round_1 = checkpoint_round_1
            self.data.checkpoint_round_2 = checkpoint_round_2
            self.data.checkpoint_round_3 = checkpoint_round_3
            self.data.checkpoint_round_4 = checkpoint_round_4
            self.data.player1_credit = sp.nat(0)
            self.data.player2_credit = sp.nat(0)
            self.data.dispute_low_round = None
            self.data.dispute_high_round = None
            self.data.player1_query_round = None
            self.data.player2_query_round = None
            self.data.player1_query_hash = None
            self.data.player2_query_hash = None
            self.data.player1_query_proof = None
            self.data.player2_query_proof = None

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
                    player1_trace_commitment=sp.option[sp.bytes],
                    player2_trace_commitment=sp.option[sp.bytes],
                    player1_trace_revealed=sp.bool,
                    player2_trace_revealed=sp.bool,
                    player1_final_bit=sp.option[sp.nat],
                    player2_final_bit=sp.option[sp.nat],
                    player1_checkpoint1=sp.option[sp.bytes],
                    player1_checkpoint2=sp.option[sp.bytes],
                    player1_checkpoint3=sp.option[sp.bytes],
                    player1_checkpoint4=sp.option[sp.bytes],
                    player2_checkpoint1=sp.option[sp.bytes],
                    player2_checkpoint2=sp.option[sp.bytes],
                    player2_checkpoint3=sp.option[sp.bytes],
                    player2_checkpoint4=sp.option[sp.bytes],
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
                    checkpoint_round_1=sp.nat,
                    checkpoint_round_2=sp.nat,
                    checkpoint_round_3=sp.nat,
                    checkpoint_round_4=sp.nat,
                    player1_credit=sp.nat,
                    player2_credit=sp.nat,
                    dispute_low_round=sp.option[sp.nat],
                    dispute_high_round=sp.option[sp.nat],
                    player1_query_round=sp.option[sp.nat],
                    player2_query_round=sp.option[sp.nat],
                    player1_query_hash=sp.option[sp.bytes],
                    player2_query_hash=sp.option[sp.bytes],
                    player1_query_proof=sp.option[sp.bytes],
                    player2_query_proof=sp.option[sp.bytes],
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
        def commit_trace(self, commitment):
            sp.cast(commitment, sp.bytes)

            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(1), "BAD_PHASE"
            assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
            assert sp.now <= self.data.progress_deadline.unwrap_some(), (
                "TRACE_COMMIT_PHASE_OVER"
            )

            if sp.sender == self.data.player1.unwrap_some():
                assert self.data.player1_trace_commitment.is_none(), "ALREADY_REVEALED"
                self.data.player1_trace_commitment = sp.Some(commitment)
            else:
                assert sp.sender == self.data.player2.unwrap_some(), (
                    "PLAYER_NOT_REGISTERED"
                )
                assert self.data.player2_trace_commitment.is_none(), "ALREADY_REVEALED"
                self.data.player2_trace_commitment = sp.Some(commitment)

            self.data.progress_deadline = sp.Some(
                sp.add_seconds(sp.now, self.data.progress_window_seconds)
            )

            if self.data.player1_trace_commitment.is_some():
                if self.data.player2_trace_commitment.is_some():
                    self.data.phase = sp.nat(2)

        @sp.entrypoint
        def reveal_trace(self, params):
            sp.cast(
                params,
                sp.record(
                    final_bit=sp.nat,
                    checkpoint1=sp.bytes,
                    checkpoint2=sp.bytes,
                    checkpoint3=sp.bytes,
                    checkpoint4=sp.bytes,
                    salt=sp.bytes,
                ),
            )

            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(2), "BAD_PHASE"
            assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
            assert sp.now <= self.data.progress_deadline.unwrap_some(), (
                "TRACE_REVEAL_PHASE_OVER"
            )
            assert params.final_bit == sp.nat(0) or params.final_bit == sp.nat(1), (
                "INVALID_FINAL_BIT"
            )

            if sp.sender == self.data.player1.unwrap_some():
                assert not self.data.player1_trace_revealed, "ALREADY_REVEALED"
                assert (
                    trace_commitment_of(
                        sp.record(
                            player=sp.sender,
                            final_bit=params.final_bit,
                            checkpoint1=params.checkpoint1,
                            checkpoint2=params.checkpoint2,
                            checkpoint3=params.checkpoint3,
                            checkpoint4=params.checkpoint4,
                            salt=params.salt,
                        )
                    )
                    == self.data.player1_trace_commitment.unwrap_some()
                ), "INVALID_TRACE_COMMITMENT"
                self.data.player1_final_bit = sp.Some(params.final_bit)
                self.data.player1_checkpoint1 = sp.Some(params.checkpoint1)
                self.data.player1_checkpoint2 = sp.Some(params.checkpoint2)
                self.data.player1_checkpoint3 = sp.Some(params.checkpoint3)
                self.data.player1_checkpoint4 = sp.Some(params.checkpoint4)
                self.data.player1_trace_revealed = True
            else:
                assert sp.sender == self.data.player2.unwrap_some(), (
                    "PLAYER_NOT_REGISTERED"
                )
                assert not self.data.player2_trace_revealed, "ALREADY_REVEALED"
                assert (
                    trace_commitment_of(
                        sp.record(
                            player=sp.sender,
                            final_bit=params.final_bit,
                            checkpoint1=params.checkpoint1,
                            checkpoint2=params.checkpoint2,
                            checkpoint3=params.checkpoint3,
                            checkpoint4=params.checkpoint4,
                            salt=params.salt,
                        )
                    )
                    == self.data.player2_trace_commitment.unwrap_some()
                ), "INVALID_TRACE_COMMITMENT"
                self.data.player2_final_bit = sp.Some(params.final_bit)
                self.data.player2_checkpoint1 = sp.Some(params.checkpoint1)
                self.data.player2_checkpoint2 = sp.Some(params.checkpoint2)
                self.data.player2_checkpoint3 = sp.Some(params.checkpoint3)
                self.data.player2_checkpoint4 = sp.Some(params.checkpoint4)
                self.data.player2_trace_revealed = True

            self.data.progress_deadline = sp.Some(
                sp.add_seconds(sp.now, self.data.progress_window_seconds)
            )

            # Refactored: Check if both traces revealed and if they match
            both_revealed = (
                self.data.player1_trace_revealed and self.data.player2_trace_revealed
            )
            if both_revealed:
                final_bits_match = (
                    self.data.player1_final_bit.unwrap_some()
                    == self.data.player2_final_bit.unwrap_some()
                )
                if not final_bits_match:
                    # Final bits differ - open dispute from checkpoint 0
                    self.data.phase = sp.nat(4)
                    self.data.progress_deadline = sp.Some(
                        sp.add_seconds(sp.now, self.data.progress_window_seconds)
                    )
                    self.data.player1_query_round = None
                    self.data.player2_query_round = None
                    self.data.player1_query_hash = None
                    self.data.player2_query_hash = None
                    self.data.player1_query_proof = None
                    self.data.player2_query_proof = None
                    self.data.dispute_low_round = sp.Some(sp.nat(0))
                    self.data.dispute_high_round = sp.Some(self.data.checkpoint_round_1)
                else:
                    # Final bits match, check checkpoints sequentially
                    cp1_match = (
                        self.data.player1_checkpoint1.unwrap_some()
                        == self.data.player2_checkpoint1.unwrap_some()
                    )
                    cp2_match = (
                        self.data.player1_checkpoint2.unwrap_some()
                        == self.data.player2_checkpoint2.unwrap_some()
                    )
                    cp3_match = (
                        self.data.player1_checkpoint3.unwrap_some()
                        == self.data.player2_checkpoint3.unwrap_some()
                    )
                    cp4_match = (
                        self.data.player1_checkpoint4.unwrap_some()
                        == self.data.player2_checkpoint4.unwrap_some()
                    )

                    # No checkpoints match case
                    if not cp1_match:
                        self.data.phase = sp.nat(4)
                        self.data.progress_deadline = sp.Some(
                            sp.add_seconds(sp.now, self.data.progress_window_seconds)
                        )
                        self.data.player1_query_round = None
                        self.data.player2_query_round = None
                        self.data.player1_query_hash = None
                        self.data.player2_query_hash = None
                        self.data.player1_query_proof = None
                        self.data.player2_query_proof = None
                        self.data.dispute_low_round = sp.Some(sp.nat(0))
                        self.data.dispute_high_round = sp.Some(self.data.checkpoint_round_1)
                    else:
                        if not cp2_match:
                            self.data.phase = sp.nat(4)
                            self.data.progress_deadline = sp.Some(
                                sp.add_seconds(sp.now, self.data.progress_window_seconds)
                            )
                            self.data.player1_query_round = None
                            self.data.player2_query_round = None
                            self.data.player1_query_hash = None
                            self.data.player2_query_hash = None
                            self.data.player1_query_proof = None
                            self.data.player2_query_proof = None
                            self.data.dispute_low_round = sp.Some(self.data.checkpoint_round_1)
                            self.data.dispute_high_round = sp.Some(self.data.checkpoint_round_2)
                        else:
                            if not cp3_match:
                                self.data.phase = sp.nat(4)
                                self.data.progress_deadline = sp.Some(
                                    sp.add_seconds(sp.now, self.data.progress_window_seconds)
                                )
                                self.data.player1_query_round = None
                                self.data.player2_query_round = None
                                self.data.player1_query_hash = None
                                self.data.player2_query_hash = None
                                self.data.player1_query_proof = None
                                self.data.player2_query_proof = None
                                self.data.dispute_low_round = sp.Some(self.data.checkpoint_round_2)
                                self.data.dispute_high_round = sp.Some(self.data.checkpoint_round_3)
                            else:
                                if not cp4_match:
                                    self.data.phase = sp.nat(4)
                                    self.data.progress_deadline = sp.Some(
                                        sp.add_seconds(sp.now, self.data.progress_window_seconds)
                                    )
                                    self.data.player1_query_round = None
                                    self.data.player2_query_round = None
                                    self.data.player1_query_hash = None
                                    self.data.player2_query_hash = None
                                    self.data.player1_query_proof = None
                                    self.data.player2_query_proof = None
                                    self.data.dispute_low_round = sp.Some(self.data.checkpoint_round_3)
                                    self.data.dispute_high_round = sp.Some(self.data.checkpoint_round_4)
                                else:
                                    # All checkpoints match - game ends
                                    self.data.finished = True
                                    self.data.phase = sp.nat(5)
                                    self.data.progress_deadline = None
                                    if self.data.player1_final_bit.unwrap_some() == sp.nat(0):
                                        self.data.winner = self.data.player1
                                        self.data.outcome_bit = sp.Some(sp.nat(0))
                                        self.data.player1_credit = sp.nat(20)
                                        self.data.player2_credit = sp.nat(0)
                                    else:
                                        self.data.winner = self.data.player2
                                        self.data.outcome_bit = sp.Some(sp.nat(1))
                                        self.data.player1_credit = sp.nat(0)
                                        self.data.player2_credit = sp.nat(20)

        @sp.entrypoint
        def open_dispute(self):
            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(4), "BAD_PHASE"
            assert self.data.dispute_low_round.is_some(), "BAD_DISPUTE_RANGE"
            assert self.data.dispute_high_round.is_some(), "BAD_DISPUTE_RANGE"

            self.data.progress_deadline = sp.Some(
                sp.add_seconds(sp.now, self.data.progress_window_seconds)
            )
            self.data.player1_query_round = None
            self.data.player2_query_round = None
            self.data.player1_query_hash = None
            self.data.player2_query_hash = None
            self.data.player1_query_proof = None
            self.data.player2_query_proof = None

        @sp.entrypoint
        def submit_checkpoint(self, params):
            sp.cast(
                params,
                sp.record(round_index=sp.nat, state_hash=sp.bytes, proof=sp.bytes),
            )

            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(4), "BAD_PHASE"
            assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
            assert sp.now <= self.data.progress_deadline.unwrap_some(), (
                "TRACE_REVEAL_PHASE_OVER"
            )
            assert self.data.dispute_low_round.is_some(), "BAD_DISPUTE_RANGE"
            assert self.data.dispute_high_round.is_some(), "BAD_DISPUTE_RANGE"
            assert params.round_index > self.data.dispute_low_round.unwrap_some(), (
                "BAD_DISPUTE_RANGE"
            )
            assert params.round_index <= self.data.dispute_high_round.unwrap_some(), (
                "BAD_DISPUTE_RANGE"
            )

            if sp.sender == self.data.player1.unwrap_some():
                assert self.data.player1_query_round.is_none(), "ALREADY_SUBMITTED"

                # Flatten nested checkpoint verification with else if chain
                if params.round_index == self.data.checkpoint_round_1:
                    assert (
                        params.state_hash == self.data.player1_checkpoint1.unwrap_some()
                    ), "INVALID_CHECKPOINT_HASH"
                else:
                    if params.round_index == self.data.checkpoint_round_2:
                        assert (
                            params.state_hash
                            == self.data.player1_checkpoint2.unwrap_some()
                        ), "INVALID_CHECKPOINT_HASH"
                    else:
                        if params.round_index == self.data.checkpoint_round_3:
                            assert (
                                params.state_hash
                                == self.data.player1_checkpoint3.unwrap_some()
                            ), "INVALID_CHECKPOINT_HASH"
                        else:
                            if params.round_index == self.data.checkpoint_round_4:
                                assert (
                                    params.state_hash
                                    == self.data.player1_checkpoint4.unwrap_some()
                                ), "INVALID_CHECKPOINT_HASH"

                if self.data.player2_query_round.is_some():
                    assert (
                        params.round_index
                        == self.data.player2_query_round.unwrap_some()
                    ), "ROUND_MISMATCH"

                self.data.player1_query_round = sp.Some(params.round_index)
                self.data.player1_query_hash = sp.Some(params.state_hash)
                self.data.player1_query_proof = sp.Some(params.proof)
            else:
                assert sp.sender == self.data.player2.unwrap_some(), (
                    "PLAYER_NOT_REGISTERED"
                )
                assert self.data.player2_query_round.is_none(), "ALREADY_SUBMITTED"

                # Flatten nested checkpoint verification with else if chain
                if params.round_index == self.data.checkpoint_round_1:
                    assert (
                        params.state_hash == self.data.player2_checkpoint1.unwrap_some()
                    ), "INVALID_CHECKPOINT_HASH"
                else:
                    if params.round_index == self.data.checkpoint_round_2:
                        assert (
                            params.state_hash
                            == self.data.player2_checkpoint2.unwrap_some()
                        ), "INVALID_CHECKPOINT_HASH"
                    else:
                        if params.round_index == self.data.checkpoint_round_3:
                            assert (
                                params.state_hash
                                == self.data.player2_checkpoint3.unwrap_some()
                            ), "INVALID_CHECKPOINT_HASH"
                        else:
                            if params.round_index == self.data.checkpoint_round_4:
                                assert (
                                    params.state_hash
                                    == self.data.player2_checkpoint4.unwrap_some()
                                ), "INVALID_CHECKPOINT_HASH"

                if self.data.player1_query_round.is_some():
                    assert (
                        params.round_index
                        == self.data.player1_query_round.unwrap_some()
                    ), "ROUND_MISMATCH"

                self.data.player2_query_round = sp.Some(params.round_index)
                self.data.player2_query_hash = sp.Some(params.state_hash)
                self.data.player2_query_proof = sp.Some(params.proof)

            if self.data.player1_query_round.is_some():
                if self.data.player2_query_round.is_some():
                    if (
                        self.data.player1_query_hash.unwrap_some()
                        == self.data.player2_query_hash.unwrap_some()
                    ):
                        if (
                            params.round_index
                            == self.data.dispute_high_round.unwrap_some()
                        ):
                            self.data.progress_deadline = sp.Some(
                                sp.add_seconds(
                                    sp.now,
                                    self.data.progress_window_seconds,
                                )
                            )
                        else:
                            self.data.dispute_low_round = sp.Some(params.round_index)
                            self.data.progress_deadline = sp.Some(
                                sp.add_seconds(
                                    sp.now,
                                    self.data.progress_window_seconds,
                                )
                            )
                    else:
                        if (
                            params.round_index
                            == self.data.dispute_high_round.unwrap_some()
                        ):
                            self.data.progress_deadline = sp.Some(
                                sp.add_seconds(
                                    sp.now,
                                    self.data.progress_window_seconds,
                                )
                            )
                        else:
                            self.data.dispute_high_round = sp.Some(params.round_index)
                            self.data.progress_deadline = sp.Some(
                                sp.add_seconds(
                                    sp.now,
                                    self.data.progress_window_seconds,
                                )
                            )

                    self.data.player1_query_round = None
                    self.data.player2_query_round = None
                    self.data.player1_query_hash = None
                    self.data.player2_query_hash = None
                    self.data.player1_query_proof = None
                    self.data.player2_query_proof = None

        @sp.entrypoint
        def resolve_dispute(self, params):
            sp.cast(
                params,
                sp.record(
                    cell_index=sp.nat,
                    left=sp.nat,
                    center=sp.nat,
                    right=sp.nat,
                    player1_next=sp.nat,
                    player2_next=sp.nat,
                ),
            )

            assert not self.data.finished, "GAME_ALREADY_FINISHED"
            assert self.data.phase == sp.nat(4), "BAD_PHASE"
            assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
            assert sp.now <= self.data.progress_deadline.unwrap_some(), (
                "TRACE_REVEAL_PHASE_OVER"
            )
            assert params.left == sp.nat(0) or params.left == sp.nat(1), (
                "INVALID_FINAL_BIT"
            )
            assert params.center == sp.nat(0) or params.center == sp.nat(1), (
                "INVALID_FINAL_BIT"
            )
            assert params.right == sp.nat(0) or params.right == sp.nat(1), (
                "INVALID_FINAL_BIT"
            )
            assert params.player1_next == sp.nat(0) or params.player1_next == sp.nat(
                1
            ), "INVALID_FINAL_BIT"
            assert params.player2_next == sp.nat(0) or params.player2_next == sp.nat(
                1
            ), "INVALID_FINAL_BIT"

            # Cellular automaton lookup table with flattened compound conditions
            # Table: (left, center, right) -> expected_next
            expected = sp.nat(0)
            if (params.left == sp.nat(0)) and (params.center == sp.nat(0)) and (params.right == sp.nat(0)):
                expected = sp.nat(0)
            else:
                if (params.left == sp.nat(0)) and (params.center == sp.nat(0)) and (params.right == sp.nat(1)):
                    expected = sp.nat(1)
                else:
                    if (params.left == sp.nat(0)) and (params.center == sp.nat(1)) and (params.right == sp.nat(0)):
                        expected = sp.nat(1)
                    else:
                        if (params.left == sp.nat(0)) and (params.center == sp.nat(1)) and (params.right == sp.nat(1)):
                            expected = sp.nat(0)
                        else:
                            if (params.left == sp.nat(1)) and (params.center == sp.nat(0)) and (params.right == sp.nat(0)):
                                expected = sp.nat(1)
                            else:
                                if (params.left == sp.nat(1)) and (params.center == sp.nat(0)) and (params.right == sp.nat(1)):
                                    expected = sp.nat(0)
                                else:
                                    if (params.left == sp.nat(1)) and (params.center == sp.nat(1)) and (params.right == sp.nat(0)):
                                        expected = sp.nat(0)
                                    else:
                                        expected = sp.nat(1)  # (1,1,1) case

            if params.player1_next == expected:
                if params.player2_next == expected:
                    assert False, "UNRESOLVED_LOCAL_PROOF"
                else:
                    self.data.finished = True
                    self.data.phase = sp.nat(5)
                    self.data.winner = self.data.player1
                    self.data.outcome_bit = None
                    self.data.progress_deadline = None
                    self.data.player1_credit = sp.nat(20)
                    self.data.player2_credit = sp.nat(0)
            else:
                if params.player2_next == expected:
                    self.data.finished = True
                    self.data.phase = sp.nat(5)
                    self.data.winner = self.data.player2
                    self.data.outcome_bit = None
                    self.data.progress_deadline = None
                    self.data.player1_credit = sp.nat(0)
                    self.data.player2_credit = sp.nat(20)
                else:
                    assert False, "UNRESOLVED_LOCAL_PROOF"

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
                    self.data.phase = sp.nat(5)
                    self.data.winner = self.data.player1
                    self.data.outcome_bit = None
                    self.data.progress_deadline = None
                    self.data.player1_credit = sp.nat(10)
                    self.data.player2_credit = sp.nat(0)
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
                            self.data.phase = sp.nat(5)
                            self.data.winner = self.data.player1
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            self.data.player1_credit = sp.nat(20)
                            self.data.player2_credit = sp.nat(0)
                    else:
                        if self.data.player2_revealed:
                            self.data.finished = True
                            self.data.phase = sp.nat(5)
                            self.data.winner = self.data.player2
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            self.data.player1_credit = sp.nat(0)
                            self.data.player2_credit = sp.nat(20)
                        else:
                            if sp.sender == self.data.player1.unwrap_some():
                                self.data.finished = True
                                self.data.phase = sp.nat(5)
                                self.data.winner = self.data.player1
                                self.data.outcome_bit = None
                                self.data.progress_deadline = None
                                self.data.player1_credit = sp.nat(20)
                                self.data.player2_credit = sp.nat(0)
                            else:
                                assert self.data.player2.is_some(), (
                                    "PLAYER_NOT_REGISTERED"
                                )
                                assert sp.sender == self.data.player2.unwrap_some(), (
                                    "PLAYER_NOT_REGISTERED"
                                )
                                self.data.finished = True
                                self.data.phase = sp.nat(5)
                                self.data.winner = self.data.player2
                                self.data.outcome_bit = None
                                self.data.progress_deadline = None
                                self.data.player1_credit = sp.nat(0)
                                self.data.player2_credit = sp.nat(20)
            else:
                if self.data.phase == sp.nat(1):
                    assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
                    assert sp.now > self.data.progress_deadline.unwrap_some(), (
                        "PROGRESS_TIMEOUT_NOT_REACHED"
                    )

                    if self.data.player1_trace_commitment.is_some():
                        if self.data.player2_trace_commitment.is_some():
                            assert False, "NOTHING_TO_CLAIM"
                        else:
                            self.data.finished = True
                            self.data.phase = sp.nat(5)
                            self.data.winner = self.data.player1
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            self.data.player1_credit = sp.nat(20)
                            self.data.player2_credit = sp.nat(0)
                    else:
                        if self.data.player2_trace_commitment.is_some():
                            self.data.finished = True
                            self.data.phase = sp.nat(5)
                            self.data.winner = self.data.player2
                            self.data.outcome_bit = None
                            self.data.progress_deadline = None
                            self.data.player1_credit = sp.nat(0)
                            self.data.player2_credit = sp.nat(20)
                        else:
                            if sp.sender == self.data.player1.unwrap_some():
                                self.data.finished = True
                                self.data.phase = sp.nat(5)
                                self.data.winner = self.data.player1
                                self.data.outcome_bit = None
                                self.data.progress_deadline = None
                                self.data.player1_credit = sp.nat(20)
                                self.data.player2_credit = sp.nat(0)
                            else:
                                assert self.data.player2.is_some(), (
                                    "PLAYER_NOT_REGISTERED"
                                )
                                assert sp.sender == self.data.player2.unwrap_some(), (
                                    "PLAYER_NOT_REGISTERED"
                                )
                                self.data.finished = True
                                self.data.phase = sp.nat(5)
                                self.data.winner = self.data.player2
                                self.data.outcome_bit = None
                                self.data.progress_deadline = None
                                self.data.player1_credit = sp.nat(0)
                                self.data.player2_credit = sp.nat(20)
                else:
                    if self.data.phase == sp.nat(2):
                        assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
                        assert sp.now > self.data.progress_deadline.unwrap_some(), (
                            "PROGRESS_TIMEOUT_NOT_REACHED"
                        )

                        if self.data.player1_trace_revealed:
                            if self.data.player2_trace_revealed:
                                assert False, "NOTHING_TO_CLAIM"
                            else:
                                self.data.finished = True
                                self.data.phase = sp.nat(5)
                                self.data.winner = self.data.player1
                                self.data.outcome_bit = None
                                self.data.progress_deadline = None
                                self.data.player1_credit = sp.nat(20)
                                self.data.player2_credit = sp.nat(0)
                        else:
                            if self.data.player2_trace_revealed:
                                self.data.finished = True
                                self.data.phase = sp.nat(5)
                                self.data.winner = self.data.player2
                                self.data.outcome_bit = None
                                self.data.progress_deadline = None
                                self.data.player1_credit = sp.nat(0)
                                self.data.player2_credit = sp.nat(20)
                            else:
                                if sp.sender == self.data.player1.unwrap_some():
                                    self.data.finished = True
                                    self.data.phase = sp.nat(5)
                                    self.data.winner = self.data.player1
                                    self.data.outcome_bit = None
                                    self.data.progress_deadline = None
                                    self.data.player1_credit = sp.nat(20)
                                    self.data.player2_credit = sp.nat(0)
                                else:
                                    assert self.data.player2.is_some(), (
                                        "PLAYER_NOT_REGISTERED"
                                    )
                                    assert (
                                        sp.sender == self.data.player2.unwrap_some()
                                    ), "PLAYER_NOT_REGISTERED"
                                    self.data.finished = True
                                    self.data.phase = sp.nat(5)
                                    self.data.winner = self.data.player2
                                    self.data.outcome_bit = None
                                    self.data.progress_deadline = None
                                    self.data.player1_credit = sp.nat(0)
                                    self.data.player2_credit = sp.nat(20)
                    else:
                        assert self.data.phase == sp.nat(4), "BAD_PHASE"
                        assert self.data.progress_deadline.is_some(), "NOTHING_TO_CLAIM"
                        assert sp.now > self.data.progress_deadline.unwrap_some(), (
                            "PROGRESS_TIMEOUT_NOT_REACHED"
                        )

                        if self.data.player1_query_round.is_some():
                            if self.data.player2_query_round.is_some():
                                assert False, "NOTHING_TO_CLAIM"
                            else:
                                self.data.finished = True
                                self.data.phase = sp.nat(5)
                                self.data.winner = self.data.player1
                                self.data.outcome_bit = None
                                self.data.progress_deadline = None
                                self.data.player1_credit = sp.nat(20)
                                self.data.player2_credit = sp.nat(0)
                        else:
                            if self.data.player2_query_round.is_some():
                                self.data.finished = True
                                self.data.phase = sp.nat(5)
                                self.data.winner = self.data.player2
                                self.data.outcome_bit = None
                                self.data.progress_deadline = None
                                self.data.player1_credit = sp.nat(0)
                                self.data.player2_credit = sp.nat(20)
                            else:
                                if sp.sender == self.data.player1.unwrap_some():
                                    self.data.finished = True
                                    self.data.phase = sp.nat(5)
                                    self.data.winner = self.data.player1
                                    self.data.outcome_bit = None
                                    self.data.progress_deadline = None
                                    self.data.player1_credit = sp.nat(20)
                                    self.data.player2_credit = sp.nat(0)
                                else:
                                    assert self.data.player2.is_some(), (
                                        "PLAYER_NOT_REGISTERED"
                                    )
                                    assert (
                                        sp.sender == self.data.player2.unwrap_some()
                                    ), "PLAYER_NOT_REGISTERED"
                                    self.data.finished = True
                                    self.data.phase = sp.nat(5)
                                    self.data.winner = self.data.player2
                                    self.data.outcome_bit = None
                                    self.data.progress_deadline = None
                                    self.data.player1_credit = sp.nat(0)
                                    self.data.player2_credit = sp.nat(20)
