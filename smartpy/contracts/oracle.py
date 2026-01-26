import smartpy as sp

# ============================================================================
# Oracle Commit-Reveal Contract
# ============================================================================
# Decentralized oracle for CrowdShield markets using commit-reveal scheme.
# Reporters stake tez, commit hashes, reveal votes, and finalize outcomes.
# Implements slashing for absent/incorrect reporters.
# ============================================================================


@sp.module
def main():
    # Import Side type (must match market contract)
    class Side(sp.Enum):
        OVER = ()
        UNDER = ()
    
    class Tally(sp.Record):
        over_votes: sp.nat
        under_votes: sp.nat
        reveals_count: sp.nat
    
    # ========================================================================
    # OracleCommitReveal Contract
    # ========================================================================
    
    class OracleCommitReveal(sp.Contract):
        """
        Decentralized oracle with commit-reveal mechanism.
        
        Storage:
        - admin: Contract administrator
        - market_contract: CrowdShieldMarket contract address
        - min_stake: Minimum stake to become a reporter
        - min_quorum: Minimum number of reveals to finalize
        - commit_duration: Duration for commit phase (seconds)
        - reveal_duration: Duration for reveal phase (seconds)
        - slash_absent_bps: Slash percentage for absent reporters (basis points)
        - slash_wrong_bps: Slash percentage for wrong reporters (basis points)
        - reporters: Big map of reporter -> staked amount
        - commits: Big map of (market_id, reporter) -> commit hash
        - revealed: Big map of (market_id, reporter) -> revealed status
        - reveal_votes: Big map of (market_id, reporter) -> voted side
        - tally: Big map of market_id -> vote tally
        - finalized: Big map of market_id -> finalized status
        - commit_deadline: Big map of market_id -> commit deadline
        - reveal_deadline: Big map of market_id -> reveal deadline
        """
        
        def __init__(
            self,
            admin,
            market_contract,
            min_stake,
            min_quorum,
            commit_duration,
            reveal_duration,
            slash_absent_bps,
            slash_wrong_bps
        ):
            self.data.admin = admin
            self.data.market_contract = market_contract
            self.data.min_stake = min_stake
            self.data.min_quorum = min_quorum
            self.data.commit_duration = commit_duration
            self.data.reveal_duration = reveal_duration
            self.data.slash_absent_bps = slash_absent_bps  # e.g., 1000 = 10%
            self.data.slash_wrong_bps = slash_wrong_bps    # e.g., 3000 = 30%
            
            self.data.reporters = sp.cast(
                sp.big_map(),
                sp.big_map[sp.address, sp.mutez]
            )
            self.data.commits = sp.cast(
                sp.big_map(),
                sp.big_map[sp.tuple[sp.nat, sp.address], sp.bytes]
            )
            self.data.revealed = sp.cast(
                sp.big_map(),
                sp.big_map[sp.tuple[sp.nat, sp.address], sp.bool]
            )
            self.data.reveal_votes = sp.cast(
                sp.big_map(),
                sp.big_map[sp.tuple[sp.nat, sp.address], Side]
            )
            self.data.tally = sp.cast(
                sp.big_map(),
                sp.big_map[sp.nat, Tally]
            )
            self.data.finalized = sp.cast(
                sp.big_map(),
                sp.big_map[sp.nat, sp.bool]
            )
            self.data.commit_deadline = sp.cast(
                sp.big_map(),
                sp.big_map[sp.nat, sp.timestamp]
            )
            self.data.reveal_deadline = sp.cast(
                sp.big_map(),
                sp.big_map[sp.nat, sp.timestamp]
            )
            self.data.committed_reporters = sp.cast(
                sp.big_map(),
                sp.big_map[sp.nat, sp.set[sp.address]]
            )
        
        # ====================================================================
        # Entrypoint: register_reporter
        # ====================================================================
        @sp.entrypoint
        def register_reporter(self):
            """
            Register as a reporter by staking tez.
            
            Preconditions:
            - sp.amount >= min_stake
            
            Effects:
            - Adds/increases reporter's stake
            """
            assert sp.amount >= self.data.min_stake, "INSUFFICIENT_STAKE"
            
            current_stake = self.data.reporters.get(sp.sender, default=sp.mutez(0))
            self.data.reporters[sp.sender] = current_stake + sp.amount
        
        # ====================================================================
        # Entrypoint: init_resolution
        # ====================================================================
        @sp.entrypoint
        def init_resolution(self, market_id):
            """
            Initialize resolution process for a market.
            Called when market transitions to RESOLVING.
            
            Preconditions:
            - Not already initialized
            
            Effects:
            - Sets commit and reveal deadlines
            - Initializes tally
            """
            sp.cast(market_id, sp.nat)
            
            assert not self.data.finalized.get(market_id, default=False), "ALREADY_FINALIZED"
            assert not self.data.commit_deadline.contains(market_id), "ALREADY_INITIALIZED"
            
            # Set deadlines
            self.data.commit_deadline[market_id] = sp.add_seconds(
                sp.now, self.data.commit_duration
            )
            self.data.reveal_deadline[market_id] = sp.add_seconds(
                sp.now, self.data.commit_duration + self.data.reveal_duration
            )
            
            # Initialize tally
            self.data.tally[market_id] = sp.record(
                over_votes=sp.nat(0),
                under_votes=sp.nat(0),
                reveals_count=sp.nat(0)
            )
            
            # Initialize committed reporters set
            self.data.committed_reporters[market_id] = sp.cast(
                sp.set(), sp.set[sp.address]
            )
        
        # ====================================================================
        # Entrypoint: commit
        # ====================================================================
        @sp.entrypoint
        def commit(self, market_id, commit_hash):
            """
            Commit a hashed vote for a market outcome.
            
            Preconditions:
            - Sender is a registered reporter
            - Resolution is initialized
            - Within commit deadline
            - Not already committed
            
            Effects:
            - Stores commit hash
            - Adds reporter to committed set
            """
            sp.cast(market_id, sp.nat)
            sp.cast(commit_hash, sp.bytes)
            
            # Must be a reporter
            assert self.data.reporters.contains(sp.sender), "NOT_REPORTER"
            
            # Resolution must be initialized
            assert self.data.commit_deadline.contains(market_id), "NOT_INITIALIZED"
            
            # Within commit deadline
            assert sp.now <= self.data.commit_deadline[market_id], "COMMIT_DEADLINE_PASSED"
            
            # Not already committed
            commit_key = (market_id, sp.sender)
            assert not self.data.commits.contains(commit_key), "ALREADY_COMMITTED"
            
            # Store commit
            self.data.commits[commit_key] = commit_hash
            
            # Add to committed set
            committed = self.data.committed_reporters[market_id]
            committed.add(sp.sender)
            self.data.committed_reporters[market_id] = committed
        
        # ====================================================================
        # Entrypoint: reveal
        # ====================================================================
        @sp.entrypoint
        def reveal(self, market_id, result, salt):
            """
            Reveal vote for a market outcome.
            
            Preconditions:
            - Commit exists for this reporter
            - After commit deadline, before reveal deadline
            - Not already revealed
            - Hash matches: keccak(pack(result, salt)) == commit
            
            Effects:
            - Marks as revealed
            - Updates tally
            - Stores revealed vote
            """
            sp.cast(market_id, sp.nat)
            sp.cast(result, Side)
            sp.cast(salt, sp.bytes)
            
            commit_key = (market_id, sp.sender)
            
            # Must have committed
            assert self.data.commits.contains(commit_key), "NO_COMMIT"
            
            # After commit deadline
            assert sp.now > self.data.commit_deadline[market_id], "COMMIT_PHASE_ACTIVE"
            
            # Before reveal deadline
            assert sp.now <= self.data.reveal_deadline[market_id], "REVEAL_DEADLINE_PASSED"
            
            # Not already revealed
            assert not self.data.revealed.get(commit_key, default=False), "ALREADY_REVEALED"
            
            # Verify hash
            # Compute expected hash: keccak(pack(result || salt))
            packed_data = sp.pack((result, salt))
            expected_hash = sp.keccak(packed_data)
            stored_hash = self.data.commits[commit_key]
            
            assert expected_hash == stored_hash, "HASH_MISMATCH"
            
            # Mark as revealed
            self.data.revealed[commit_key] = True
            
            # Store vote
            self.data.reveal_votes[commit_key] = result
            
            # Update tally
            tally = self.data.tally[market_id]
            if result == Side.OVER:
                tally.over_votes += 1
            else:
                tally.under_votes += 1
            tally.reveals_count += 1
            self.data.tally[market_id] = tally
        
        # ====================================================================
        # Entrypoint: finalize
        # ====================================================================
        @sp.entrypoint
        def finalize(self, market_id):
            """
            Finalize resolution and send outcome to market contract.
            
            Preconditions:
            - Not already finalized
            - Quorum reached OR reveal deadline passed
            
            Effects:
            - Calculates majority result
            - Slashes absent and incorrect reporters
            - Calls market.receive_outcome()
            - Marks as finalized
            """
            sp.cast(market_id, sp.nat)
            
            assert not self.data.finalized.get(market_id, default=False), "ALREADY_FINALIZED"
            
            tally = self.data.tally.get(
                market_id,
                default=sp.record(over_votes=sp.nat(0), under_votes=sp.nat(0), reveals_count=sp.nat(0))
            )
            
            # Check quorum or deadline
            quorum_reached = tally.reveals_count >= self.data.min_quorum
            deadline_passed = sp.now > self.data.reveal_deadline.get(
                market_id,
                default=sp.timestamp(0)
            )
            
            assert quorum_reached or deadline_passed, "CANNOT_FINALIZE"
            
            # Require at least one vote
            assert tally.reveals_count > 0, "NO_VOTES"
            
            # Determine result (majority wins)
            result = Side.OVER if tally.over_votes >= tally.under_votes else Side.UNDER
            
            # Apply slashing
            committed = self.data.committed_reporters.get(
                market_id,
                default=sp.cast(sp.set(), sp.set[sp.address])
            )
            
            for reporter in committed.elements():
                commit_key = (market_id, reporter)
                was_revealed = self.data.revealed.get(commit_key, default=False)
                
                if not was_revealed:
                    # Slash for absence
                    self._slash_reporter(reporter, self.data.slash_absent_bps)
                else:
                    # Check if voted correctly
                    voted_side = self.data.reveal_votes.get(commit_key)
                    if voted_side != result:
                        # Slash for wrong vote
                        self._slash_reporter(reporter, self.data.slash_wrong_bps)
            
            # Mark as finalized
            self.data.finalized[market_id] = True
            
            # Call market contract with result
            market_contract = sp.contract(
                sp.record(market_id=sp.nat, result=Side),
                self.data.market_contract,
                entrypoint="receive_outcome"
            ).unwrap_some(error="INVALID_MARKET_CONTRACT")
            
            sp.transfer(
                sp.record(market_id=market_id, result=result),
                sp.mutez(0),
                market_contract
            )
        
        # ====================================================================
        # Internal: _slash_reporter
        # ====================================================================
        @sp.private(with_storage="read-write")
        def _slash_reporter(self, reporter, slash_bps):
            """Slash a portion of reporter's stake."""
            stake = self.data.reporters.get(reporter, default=sp.mutez(0))
            if stake > sp.mutez(0):
                slash_amount = sp.split_tokens(stake, slash_bps, 10000)
                new_stake = stake - slash_amount
                if new_stake > sp.mutez(0):
                    self.data.reporters[reporter] = new_stake
                else:
                    del self.data.reporters[reporter]
        
        # ====================================================================
        # Entrypoint: withdraw_stake
        # ====================================================================
        @sp.entrypoint
        def withdraw_stake(self, amount):
            """
            Withdraw staked amount (partial or full).
            
            Preconditions:
            - Sender has sufficient stake
            
            Effects:
            - Reduces stake
            - Transfers tez to sender
            """
            sp.cast(amount, sp.mutez)
            
            current_stake = self.data.reporters.get(sp.sender, default=sp.mutez(0))
            assert current_stake >= amount, "INSUFFICIENT_STAKE"
            
            new_stake = current_stake - amount
            if new_stake > sp.mutez(0):
                self.data.reporters[sp.sender] = new_stake
            else:
                del self.data.reporters[sp.sender]
            
            sp.send(sp.sender, amount)
        
        # ====================================================================
        # Admin: set_market_contract
        # ====================================================================
        @sp.entrypoint
        def set_market_contract(self, new_address):
            """Update market contract address (admin only)."""
            assert sp.sender == self.data.admin, "NOT_ADMIN"
            self.data.market_contract = new_address
        
        # ====================================================================
        # Views
        # ====================================================================
        @sp.onchain_view
        def get_reporter_stake(self, reporter):
            """Get reporter's current stake."""
            return self.data.reporters.get(reporter, default=sp.mutez(0))
        
        @sp.onchain_view
        def get_tally(self, market_id):
            """Get current vote tally for a market."""
            return self.data.tally.get(
                market_id,
                default=sp.record(over_votes=sp.nat(0), under_votes=sp.nat(0), reveals_count=sp.nat(0))
            )
        
        @sp.onchain_view
        def is_finalized(self, market_id):
            """Check if market resolution is finalized."""
            return self.data.finalized.get(market_id, default=False)


# ============================================================================
# Helper function to compute commit hash
# ============================================================================
def compute_commit_hash(result, salt):
    """
    Compute commit hash off-chain.
    Use this to generate the hash before calling commit().
    
    Args:
        result: Side.OVER or Side.UNDER
        salt: random bytes
    
    Returns:
        bytes: keccak hash of packed (result, salt)
    """
    return sp.keccak(sp.pack((result, salt)))


# ============================================================================
# Compilation target
# ============================================================================
if "main" in __name__:
    @sp.add_test()
    def test():
        scenario = sp.test_scenario("OracleCommitReveal Compilation", main)
        
        admin = sp.test_account("admin").address
        market = sp.test_account("market").address
        
        contract = main.OracleCommitReveal(
            admin=admin,
            market_contract=market,
            min_stake=sp.tez(10),
            min_quorum=sp.nat(3),
            commit_duration=sp.int(3600),      # 1 hour
            reveal_duration=sp.int(86400),     # 24 hours
            slash_absent_bps=sp.nat(1000),     # 10%
            slash_wrong_bps=sp.nat(3000)       # 30%
        )
        scenario += contract
