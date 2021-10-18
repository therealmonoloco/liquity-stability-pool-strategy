import pytest

from brownie import chain, reverts, Wei


def test_withdraw_wrapper(
    strategy, vault, token, lusd_whale, gov, strategist, management, guardian, user
):
    amount = 100 * (10 ** token.decimals())

    # deposit to the vault
    token.approve(vault.address, amount, {"from": lusd_whale})
    vault.deposit(amount, {"from": lusd_whale})
    assert token.balanceOf(vault.address) == amount

    # harvest and make sure all funds are in the stability pool
    chain.sleep(1)
    strategy.harvest()
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == 0

    strategy.withdrawLUSD(1, {"from": gov})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == 1

    strategy.withdrawLUSD(2, {"from": management})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == 3

    strategy.withdrawLUSD(3, {"from": strategist})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == 6

    strategy.withdrawLUSD(4, {"from": guardian})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == 10

    # non white-listed roles in onlyEmergencyAuthorized should revert
    with reverts("!authorized"):
        strategy.withdrawLUSD(5, {"from": user})

    # a larger withdraw than the LUSD balance should return remaining amount
    strategy.withdrawLUSD(10000000 * (10 ** token.decimals()), {"from": gov})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == amount

    # a withdrawal with a 0 LUSD deposit should revert
    with reverts("StabilityPool: User must have a non-zero deposit"):
        strategy.withdrawLUSD(1, {"from": gov})


def test_deposit_wrapper(
    strategy, token, lusd_whale, gov, strategist, management, guardian, user
):
    # send some LUSD to the strategy
    amount = 100 * (10 ** token.decimals())
    token.transfer(strategy, amount, {"from": lusd_whale})

    strategy.depositLUSD(1, {"from": gov})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == amount - 1

    strategy.depositLUSD(2, {"from": management})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == amount - 3

    strategy.depositLUSD(3, {"from": strategist})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == amount - 6

    strategy.depositLUSD(4, {"from": guardian})
    assert strategy.totalLUSDBalance() == amount
    assert token.balanceOf(strategy) == amount - 10

    # non white-listed roles in onlyEmergencyAuthorized should revert
    with reverts("!authorized"):
        strategy.depositLUSD(5, {"from": user})

    # a larger deposit than the LUSD balance should revert
    with reverts():
        strategy.depositLUSD(1000 * (10 ** token.decimals()), {"from": gov})
