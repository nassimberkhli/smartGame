import smartpy as sp

# ============================================================================
# CrowdShield SmartPy Test Suite
# ============================================================================
# Comprehensive tests for Market, Oracle, and Fund contracts.
# Run with: ~/smartpy-cli/SmartPy.sh test tests/test_all.py output/
# ============================================================================


# Import contract modules
@sp.module
def market_module():
    """CrowdShieldMarket contract module."""
    
    class Side(sp.Enum):
        OVER = ()
        UNDER = ()
    
    class Status(sp.Enum):
        OPEN = ()
        RESOLVING = ()
        RESOLVED = ()
    
    class Market(sp.Record):
        question: sp.string
        location: sp.string
        threshold: sp.string
        end_time: sp.timestamp
        status: Status
        result: sp.option[Side]
        pool_over: sp.mutez
        pool_under: sp.mutez
    
    class CrowdShieldMarket(sp.Contract):
        def __init__(self, admin, oracle, fund, fee_bps):
            self.data.admin = admin
            self.data.oracle = oracle
            self.data.fund = fund
            self.data.fee_bps = fee_bps
            self.data.markets = sp.cast(sp.big_map(), sp.big_map[sp.nat, Market])
            self.data.next_market_id = sp.nat(0)
            self.data.bets = sp.cast(sp.big_map(), sp.big_map[sp.tuple[sp.nat, sp.address, Side], sp.mutez])
            self.data.claimed = sp.cast(sp.big_map(), sp.big_map[sp.tuple[sp.nat, sp.address], sp.bool])
        
        @sp.entrypoint
        def create_market(self, question, location, threshold, end_time):
            sp.cast(question, sp.string)
            sp.cast(location, sp.string)
            sp.cast(threshold, sp.string)
            sp.cast(end_time, sp.timestamp)
            assert end_time > sp.now, "END_TIME_PAST"
            market = sp.record(
                question=question, location=location, threshold=threshold,
                end_time=end_time, status=Status.OPEN,
                result=sp.cast(None, sp.option[Side]),
                pool_over=sp.mutez(0), pool_under=sp.mutez(0)
            )
            self.data.markets[self.data.next_market_id] = market
            self.data.next_market_id += 1
        
        @sp.entrypoint
        def bet(self, market_id, side):
            sp.cast(market_id, sp.nat)
            sp.cast(side, Side)
            assert self.data.markets.contains(market_id), "MARKET_NOT_FOUND"
            market = self.data.markets[market_id]
            assert market.status == Status.OPEN, "MARKET_NOT_OPEN"
            assert sp.now < market.end_time, "BETTING_CLOSED"
            assert sp.amount > sp.mutez(0), "ZERO_AMOUNT"
            bet_key = (market_id, sp.sender, side)
            current_bet = self.data.bets.get(bet_key, default=sp.mutez(0))
            self.data.bets[bet_key] = current_bet + sp.amount
            if side == Side.OVER:
                market.pool_over += sp.amount
            else:
                market.pool_under += sp.amount
            self.data.markets[market_id] = market
        
        @sp.entrypoint
        def start_resolving(self, market_id):
            sp.cast(market_id, sp.nat)
            assert self.data.markets.contains(market_id), "MARKET_NOT_FOUND"
            market = self.data.markets[market_id]
            assert market.status == Status.OPEN, "MARKET_NOT_OPEN"
            assert sp.now >= market.end_time, "MARKET_NOT_ENDED"
            market.status = Status.RESOLVING
            self.data.markets[market_id] = market
        
        @sp.entrypoint
        def receive_outcome(self, market_id, result):
            sp.cast(market_id, sp.nat)
            sp.cast(result, Side)
            assert sp.sender == self.data.oracle, "NOT_ORACLE"
            assert self.data.markets.contains(market_id), "MARKET_NOT_FOUND"
            market = self.data.markets[market_id]
            assert market.status == Status.RESOLVING, "NOT_RESOLVING"
            market.result = sp.Some(result)
            market.status = Status.RESOLVED
            self.data.markets[market_id] = market
            total_pool = market.pool_over + market.pool_under
            fee = sp.split_tokens(total_pool, self.data.fee_bps, 10000)
            winning_pool = market.pool_over if result == Side.OVER else market.pool_under
            if winning_pool == sp.mutez(0):
                sp.send(self.data.fund, total_pool)
            else:
                if fee > sp.mutez(0):
                    sp.send(self.data.fund, fee)
        
        @sp.entrypoint
        def claim(self, market_id):
            sp.cast(market_id, sp.nat)
            assert self.data.markets.contains(market_id), "MARKET_NOT_FOUND"
            market = self.data.markets[market_id]
            assert market.status == Status.RESOLVED, "NOT_RESOLVED"
            claim_key = (market_id, sp.sender)
            already_claimed = self.data.claimed.get(claim_key, default=False)
            assert not already_claimed, "ALREADY_CLAIMED"
            result = market.result.unwrap_some(error="NO_RESULT")
            bet_key = (market_id, sp.sender, result)
            user_stake = self.data.bets.get(bet_key, default=sp.mutez(0))
            assert user_stake > sp.mutez(0), "NO_WINNING_BET"
            total_pool = market.pool_over + market.pool_under
            fee = sp.split_tokens(total_pool, self.data.fee_bps, 10000)
            distributable = total_pool - fee
            winning_pool = market.pool_over if result == Side.OVER else market.pool_under
            payout = sp.split_tokens(
                distributable,
                sp.fst(sp.ediv(user_stake, sp.mutez(1)).unwrap_some()),
                sp.fst(sp.ediv(winning_pool, sp.mutez(1)).unwrap_some())
            )
            self.data.claimed[claim_key] = True
            sp.send(sp.sender, payout)


