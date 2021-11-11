import pytest


def test_migration(
    chain, token, vault, strategy, amount, Strategy, strategist, gov, user
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-2) == amount

    # migrate to a new strategy
    new_strategy = strategist.deploy(Strategy, vault)
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    assert pytest.approx(new_strategy.estimatedTotalAssets(), rel=1e-2) == amount
