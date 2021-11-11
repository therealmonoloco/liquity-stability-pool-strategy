from brownie import chain, reverts


def test_profit_under_max_ratio_does_not_revert(
    vault, strategy, token, dai_whale, healthCheck
):
    profitLimit = healthCheck.profitLimitRatio()
    maxBPS = 10_000

    # Send some funds to the strategy
    token.approve(vault.address, 2 ** 256 - 1, {"from": dai_whale})
    vault.deposit(1000 * (10 ** token.decimals()), {"from": dai_whale})
    chain.sleep(1)
    strategy.harvest()

    token.transfer(
        strategy,
        vault.strategies(strategy).dict()["totalDebt"] * ((profitLimit * 0.9) / maxBPS),
        {"from": dai_whale},
    )

    chain.sleep(1)
    strategy.harvest()

    # If we reach the assert the harvest did not revert
    assert True


def test_high_loss_causes_healthcheck_revert(vault, strategy, token, dai_whale, lusd):
    # Send some funds to the strategy
    token.approve(vault.address, 2 ** 256 - 1, {"from": dai_whale})
    vault.deposit(50_000 * (10 ** token.decimals()), {"from": dai_whale})
    chain.sleep(1)
    strategy.harvest()

    # Send LUSD away so it is not in the strategy's balance
    strategy.withdrawLUSD(
        20_000 * (10 ** token.decimals()), {"from": strategy.strategist()}
    )
    lusd.transfer(dai_whale, lusd.balanceOf(strategy), {"from": strategy})

    chain.sleep(1)
    with reverts("!healthcheck"):
        strategy.harvest()


def test_loss_under_max_ratio_does_not_revert(
    vault, strategy, token, dai_whale, healthCheck
):
    lossRatio = healthCheck.lossLimitRatio()
    maxBPS = 10_000

    # Send some funds to the strategy
    token.approve(vault.address, 2 ** 256 - 1, {"from": dai_whale})
    vault.deposit(1 * (10 ** token.decimals()), {"from": dai_whale})
    chain.sleep(1)
    strategy.harvest()

    # Send LUSD away so it is not in the strategy's balance
    strategy.withdrawLUSD(
        vault.strategies(strategy).dict()["totalDebt"] * ((lossRatio * 0.9) / maxBPS),
        {"from": strategy.strategist()},
    )
    token.transfer(dai_whale, token.balanceOf(strategy), {"from": strategy})

    chain.sleep(1)
    strategy.harvest()

    # If we reach the assert the harvest did not revert
    assert True


def disabled_test_high_profit_causes_healthcheck_revert(
    vault, strategy, token, dai_whale, healthCheck
):
    profitLimit = healthCheck.profitLimitRatio()
    maxBPS = 10_000

    # Send some funds to the strategy
    token.approve(vault.address, 2 ** 256 - 1, {"from": dai_whale})
    vault.deposit(70_000 * (10 ** token.decimals()), {"from": dai_whale})
    chain.sleep(1)
    strategy.harvest()

    token.transfer(
        strategy,
        vault.strategies(strategy).dict()["totalDebt"] * ((profitLimit * 1.1) / maxBPS),
        {"from": dai_whale},
    )

    chain.sleep(1)
    with reverts("!healthcheck"):
        strategy.harvest()