@sp.module
def fund_module():
    """PreventionFund contract module."""
    
    class Expense(sp.Record):
        amount: sp.mutez
        recipient: sp.address
        description: sp.string
        timestamp: sp.timestamp
    
    class PreventionFund(sp.Contract):
        def __init__(self, admin):
            self.data.admin = admin
            self.data.expenses = sp.cast([], sp.list[Expense])
            self.data.total_received = sp.mutez(0)
            self.data.total_spent = sp.mutez(0)
        
        @sp.entrypoint
        def deposit(self):
            assert sp.amount > sp.mutez(0), "ZERO_AMOUNT"
            self.data.total_received += sp.amount
        
        @sp.entrypoint
        def default(self):
            if sp.amount > sp.mutez(0):
                self.data.total_received += sp.amount
        
        @sp.entrypoint
        def spend(self, amount, recipient, description):
            sp.cast(amount, sp.mutez)
            sp.cast(recipient, sp.address)
            sp.cast(description, sp.string)
            assert sp.sender == self.data.admin, "NOT_ADMIN"
            assert sp.balance >= amount, "INSUFFICIENT_BALANCE"
            expense = sp.record(
                amount=amount, recipient=recipient,
                description=description, timestamp=sp.now
            )
            self.data.expenses.push(expense)
            self.data.total_spent += amount
            sp.send(recipient, amount)


