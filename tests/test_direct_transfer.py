import pytest

from brownie import chain, Wei


def test_direct_transfer_increments_estimated_total_assets(strategy, token, lusd_whale):
    initial = strategy.estimatedTotalAssets()
    amount = 100 * (10 ** token.decimals())
    token.transfer(strategy, amount, {"from": lusd_whale})
    assert strategy.estimatedTotalAssets() == initial + amount


def test_direct_transfer_increments_profits(
    vault, strategy, token, lusd_whale, RELATIVE_APPROX
):
    initialProfit = vault.strategies(strategy).dict()["totalGain"]
    assert initialProfit == 0

    token.approve(vault.address, 2 ** 256 - 1, {"from": lusd_whale})
    vault.deposit(1000 * (10 ** token.decimals()), {"from": lusd_whale})
    chain.sleep(1)
    strategy.harvest()

    amount = 50 * (10 ** token.decimals())
    token.transfer(strategy, amount, {"from": lusd_whale})

    chain.sleep(1)
    strategy.harvest()
    assert (
        pytest.approx(
            vault.strategies(strategy).dict()["totalGain"] / token.decimals(),
            rel=RELATIVE_APPROX,
        )
        == (initialProfit + amount) / token.decimals()
    )


def test_deposit_should_not_increment_profits(vault, strategy, token, lusd_whale):
    initialProfit = vault.strategies(strategy).dict()["totalGain"]
    assert initialProfit == 0

    token.approve(vault, 2 ** 256 - 1, {"from": lusd_whale})
    vault.deposit(1000 * (10 ** token.decimals()), {"from": lusd_whale})

    chain.sleep(1)
    strategy.harvest()

    assert vault.strategies(strategy).dict()["totalGain"] == initialProfit


def test_direct_transfer_with_actual_lqty_profits(
    vault, strategy, token, lusd_whale, lqty, lqty_whale
):
    initialProfit = vault.strategies(strategy).dict()["totalGain"]
    assert initialProfit == 0

    token.approve(vault, 2 ** 256 - 1, {"from": lusd_whale})
    vault.deposit(10_000 * (10 ** token.decimals()), {"from": lusd_whale})

    chain.sleep(1)
    strategy.harvest()

    # send some lqty rewards for profit
    lqty.transfer(strategy, 20 * (10 ** lqty.decimals()), {"from": lqty_whale})

    # sleep for a day
    chain.sleep(24 * 3600)
    chain.mine(1)

    # receive a direct transfer
    airdropAmount = 10 * (10 ** token.decimals())
    token.transfer(strategy, airdropAmount, {"from": lusd_whale})

    # sleep for another day
    chain.sleep(24 * 3600)
    chain.mine(1)

    strategy.harvest()
    assert (
        vault.strategies(strategy).dict()["totalGain"] > initialProfit + airdropAmount
    )


def test_direct_transfer_with_actual_eth_profits(
    vault, strategy, accounts, token, lusd_whale, weth
):
    initialProfit = vault.strategies(strategy).dict()["totalGain"]
    assert initialProfit == 0

    token.approve(vault, 2 ** 256 - 1, {"from": lusd_whale})
    vault.deposit(10_000 * (10 ** token.decimals()), {"from": lusd_whale})

    chain.sleep(1)
    strategy.harvest()

    # Send some ETH to strategy
    accounts.at(weth, force=True).transfer(strategy, Wei("1 ether"))

    # sleep for a day
    chain.sleep(24 * 3600)
    chain.mine(1)

    # receive a direct transfer
    airdropAmount = 10 * (10 ** token.decimals())
    token.transfer(strategy, airdropAmount, {"from": lusd_whale})

    # sleep for another day
    chain.sleep(24 * 3600)
    chain.mine(1)

    strategy.harvest()
    assert (
        vault.strategies(strategy).dict()["totalGain"] > initialProfit + airdropAmount
    )
