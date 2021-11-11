import pytest

from brownie import chain, Wei


def test_direct_token_transfer_increments_estimated_total_assets(
    strategy, token, dai_whale
):
    initial = strategy.estimatedTotalAssets()
    amount = 100 * (10 ** token.decimals())
    token.transfer(strategy, amount, {"from": dai_whale})
    assert strategy.estimatedTotalAssets() == initial + amount


def test_direct_lusd_transfer_increments_estimated_total_assets(
    strategy, lusd, lusd_whale
):
    initial = strategy.estimatedTotalAssets()
    amount = 100 * (10 ** lusd.decimals())
    lusd.transfer(strategy, amount, {"from": lusd_whale})
    assert strategy.estimatedTotalAssets() == initial + amount


def test_direct_transfer_increments_profits(vault, strategy, token, dai_whale):
    initialProfit = vault.strategies(strategy).dict()["totalGain"]
    assert initialProfit == 0

    token.approve(vault.address, 2 ** 256 - 1, {"from": dai_whale})
    vault.deposit(100_000 * (10 ** token.decimals()), {"from": dai_whale})
    chain.sleep(1)
    strategy.harvest()

    amount = 50 * (10 ** token.decimals())
    token.transfer(strategy, amount, {"from": dai_whale})

    chain.sleep(1)
    strategy.harvest()
    assert vault.strategies(strategy).dict()["totalGain"] >= (initialProfit + amount)


def test_deposit_should_not_increment_profits(vault, strategy, token, dai_whale):
    initialProfit = vault.strategies(strategy).dict()["totalGain"]
    assert initialProfit == 0

    token.approve(vault, 2 ** 256 - 1, {"from": dai_whale})
    vault.deposit(1000 * (10 ** token.decimals()), {"from": dai_whale})

    chain.sleep(1)
    strategy.harvest()

    assert vault.strategies(strategy).dict()["totalGain"] == initialProfit


def test_direct_transfer_with_actual_lqty_profits(
    vault, strategy, token, dai_whale, lqty, lqty_whale
):
    initialProfit = vault.strategies(strategy).dict()["totalGain"]
    assert initialProfit == 0

    token.approve(vault, 2 ** 256 - 1, {"from": dai_whale})
    vault.deposit(500_000 * (10 ** token.decimals()), {"from": dai_whale})

    chain.sleep(1)
    strategy.harvest()

    # send some lqty rewards for profit
    lqty.transfer(strategy, 20 * (10 ** lqty.decimals()), {"from": lqty_whale})

    # sleep for a day
    chain.sleep(24 * 3600)
    chain.mine(1)

    # receive a direct transfer
    airdropAmount = 10 * (10 ** token.decimals())
    token.transfer(strategy, airdropAmount, {"from": dai_whale})

    # sleep for another day
    chain.sleep(24 * 3600)
    chain.mine(1)

    strategy.harvest()
    assert (
        vault.strategies(strategy).dict()["totalGain"] > initialProfit + airdropAmount
    )


def test_direct_transfer_with_actual_eth_profits(
    vault, strategy, accounts, token, dai_whale, weth
):
    initialProfit = vault.strategies(strategy).dict()["totalGain"]
    assert initialProfit == 0

    token.approve(vault, 2 ** 256 - 1, {"from": dai_whale})
    vault.deposit(5_000_000 * (10 ** token.decimals()), {"from": dai_whale})

    chain.sleep(1)
    strategy.harvest()

    # Send some ETH to strategy
    accounts.at(weth, force=True).transfer(strategy, Wei("1 ether"))

    # sleep for a day
    chain.sleep(24 * 3600)
    chain.mine(1)

    # receive a direct transfer
    airdropAmount = 2 * (10 ** token.decimals())
    token.transfer(strategy, airdropAmount, {"from": dai_whale})

    # sleep for another day
    chain.sleep(24 * 3600)
    chain.mine(1)

    strategy.harvest()
    assert (
        vault.strategies(strategy).dict()["totalGain"] > initialProfit + airdropAmount
    )