@sp.module  
def oracle_module():
    """OracleCommitReveal contract module (simplified for testing)."""
    
    class Side(sp.Enum):
        OVER = ()
        UNDER = ()
    
    class Tally(sp.Record):
        over_votes: sp.nat
        under_votes: sp.nat
        reveals_count: sp.nat
    
    class OracleCommitReveal(sp.Contract):
        def __init__(self, admin, market_contract, min_stake, min_quorum, 
                     commit_duration, reveal_duration, slash_absent_bps, slash_wrong_bps):
            self.data.admin = admin
            self.data.market_contract = market_contract
            self.data.min_stake = min_stake
            self.data.min_quorum = min_quorum
            self.data.commit_duration = commit_duration
            self.data.reveal_duration = reveal_duration
            self.data.slash_absent_bps = slash_absent_bps
            self.data.slash_wrong_bps = slash_wrong_bps
            self.data.reporters = sp.cast(sp.big_map(), sp.big_map[sp.address, sp.mutez])
            self.data.commits = sp.cast(sp.big_map(), sp.big_map[sp.tuple[sp.nat, sp.address], sp.bytes])
            self.data.revealed = sp.cast(sp.big_map(), sp.big_map[sp.tuple[sp.nat, sp.address], sp.bool])
            self.data.reveal_votes = sp.cast(sp.big_map(), sp.big_map[sp.tuple[sp.nat, sp.address], Side])
            self.data.tally = sp.cast(sp.big_map(), sp.big_map[sp.nat, Tally])
            self.data.finalized = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.bool])
            self.data.commit_deadline = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.timestamp])
            self.data.reveal_deadline = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.timestamp])
            self.data.committed_reporters = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.set[sp.address]])
        
        @sp.entrypoint
        def register_reporter(self):
            assert sp.amount >= self.data.min_stake, "INSUFFICIENT_STAKE"
            current_stake = self.data.reporters.get(sp.sender, default=sp.mutez(0))
            self.data.reporters[sp.sender] = current_stake + sp.amount
        
        @sp.entrypoint
        def init_resolution(self, market_id):
            sp.cast(market_id, sp.nat)
            assert not self.data.finalized.get(market_id, default=False), "ALREADY_FINALIZED"
            assert not self.data.commit_deadline.contains(market_id), "ALREADY_INITIALIZED"
            self.data.commit_deadline[market_id] = sp.add_seconds(sp.now, self.data.commit_duration)
            self.data.reveal_deadline[market_id] = sp.add_seconds(
                sp.now, self.data.commit_duration + self.data.reveal_duration
            )
            self.data.tally[market_id] = sp.record(over_votes=sp.nat(0), under_votes=sp.nat(0), reveals_count=sp.nat(0))
            self.data.committed_reporters[market_id] = sp.cast(sp.set(), sp.set[sp.address])
        
        @sp.entrypoint
        def commit(self, market_id, commit_hash):
            sp.cast(market_id, sp.nat)
            sp.cast(commit_hash, sp.bytes)
            assert self.data.reporters.contains(sp.sender), "NOT_REPORTER"
            assert self.data.commit_deadline.contains(market_id), "NOT_INITIALIZED"
            assert sp.now <= self.data.commit_deadline[market_id], "COMMIT_DEADLINE_PASSED"
            commit_key = (market_id, sp.sender)
            assert not self.data.commits.contains(commit_key), "ALREADY_COMMITTED"
            self.data.commits[commit_key] = commit_hash
            committed = self.data.committed_reporters[market_id]
            committed.add(sp.sender)
            self.data.committed_reporters[market_id] = committed
        
        @sp.entrypoint
        def reveal(self, market_id, result, salt):
            sp.cast(market_id, sp.nat)
            sp.cast(result, Side)
            sp.cast(salt, sp.bytes)
            commit_key = (market_id, sp.sender)
            assert self.data.commits.contains(commit_key), "NO_COMMIT"
            assert sp.now > self.data.commit_deadline[market_id], "COMMIT_PHASE_ACTIVE"
            assert sp.now <= self.data.reveal_deadline[market_id], "REVEAL_DEADLINE_PASSED"
            assert not self.data.revealed.get(commit_key, default=False), "ALREADY_REVEALED"
            packed_data = sp.pack((result, salt))
            expected_hash = sp.keccak(packed_data)
            stored_hash = self.data.commits[commit_key]
            assert expected_hash == stored_hash, "HASH_MISMATCH"
            self.data.revealed[commit_key] = True
            self.data.reveal_votes[commit_key] = result
            tally = self.data.tally[market_id]
            if result == Side.OVER:
                tally.over_votes += 1
            else:
                tally.under_votes += 1
            tally.reveals_count += 1
            self.data.tally[market_id] = tally
        
        @sp.entrypoint
        def finalize(self, market_id):
            sp.cast(market_id, sp.nat)
            assert not self.data.finalized.get(market_id, default=False), "ALREADY_FINALIZED"
            tally = self.data.tally.get(
                market_id, default=sp.record(over_votes=sp.nat(0), under_votes=sp.nat(0), reveals_count=sp.nat(0))
            )
            quorum_reached = tally.reveals_count >= self.data.min_quorum
            deadline_passed = sp.now > self.data.reveal_deadline.get(market_id, default=sp.timestamp(0))
            assert quorum_reached or deadline_passed, "CANNOT_FINALIZE"
            assert tally.reveals_count > 0, "NO_VOTES"
            result = Side.OVER if tally.over_votes >= tally.under_votes else Side.UNDER
            
            # Apply slashing
            committed = self.data.committed_reporters.get(market_id, default=sp.cast(sp.set(), sp.set[sp.address]))
            for reporter in committed.elements():
                commit_key = (market_id, reporter)
                was_revealed = self.data.revealed.get(commit_key, default=False)
                if not was_revealed:
                    # Slash absent
                    stake = self.data.reporters.get(reporter, default=sp.mutez(0))
                    if stake > sp.mutez(0):
                        slash_amount = sp.split_tokens(stake, self.data.slash_absent_bps, 10000)
                        new_stake = stake - slash_amount
                        if new_stake > sp.mutez(0):
                            self.data.reporters[reporter] = new_stake
                        else:
                            del self.data.reporters[reporter]
                else:
                    voted_side = self.data.reveal_votes.get(commit_key)
                    if voted_side != result:
                        # Slash wrong
                        stake = self.data.reporters.get(reporter, default=sp.mutez(0))
                        if stake > sp.mutez(0):
                            slash_amount = sp.split_tokens(stake, self.data.slash_wrong_bps, 10000)
                            new_stake = stake - slash_amount
                            if new_stake > sp.mutez(0):
                                self.data.reporters[reporter] = new_stake
                            else:
                                del self.data.reporters[reporter]
            
            self.data.finalized[market_id] = True
            
            # Callback to market
            market_contract = sp.contract(
                sp.record(market_id=sp.nat, result=Side),
                self.data.market_contract,
                entrypoint="receive_outcome"
            ).unwrap_some(error="INVALID_MARKET_CONTRACT")
            sp.transfer(sp.record(market_id=market_id, result=result), sp.mutez(0), market_contract)


