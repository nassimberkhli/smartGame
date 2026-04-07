import smartpy as sp

from contracts.contract import bet_contract


@sp.add_test()
def test():
    scenario = sp.test_scenario()
    contract = bet_contract.BinaryAutomatonBet(
        3600,
        3600,
        10_000,
        10_000,
        128,
        128,
    )
    scenario += contract
