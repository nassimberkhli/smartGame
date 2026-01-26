import smartpy as sp

# ============================================================================
# Prevention Fund Contract
# ============================================================================
# Transparent fund for crowd safety prevention measures.
# Receives fees from market resolutions and allows admin-controlled spending
# with on-chain journaling.
# ============================================================================


@sp.module
def main():
    
    class Expense(sp.Record):
        amount: sp.mutez
        recipient: sp.address
        description: sp.string
        timestamp: sp.timestamp
    
    # ========================================================================
    # PreventionFund Contract
    # ========================================================================
    
    class PreventionFund(sp.Contract):
        """
        Transparent prevention fund for safety measures.
        
        Storage:
        - admin: Fund administrator
        - expenses: List of recorded expenses
        - total_received: Total tez received
        - total_spent: Total tez spent
        """
        
        def __init__(self, admin):
            self.data.admin = admin
            self.data.expenses = sp.cast([], sp.list[Expense])
            self.data.total_received = sp.mutez(0)
            self.data.total_spent = sp.mutez(0)
        
        # ====================================================================
        # Entrypoint: deposit
        # ====================================================================
        @sp.entrypoint
        def deposit(self):
            """
            Receive tez deposit (from market fees or direct donation).
            
            Effects:
            - Increases total_received
            - Contract balance increases
            """
            assert sp.amount > sp.mutez(0), "ZERO_AMOUNT"
            self.data.total_received += sp.amount
        
        # ====================================================================
        # Entrypoint: default (fallback)
        # ====================================================================
        @sp.entrypoint
        def default(self):
            """
            Default entrypoint to receive tez without explicit deposit call.
            """
            if sp.amount > sp.mutez(0):
                self.data.total_received += sp.amount
        
        # ====================================================================
        # Entrypoint: spend
        # ====================================================================
        @sp.entrypoint
        def spend(self, amount, recipient, description):
            """
            Spend from the fund for prevention measures.
            
            Preconditions:
            - Sender is admin
            - Sufficient balance
            
            Effects:
            - Records expense on-chain
            - Transfers tez to recipient
            - Updates total_spent
            """
            sp.cast(amount, sp.mutez)
            sp.cast(recipient, sp.address)
            sp.cast(description, sp.string)
            
            # Admin only
            assert sp.sender == self.data.admin, "NOT_ADMIN"
            
            # Check balance
            assert sp.balance >= amount, "INSUFFICIENT_BALANCE"
            
            # Record expense
            expense = sp.record(
                amount=amount,
                recipient=recipient,
                description=description,
                timestamp=sp.now
            )
            self.data.expenses.push(expense)
            
            # Update totals
            self.data.total_spent += amount
            
            # Transfer
            sp.send(recipient, amount)
        
        # ====================================================================
        # Admin: transfer_admin
        # ====================================================================
        @sp.entrypoint
        def transfer_admin(self, new_admin):
            """Transfer admin rights to new address."""
            assert sp.sender == self.data.admin, "NOT_ADMIN"
            self.data.admin = new_admin
        
        # ====================================================================
        # Views
        # ====================================================================
        @sp.onchain_view
        def get_balance(self):
            """Get current fund balance."""
            return sp.balance
        
        @sp.onchain_view
        def get_stats(self):
            """Get fund statistics."""
            return sp.record(
                balance=sp.balance,
                total_received=self.data.total_received,
                total_spent=self.data.total_spent,
                expense_count=sp.len(self.data.expenses)
            )
        
        @sp.onchain_view
        def get_expense(self, index):
            """Get expense by index (0 = most recent)."""
            sp.cast(index, sp.nat)
            expenses_list = self.data.expenses
            # Note: expenses are stored in reverse order (push adds to front)
            counter = sp.local("counter", sp.nat(0))
            result = sp.local("result", sp.cast(
                None,
                sp.option[Expense]
            ))
            for expense in expenses_list:
                if counter.value == index:
                    result.value = sp.Some(expense)
                counter.value += 1
            return result.value


# ============================================================================
# Compilation target
# ============================================================================
if "main" in __name__:
    @sp.add_test()
    def test():
        scenario = sp.test_scenario("PreventionFund Compilation", main)
        
        admin = sp.test_account("admin").address
        
        contract = main.PreventionFund(admin=admin)
        scenario += contract