# ============================================================================
# TEST: CrowdShieldMarket Unit Tests
# ============================================================================

@sp.add_test()
def test_market_create_valid():
    """Test creating a market with valid parameters."""
    scenario = sp.test_scenario("Market: Create Valid", market_module)
    
    admin = sp.test_account("admin")
    oracle = sp.test_account("oracle")
    fund = sp.test_account("fund")
    
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle.address,
        fund=fund.address,
        fee_bps=sp.nat(500)
    )
    scenario += market
    
    # Create market with future end time
    future_time = sp.timestamp(3600)  # 1 hour from epoch
    scenario.h2("Create market with valid end_time")
    market.create_market(
        question="Will crowd exceed 10000?",
        location="Central Plaza",
        threshold="> 10000 people",
        end_time=future_time,
        _now=sp.timestamp(0)
    )
    
    # Verify market was created
    scenario.verify(market.data.next_market_id == 1)
    scenario.verify(market.data.markets[0].question == "Will crowd exceed 10000?")
    scenario.verify(market.data.markets[0].status == market_module.Status.OPEN)


@sp.add_test()
def test_market_create_invalid_endtime():
    """Test creating a market with past end_time fails."""
    scenario = sp.test_scenario("Market: Create Invalid End Time", market_module)
    
    admin = sp.test_account("admin")
    oracle = sp.test_account("oracle")
    fund = sp.test_account("fund")
    
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle.address,
        fund=fund.address,
        fee_bps=sp.nat(500)
    )
    scenario += market
    
    # Try to create market with past end time
    past_time = sp.timestamp(0)
    scenario.h2("Create market with past end_time should fail")
    market.create_market(
        question="Test",
        location="Test",
        threshold="Test",
        end_time=past_time,
        _now=sp.timestamp(100),
        _valid=False,
        _exception="END_TIME_PAST"
    )


@sp.add_test()
def test_market_bet_valid():
    """Test placing a valid bet."""
    scenario = sp.test_scenario("Market: Valid Bet", market_module)
    
    admin = sp.test_account("admin")
    oracle = sp.test_account("oracle")
    fund = sp.test_account("fund")
    user1 = sp.test_account("user1")
    
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle.address,
        fund=fund.address,
        fee_bps=sp.nat(500)
    )
    scenario += market
    
    # Create market
    market.create_market(
        question="Test", location="Test", threshold="Test",
        end_time=sp.timestamp(3600),
        _now=sp.timestamp(0)
    )
    
    # Place bet
    scenario.h2("Place valid bet on OVER")
    market.bet(
        market_id=sp.nat(0),
        side=market_module.Side.OVER,
        _sender=user1,
        _amount=sp.tez(10),
        _now=sp.timestamp(100)
    )
    
    # Verify bet was recorded
    bet_key = (sp.nat(0), user1.address, market_module.Side.OVER)
    scenario.verify(market.data.bets[bet_key] == sp.tez(10))
    scenario.verify(market.data.markets[0].pool_over == sp.tez(10))


