import smartpy as sp

# ============================================================================
# CrowdShield Market Contract
# ============================================================================
# A pari-mutuel prediction market for crowd safety predictions on Tezos.
# Implements pull-based payments (claim pattern) and oracle-based resolution.
# ============================================================================


@sp.module
def main():
    # ========================================================================
    # Types
    # ========================================================================
    
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
    
    # ========================================================================
    # CrowdShieldMarket Contract
    # ========================================================================
    
    class CrowdShieldMarket(sp.Contract):
        """
        Main prediction market contract.
        
        Storage:
        - admin: Contract administrator
        - oracle: Address of the OracleCommitReveal contract
        - fund: Address of the PreventionFund contract
        - fee_bps: Fee in basis points (e.g., 500 = 5%)
        - markets: Big map of market_id -> Market
        - next_market_id: Counter for market IDs
        - bets: Big map of (market_id, user, side) -> staked amount
        - claimed: Big map of (market_id, user) -> claimed status
        """
        
        def __init__(self, admin, oracle, fund, fee_bps):
            self.data.admin = admin
            self.data.oracle = oracle
            self.data.fund = fund
            self.data.fee_bps = fee_bps
            self.data.markets = sp.cast(
                sp.big_map(),
                sp.big_map[sp.nat, Market]
            )
            self.data.next_market_id = sp.nat(0)
            self.data.bets = sp.cast(
                sp.big_map(),
                sp.big_map[sp.tuple[sp.nat, sp.address, Side], sp.mutez]
            )
            self.data.claimed = sp.cast(
                sp.big_map(),
                sp.big_map[sp.tuple[sp.nat, sp.address], sp.bool]
            )
        
        # ====================================================================
        # Entrypoint: create_market
        # ====================================================================
        @sp.entrypoint
        def create_market(self, question, location, threshold, end_time):
            """
            Create a new prediction market.
            
            Preconditions:
            - end_time > now
            
            Effects:
            - Creates a new market with OPEN status
            - Increments next_market_id
            """
            sp.cast(question, sp.string)
            sp.cast(location, sp.string)
            sp.cast(threshold, sp.string)
            sp.cast(end_time, sp.timestamp)
            
            # Validate end_time is in the future
            assert end_time > sp.now, "END_TIME_PAST"
            
            # Create market
            market = sp.record(
                question=question,
                location=location,
                threshold=threshold,
                end_time=end_time,
                status=Status.OPEN,
                result=sp.cast(None, sp.option[Side]),
                pool_over=sp.mutez(0),
                pool_under=sp.mutez(0)
            )
            
            self.data.markets[self.data.next_market_id] = market
            self.data.next_market_id += 1
        
        # ====================================================================
        # Entrypoint: bet
        # ====================================================================
        @sp.entrypoint
        def bet(self, market_id, side):
            """
            Place a bet on a market side (OVER or UNDER).
            
            Preconditions:
            - Market exists and is OPEN
            - now < end_time
            - sp.amount > 0
            
            Effects:
            - Adds bet amount to user's stake for this side
            - Updates pool totals
            """
            sp.cast(market_id, sp.nat)
            sp.cast(side, Side)
            
            # Validate market exists
            assert self.data.markets.contains(market_id), "MARKET_NOT_FOUND"
            
            market = self.data.markets[market_id]
            
            # Validate market is open
            assert market.status == Status.OPEN, "MARKET_NOT_OPEN"
            
            # Validate before deadline
            assert sp.now < market.end_time, "BETTING_CLOSED"
            
            # Validate amount
            assert sp.amount > sp.mutez(0), "ZERO_AMOUNT"
            
            # Update user's bet
            bet_key = (market_id, sp.sender, side)
            current_bet = self.data.bets.get(bet_key, default=sp.mutez(0))
            self.data.bets[bet_key] = current_bet + sp.amount
            
            # Update pool
            if side == Side.OVER:
                market.pool_over += sp.amount
            else:
                market.pool_under += sp.amount
            
            self.data.markets[market_id] = market
        
        # ====================================================================
        # Entrypoint: start_resolving
        # ====================================================================
        @sp.entrypoint
        def start_resolving(self, market_id):
            """
            Transition market from OPEN to RESOLVING.
            
            Preconditions:
            - Market exists and is OPEN
            - now >= end_time
            
            Effects:
            - Sets status to RESOLVING
            """
            sp.cast(market_id, sp.nat)
            
            assert self.data.markets.contains(market_id), "MARKET_NOT_FOUND"
            
            market = self.data.markets[market_id]
            
            assert market.status == Status.OPEN, "MARKET_NOT_OPEN"
            assert sp.now >= market.end_time, "MARKET_NOT_ENDED"
            
            market.status = Status.RESOLVING
            self.data.markets[market_id] = market
        
        # ====================================================================
        # Entrypoint: receive_outcome (Oracle Callback)
        # ====================================================================
        @sp.entrypoint
        def receive_outcome(self, market_id, result):
            """
            Receive outcome from the oracle contract.
            
            Preconditions:
            - sp.sender == oracle
            - Market is in RESOLVING status
            
            Effects:
            - Sets market result
            - Transitions to RESOLVED
            - Sends fees to PreventionFund
            """
            sp.cast(market_id, sp.nat)
            sp.cast(result, Side)
            
            # Only oracle can call this
            assert sp.sender == self.data.oracle, "NOT_ORACLE"
            
            assert self.data.markets.contains(market_id), "MARKET_NOT_FOUND"
            
            market = self.data.markets[market_id]
            
            assert market.status == Status.RESOLVING, "NOT_RESOLVING"
            
            # Set result and status
            market.result = sp.Some(result)
            market.status = Status.RESOLVED
            self.data.markets[market_id] = market
            
            # Calculate and send fees to fund
            total_pool = market.pool_over + market.pool_under
            
            # fee = total * fee_bps / 10000
            # Using sp.split_tokens for safe mutez arithmetic
            fee = sp.split_tokens(total_pool, self.data.fee_bps, 10000)
            
            # Check winning pool
            winning_pool = market.pool_over if result == Side.OVER else market.pool_under
            
            # If no winners, send entire distributable to fund
            if winning_pool == sp.mutez(0):
                # Everything goes to fund (fee already calculated, but send all)
                sp.send(self.data.fund, total_pool)
            else:
                # Send only fee to fund
                if fee > sp.mutez(0):
                    sp.send(self.data.fund, fee)
        
        # ====================================================================
        # Entrypoint: claim
        # ====================================================================
        @sp.entrypoint
        def claim(self, market_id):
            """
            Claim winnings from a resolved market.
            
            Preconditions:
            - Market is RESOLVED
            - User has not already claimed
            - User has winning bets
            
            Effects:
            - Marks user as claimed
            - Transfers proportional payout
            
            Payout calculation:
            - total = pool_over + pool_under
            - fee = total * fee_bps / 10000
            - distributable = total - fee
            - winning_pool = pool_{result}
            - user_stake = bets[(market_id, sender, result)]
            - payout = distributable * user_stake / winning_pool
            """
            sp.cast(market_id, sp.nat)
            
            assert self.data.markets.contains(market_id), "MARKET_NOT_FOUND"
            
            market = self.data.markets[market_id]
            
            assert market.status == Status.RESOLVED, "NOT_RESOLVED"
            
            # Check not already claimed
            claim_key = (market_id, sp.sender)
            already_claimed = self.data.claimed.get(claim_key, default=False)
            assert not already_claimed, "ALREADY_CLAIMED"
            
            # Get result
            result = market.result.unwrap_some(error="NO_RESULT")
            
            # Get user stake on winning side
            bet_key = (market_id, sp.sender, result)
            user_stake = self.data.bets.get(bet_key, default=sp.mutez(0))
            
            assert user_stake > sp.mutez(0), "NO_WINNING_BET"
            
            # Calculate payout
            total_pool = market.pool_over + market.pool_under
            fee = sp.split_tokens(total_pool, self.data.fee_bps, 10000)
            distributable = total_pool - fee
            
            winning_pool = market.pool_over if result == Side.OVER else market.pool_under
            
            # payout = distributable * user_stake / winning_pool
            # Use sp.split_tokens for safe arithmetic
            payout = sp.split_tokens(
                distributable,
                sp.fst(sp.ediv(user_stake, sp.mutez(1)).unwrap_some()),
                sp.fst(sp.ediv(winning_pool, sp.mutez(1)).unwrap_some())
            )
            
            # Mark as claimed
            self.data.claimed[claim_key] = True
            
            # Transfer payout
            sp.send(sp.sender, payout)
        
        # ====================================================================
        # Views
        # ====================================================================
        @sp.onchain_view
        def get_market(self, market_id):
            """Get market details by ID."""
            sp.cast(market_id, sp.nat)
            return self.data.markets.get(market_id, error="MARKET_NOT_FOUND")
        
        @sp.onchain_view
        def get_user_bet(self, params):
            """Get user's bet on a specific market and side."""
            market_id = sp.fst(params)
            user = sp.fst(sp.snd(params))
            side = sp.snd(sp.snd(params))
            bet_key = (market_id, user, side)
            return self.data.bets.get(bet_key, default=sp.mutez(0))
        
        @sp.onchain_view
        def has_claimed(self, params):
            """Check if user has claimed for a market."""
            market_id = sp.fst(params)
            user = sp.snd(params)
            claim_key = (market_id, user)
            return self.data.claimed.get(claim_key, default=False)


# ============================================================================
# Compilation target for SmartPy CLI
# ============================================================================
if "main" in __name__:
    @sp.add_test()
    def test():
        scenario = sp.test_scenario("CrowdShieldMarket Compilation", main)
        
        # Test addresses
        admin = sp.test_account("admin").address
        oracle = sp.test_account("oracle").address
        fund = sp.test_account("fund").address
        
        # Deploy contract
        contract = main.CrowdShieldMarket(
            admin=admin,
            oracle=oracle,
            fund=fund,
            fee_bps=sp.nat(500)  # 5%
        )
        scenario += contract
