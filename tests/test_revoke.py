import pytest

from brownie import chain, Wei


def test_revoke_strategy_from_vault(
    chain, token, vault, strategy, amount, user, gov, RELATIVE_APPROX
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    vault.revokeStrategy(strategy.address, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(token.balanceOf(vault.address), rel=RELATIVE_APPROX) == amount


def test_revoke_strategy_from_strategy(
    chain, token, vault, strategy, amount, gov, user, RELATIVE_APPROX
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    strategy.setEmergencyExit()
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(token.balanceOf(vault.address), rel=RELATIVE_APPROX) == amount


def test_revoke_with_lqty_profit(
    token, vault, strategy, lusd_whale, gov, lqty, lqty_whale
):
    token.approve(vault, 2 ** 256 - 1, {"from": lusd_whale})
    vault.deposit(200_000 * (10 ** token.decimals()), {"from": lusd_whale})
    chain.sleep(1)
    strategy.harvest()

    # Send some lqty rewards to strategy
    lqty.transfer(strategy, 100 * (10 ** lqty.decimals()), {"from": lqty_whale})

    vault.revokeStrategy(strategy)
    chain.sleep(1)
    strategy.harvest()

    assert vault.strategies(strategy).dict()["totalGain"] > 0
    assert vault.strategies(strategy).dict()["debtRatio"] == 0
    assert vault.strategies(strategy).dict()["totalDebt"] == 0


def test_revoke_with_eth_profit(
    token, vault, strategy, lusd_whale, weth, gov, accounts
):
    token.approve(vault, 2 ** 256 - 1, {"from": lusd_whale})
    vault.deposit(700_000 * (10 ** token.decimals()), {"from": lusd_whale})
    chain.sleep(1)
    strategy.harvest()

    # Send some ETH from liquidations to strategy
    accounts.at(weth, force=True).transfer(strategy, Wei("1 ether"))

    vault.revokeStrategy(strategy)
    chain.sleep(1)
    strategy.harvest()

    assert vault.strategies(strategy).dict()["totalGain"] > 0
    assert vault.strategies(strategy).dict()["debtRatio"] == 0
    assert vault.strategies(strategy).dict()["totalDebt"] == 0