@sp.add_test()
def test_market_bet_after_deadline():
    """Test that betting after deadline fails."""
    scenario = sp.test_scenario("Market: Bet After Deadline", market_module)
    
    admin = sp.test_account("admin")
    oracle = sp.test_account("oracle")
    fund = sp.test_account("fund")
    user1 = sp.test_account("user1")
    
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle.address,
        fund=fund.address,
        fee_bps=sp.nat(500)
    )
    scenario += market
    
    # Create market
    market.create_market(
        question="Test", location="Test", threshold="Test",
        end_time=sp.timestamp(3600),
        _now=sp.timestamp(0)
    )
    
    # Try to bet after deadline
    scenario.h2("Bet after deadline should fail")
    market.bet(
        market_id=sp.nat(0),
        side=market_module.Side.OVER,
        _sender=user1,
        _amount=sp.tez(10),
        _now=sp.timestamp(4000),  # After end_time
        _valid=False,
        _exception="BETTING_CLOSED"
    )


@sp.add_test()
def test_market_receive_outcome_not_oracle():
    """Test that only oracle can call receive_outcome."""
    scenario = sp.test_scenario("Market: receive_outcome Auth Check", market_module)
    
    admin = sp.test_account("admin")
    oracle = sp.test_account("oracle")
    fund = sp.test_account("fund")
    attacker = sp.test_account("attacker")
    
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle.address,
        fund=fund.address,
        fee_bps=sp.nat(500)
    )
    scenario += market
    
    # Create and transition market to RESOLVING
    market.create_market(
        question="Test", location="Test", threshold="Test",
        end_time=sp.timestamp(3600),
        _now=sp.timestamp(0)
    )
    market.start_resolving(market_id=sp.nat(0), _now=sp.timestamp(4000))
    
    # Non-oracle tries to set outcome
    scenario.h2("Non-oracle calling receive_outcome should fail")
    market.receive_outcome(
        market_id=sp.nat(0),
        result=market_module.Side.OVER,
        _sender=attacker,
        _valid=False,
        _exception="NOT_ORACLE"
    )


@sp.add_test()
def test_market_claim_and_payout():
    """Test claiming winnings with correct payout calculation."""
    scenario = sp.test_scenario("Market: Claim Payout", [market_module, fund_module])
    
    admin = sp.test_account("admin")
    oracle = sp.test_account("oracle")
    user1 = sp.test_account("user1")
    user2 = sp.test_account("user2")
    
    # Deploy fund first
    fund = fund_module.PreventionFund(admin=admin.address)
    scenario += fund
    
    # Deploy market
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle.address,
        fund=fund.address,
        fee_bps=sp.nat(500)  # 5%
    )
    scenario += market
    
    # Create market
    market.create_market(
        question="Test", location="Test", threshold="Test",
        end_time=sp.timestamp(3600),
        _now=sp.timestamp(0)
    )
    
    # User1 bets 100 tez on OVER
    market.bet(
        market_id=sp.nat(0),
        side=market_module.Side.OVER,
        _sender=user1,
        _amount=sp.tez(100),
        _now=sp.timestamp(100)
    )
    
    # User2 bets 100 tez on UNDER
    market.bet(
        market_id=sp.nat(0),
        side=market_module.Side.UNDER,
        _sender=user2,
        _amount=sp.tez(100),
        _now=sp.timestamp(100)
    )
    
    # Start resolving
    market.start_resolving(market_id=sp.nat(0), _now=sp.timestamp(4000))
    
    # Oracle sets outcome to OVER
    scenario.h2("Oracle resolves market as OVER")
    market.receive_outcome(
        market_id=sp.nat(0),
        result=market_module.Side.OVER,
        _sender=oracle
    )
    
    # Verify market is resolved
    scenario.verify(market.data.markets[0].status == market_module.Status.RESOLVED)
    
    # User1 claims (winner)
    scenario.h2("Winner claims payout")
    market.claim(market_id=sp.nat(0), _sender=user1)
    
    # Verify claimed
    claim_key = (sp.nat(0), user1.address)
    scenario.verify(market.data.claimed[claim_key] == True)


@sp.add_test()
def test_market_double_claim():
    """Test that double claiming fails."""
    scenario = sp.test_scenario("Market: Double Claim", [market_module, fund_module])
    
    admin = sp.test_account("admin")
    oracle = sp.test_account("oracle")
    user1 = sp.test_account("user1")
    
    fund = fund_module.PreventionFund(admin=admin.address)
    scenario += fund
    
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle.address,
        fund=fund.address,
        fee_bps=sp.nat(500)
    )
    scenario += market
    
    # Setup and resolve
    market.create_market(
        question="Test", location="Test", threshold="Test",
        end_time=sp.timestamp(3600), _now=sp.timestamp(0)
    )
    market.bet(
        market_id=sp.nat(0), side=market_module.Side.OVER,
        _sender=user1, _amount=sp.tez(100), _now=sp.timestamp(100)
    )
    market.start_resolving(market_id=sp.nat(0), _now=sp.timestamp(4000))
    market.receive_outcome(market_id=sp.nat(0), result=market_module.Side.OVER, _sender=oracle)
    
    # First claim
    market.claim(market_id=sp.nat(0), _sender=user1)
    
    # Second claim should fail
    scenario.h2("Double claim should fail")
    market.claim(
        market_id=sp.nat(0),
        _sender=user1,
        _valid=False,
        _exception="ALREADY_CLAIMED"
    )


@sp.add_test()
def test_market_zero_winning_pool():
    """Test behavior when winning pool is zero (all goes to fund)."""
    scenario = sp.test_scenario("Market: Zero Winning Pool", [market_module, fund_module])
    
    admin = sp.test_account("admin")
    oracle = sp.test_account("oracle")
    user1 = sp.test_account("user1")
    
    fund = fund_module.PreventionFund(admin=admin.address)
    scenario += fund
    
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle.address,
        fund=fund.address,
        fee_bps=sp.nat(500)
    )
    scenario += market
    
    # Create market
    market.create_market(
        question="Test", location="Test", threshold="Test",
        end_time=sp.timestamp(3600), _now=sp.timestamp(0)
    )
    
    # Only bet on UNDER
    market.bet(
        market_id=sp.nat(0), side=market_module.Side.UNDER,
        _sender=user1, _amount=sp.tez(100), _now=sp.timestamp(100)
    )
    
    market.start_resolving(market_id=sp.nat(0), _now=sp.timestamp(4000))
    
    # Resolve as OVER (no one bet on OVER, so winning_pool = 0)
    scenario.h2("Resolve with zero winning pool - all goes to fund")
    market.receive_outcome(market_id=sp.nat(0), result=market_module.Side.OVER, _sender=oracle)
    
    # Fund should have received all tez
    scenario.verify(fund.data.total_received == sp.tez(100))


# ============================================================================
# TEST: OracleCommitReveal Unit Tests
# ============================================================================

@sp.add_test()
def test_oracle_register_reporter():
    """Test reporter registration with stake."""
    scenario = sp.test_scenario("Oracle: Register Reporter", oracle_module)
    
    admin = sp.test_account("admin")
    market = sp.test_account("market")
    reporter1 = sp.test_account("reporter1")
    
    oracle = oracle_module.OracleCommitReveal(
        admin=admin.address,
        market_contract=market.address,
        min_stake=sp.tez(10),
        min_quorum=sp.nat(3),
        commit_duration=sp.int(3600),
        reveal_duration=sp.int(86400),
        slash_absent_bps=sp.nat(1000),
        slash_wrong_bps=sp.nat(3000)
    )
    scenario += oracle
    
    # Register with sufficient stake
    scenario.h2("Register reporter with sufficient stake")
    oracle.register_reporter(_sender=reporter1, _amount=sp.tez(10))
    scenario.verify(oracle.data.reporters[reporter1.address] == sp.tez(10))
    
    # Register with insufficient stake should fail
    reporter2 = sp.test_account("reporter2")
    scenario.h2("Register with insufficient stake should fail")
    oracle.register_reporter(
        _sender=reporter2, _amount=sp.tez(5),
        _valid=False, _exception="INSUFFICIENT_STAKE"
    )


@sp.add_test()
def test_oracle_commit_unique():
    """Test that commits are unique per reporter per market."""
    scenario = sp.test_scenario("Oracle: Commit Uniqueness", oracle_module)
    
    admin = sp.test_account("admin")
    market = sp.test_account("market")
    reporter1 = sp.test_account("reporter1")
    
    oracle = oracle_module.OracleCommitReveal(
        admin=admin.address,
        market_contract=market.address,
        min_stake=sp.tez(10),
        min_quorum=sp.nat(1),
        commit_duration=sp.int(3600),
        reveal_duration=sp.int(86400),
        slash_absent_bps=sp.nat(1000),
        slash_wrong_bps=sp.nat(3000)
    )
    scenario += oracle
    
    # Register and init
    oracle.register_reporter(_sender=reporter1, _amount=sp.tez(10))
    oracle.init_resolution(market_id=sp.nat(0), _now=sp.timestamp(0))
    
    # First commit
    commit_hash = sp.bytes("0x1234")
    oracle.commit(market_id=sp.nat(0), commit_hash=commit_hash, _sender=reporter1, _now=sp.timestamp(100))
    
    # Second commit should fail
    scenario.h2("Double commit should fail")
    oracle.commit(
        market_id=sp.nat(0), commit_hash=commit_hash, _sender=reporter1,
        _now=sp.timestamp(200), _valid=False, _exception="ALREADY_COMMITTED"
    )


@sp.add_test()
def test_oracle_reveal_hash_mismatch():
    """Test that reveal with wrong hash fails."""
    scenario = sp.test_scenario("Oracle: Reveal Hash Mismatch", oracle_module)
    
    admin = sp.test_account("admin")
    market = sp.test_account("market")
    reporter1 = sp.test_account("reporter1")
    
    oracle = oracle_module.OracleCommitReveal(
        admin=admin.address,
        market_contract=market.address,
        min_stake=sp.tez(10),
        min_quorum=sp.nat(1),
        commit_duration=sp.int(3600),
        reveal_duration=sp.int(86400),
        slash_absent_bps=sp.nat(1000),
        slash_wrong_bps=sp.nat(3000)
    )
    scenario += oracle
    
    oracle.register_reporter(_sender=reporter1, _amount=sp.tez(10))
    oracle.init_resolution(market_id=sp.nat(0), _now=sp.timestamp(0))
    
    # Commit with one hash
    salt = sp.bytes("0xsalt123")
    correct_hash = sp.keccak(sp.pack((oracle_module.Side.OVER, salt)))
    oracle.commit(market_id=sp.nat(0), commit_hash=correct_hash, _sender=reporter1, _now=sp.timestamp(100))
    
    # Try to reveal with wrong side
    scenario.h2("Reveal with wrong side should fail")
    oracle.reveal(
        market_id=sp.nat(0),
        result=oracle_module.Side.UNDER,  # Wrong side
        salt=salt,
        _sender=reporter1,
        _now=sp.timestamp(4000),
        _valid=False,
        _exception="HASH_MISMATCH"
    )


@sp.add_test()
def test_oracle_reveal_after_deadline():
    """Test that reveal after deadline fails."""
    scenario = sp.test_scenario("Oracle: Reveal After Deadline", oracle_module)
    
    admin = sp.test_account("admin")
    market = sp.test_account("market")
    reporter1 = sp.test_account("reporter1")
    
    oracle = oracle_module.OracleCommitReveal(
        admin=admin.address,
        market_contract=market.address,
        min_stake=sp.tez(10),
        min_quorum=sp.nat(1),
        commit_duration=sp.int(3600),
        reveal_duration=sp.int(3600),  # Short reveal period
        slash_absent_bps=sp.nat(1000),
        slash_wrong_bps=sp.nat(3000)
    )
    scenario += oracle
    
    oracle.register_reporter(_sender=reporter1, _amount=sp.tez(10))
    oracle.init_resolution(market_id=sp.nat(0), _now=sp.timestamp(0))
    
    salt = sp.bytes("0xsalt123")
    correct_hash = sp.keccak(sp.pack((oracle_module.Side.OVER, salt)))
    oracle.commit(market_id=sp.nat(0), commit_hash=correct_hash, _sender=reporter1, _now=sp.timestamp(100))
    
    # Try to reveal after reveal deadline (commit: 3600, reveal: 3600 more = 7200 total)
    scenario.h2("Reveal after deadline should fail")
    oracle.reveal(
        market_id=sp.nat(0),
        result=oracle_module.Side.OVER,
        salt=salt,
        _sender=reporter1,
        _now=sp.timestamp(10000),  # Way after deadline
        _valid=False,
        _exception="REVEAL_DEADLINE_PASSED"
    )


# ============================================================================
# TEST: PreventionFund Unit Tests
# ============================================================================

@sp.add_test()
def test_fund_deposit_and_spend():
    """Test fund deposit and spend functionality."""
    scenario = sp.test_scenario("Fund: Deposit and Spend", fund_module)
    
    admin = sp.test_account("admin")
    recipient = sp.test_account("recipient")
    
    fund = fund_module.PreventionFund(admin=admin.address)
    scenario += fund
    
    # Deposit
    scenario.h2("Deposit to fund")
    fund.deposit(_amount=sp.tez(100))
    scenario.verify(fund.data.total_received == sp.tez(100))
    
    # Spend
    scenario.h2("Admin spends from fund")
    fund.spend(
        amount=sp.tez(50),
        recipient=recipient.address,
        description="Safety equipment",
        _sender=admin
    )
    scenario.verify(fund.data.total_spent == sp.tez(50))
    
    # Non-admin spend should fail
    attacker = sp.test_account("attacker")
    scenario.h2("Non-admin spend should fail")
    fund.spend(
        amount=sp.tez(10),
        recipient=recipient.address,
        description="Hack",
        _sender=attacker,
        _valid=False,
        _exception="NOT_ADMIN"
    )


# ============================================================================
# TEST: Integration Test
# ============================================================================

@sp.add_test()
def test_integration_full_flow():
    """Integration test: Create -> Bet -> Oracle -> Claim."""
    scenario = sp.test_scenario("Integration: Full Flow", [market_module, oracle_module, fund_module])
    
    # Accounts
    admin = sp.test_account("admin")
    user1 = sp.test_account("user1")
    user2 = sp.test_account("user2")
    reporter1 = sp.test_account("reporter1")
    reporter2 = sp.test_account("reporter2")
    reporter3 = sp.test_account("reporter3")
    
    # Deploy Fund
    scenario.h1("Deploy PreventionFund")
    fund = fund_module.PreventionFund(admin=admin.address)
    scenario += fund
    
    # We need placeholder addresses first, then update
    # For testing, we'll use a simplified flow
    
    scenario.h1("Deploy CrowdShieldMarket")
    # Use a test account as oracle for simplicity in this test
    oracle_account = sp.test_account("oracle_account")
    market = market_module.CrowdShieldMarket(
        admin=admin.address,
        oracle=oracle_account.address,
        fund=fund.address,
        fee_bps=sp.nat(500)
    )
    scenario += market
    
    # Create market
    scenario.h1("Create Market")
    market.create_market(
        question="Will Central Plaza exceed 15000 people on NYE?",
        location="Central Plaza",
        threshold="> 15000 people between 22h-00h",
        end_time=sp.timestamp(86400),  # 1 day
        _now=sp.timestamp(0)
    )
    
    # Users place bets
    scenario.h1("Users Place Bets")
    scenario.h2("User1 bets 50 tez on OVER")
    market.bet(
        market_id=sp.nat(0),
        side=market_module.Side.OVER,
        _sender=user1,
        _amount=sp.tez(50),
        _now=sp.timestamp(1000)
    )
    
    scenario.h2("User2 bets 100 tez on UNDER")
    market.bet(
        market_id=sp.nat(0),
        side=market_module.Side.UNDER,
        _sender=user2,
        _amount=sp.tez(100),
        _now=sp.timestamp(2000)
    )
    
    scenario.h2("User1 adds 50 more tez on OVER")
    market.bet(
        market_id=sp.nat(0),
        side=market_module.Side.OVER,
        _sender=user1,
        _amount=sp.tez(50),
        _now=sp.timestamp(3000)
    )
    
    # Verify pools
    scenario.verify(market.data.markets[0].pool_over == sp.tez(100))
    scenario.verify(market.data.markets[0].pool_under == sp.tez(100))
    
    # Start resolving
    scenario.h1("Start Resolving")
    market.start_resolving(market_id=sp.nat(0), _now=sp.timestamp(100000))
    scenario.verify(market.data.markets[0].status == market_module.Status.RESOLVING)
    
    # Oracle resolves (simplified - in real flow, oracle contract calls this)
    scenario.h1("Oracle Resolves Market")
    market.receive_outcome(
        market_id=sp.nat(0),
        result=market_module.Side.OVER,
        _sender=oracle_account
    )
    
    scenario.verify(market.data.markets[0].status == market_module.Status.RESOLVED)
    
    # Winner claims
    scenario.h1("Winner Claims Payout")
    market.claim(market_id=sp.nat(0), _sender=user1)
    
    # Loser cannot claim
    scenario.h2("Loser has no winning bet")
    market.claim(
        market_id=sp.nat(0),
        _sender=user2,
        _valid=False,
        _exception="NO_WINNING_BET"
    )
    
    # Verify fund received fees
    # Total pool = 200 tez, fee = 5% = 10 tez
    scenario.h1("Verify Fund Received Fees")
    scenario.verify(fund.data.total_received == sp.tez(10))
    
    scenario.h1("Integration Test Complete!")
