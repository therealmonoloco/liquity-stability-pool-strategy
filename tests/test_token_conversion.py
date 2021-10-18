from brownie import reverts, Wei


def test_use_curve_acl(strategy, gov, strategist, management, keeper, guardian, user):
    # Check that default is set to True
    assert strategy.convertDAItoLUSDonCurve() == True

    strategy.setConvertDAItoLUSDonCurve(False, {"from": gov})
    assert strategy.convertDAItoLUSDonCurve() == False

    strategy.setConvertDAItoLUSDonCurve(True, {"from": management})
    assert strategy.convertDAItoLUSDonCurve() == True

    strategy.setConvertDAItoLUSDonCurve(False, {"from": strategist})
    assert strategy.convertDAItoLUSDonCurve() == False

    strategy.setConvertDAItoLUSDonCurve(True, {"from": guardian})
    assert strategy.convertDAItoLUSDonCurve() == True

    with reverts("!authorized"):
        strategy.setConvertDAItoLUSDonCurve(True, {"from": keeper})

    with reverts("!authorized"):
        strategy.setConvertDAItoLUSDonCurve(True, {"from": user})


def test_lqty_to_dai_swap(test_strategy, dai, lqty, lqty_whale):
    assert test_strategy.totalETHBalance() == 0
    assert test_strategy.totalLQTYBalance() == 0
    assert dai.balanceOf(test_strategy) == 0

    lqty.transfer(test_strategy, 1_000 * (10 ** lqty.decimals()), {"from": lqty_whale})
    test_strategy.sellLQTYforDAI()

    print(f"Swapped 1000 LQTY for {dai.balanceOf(test_strategy)/1e18:.2f} DAI")

    assert test_strategy.totalETHBalance() == 0
    assert test_strategy.totalLQTYBalance() == 0
    assert dai.balanceOf(test_strategy) > 0


def test_eth_to_dai_swap(test_strategy, accounts, weth, dai):
    assert test_strategy.totalETHBalance() == 0
    assert test_strategy.totalLQTYBalance() == 0
    assert dai.balanceOf(test_strategy) == 0

    accounts.at(weth, force=True).transfer(test_strategy, Wei("100 ether"))
    test_strategy.sellETHforDAI()

    print(f"Swapped 100 ETH for {dai.balanceOf(test_strategy)/1e18:.2f} DAI")

    assert test_strategy.totalETHBalance() == 0
    assert dai.balanceOf(test_strategy) > 0


def test_dai_to_lusd_swap_on_uniswap(test_strategy, dai, dai_whale, lusd):
    test_strategy.setConvertDAItoLUSDonCurve(
        False, {"from": test_strategy.strategist()}
    )

    assert lusd.balanceOf(test_strategy) == 0
    assert dai.balanceOf(test_strategy) == 0

    dai.transfer(test_strategy, 1_000 * (10 ** dai.decimals()), {"from": dai_whale})
    test_strategy.sellDAIforLUSD()

    print(f"Swapped 1000 DAI for {lusd.balanceOf(test_strategy)/1e18:.2f} LUSD")

    assert lusd.balanceOf(test_strategy) > 0
    assert dai.balanceOf(test_strategy) == 0


def test_dai_to_lusd_swap_on_curve(test_strategy, dai, dai_whale, lusd):
    test_strategy.setConvertDAItoLUSDonCurve(True, {"from": test_strategy.strategist()})

    assert lusd.balanceOf(test_strategy) == 0
    assert dai.balanceOf(test_strategy) == 0

    dai.transfer(test_strategy, 1_000 * (10 ** dai.decimals()), {"from": dai_whale})
    test_strategy.sellDAIforLUSD()

    print(f"Swapped 1000 DAI for {lusd.balanceOf(test_strategy)/1e18:.2f} LUSD")

    assert lusd.balanceOf(test_strategy) > 0
    assert dai.balanceOf(test_strategy) == 0


def test_claim_rewards_ends_in_lusd_using_uniswap(
    test_strategy, accounts, lusd, dai, lqty, lqty_whale, weth
):
    test_strategy.setConvertDAItoLUSDonCurve(
        False, {"from": test_strategy.strategist()}
    )

    # Start without any funds
    assert test_strategy.totalETHBalance() == 0
    assert test_strategy.totalLQTYBalance() == 0
    assert test_strategy.totalLUSDBalance() == 0
    assert dai.balanceOf(test_strategy) == 0

    # We simulate a trigger in LQTY rewards and ETH from liquidations
    # that transfers 10 ETH and 1000 LQTY to the strategy
    accounts.at(weth, force=True).transfer(test_strategy, Wei("10 ether"))
    lqty.transfer(test_strategy, 1_000 * (10 ** lqty.decimals()), {"from": lqty_whale})

    test_strategy.claimRewards()

    print(
        f"Swapped 10 ETH and 1000 LQTY for {lusd.balanceOf(test_strategy)/1e18:.2f} LUSD"
    )

    assert dai.balanceOf(test_strategy) == 0
    assert test_strategy.totalLQTYBalance() == 0
    assert test_strategy.totalETHBalance() == 0
    assert lusd.balanceOf(test_strategy) > 0


def test_claim_rewards_ends_in_lusd_using_curve(
    test_strategy, accounts, lusd, dai, lqty, lqty_whale, weth
):
    test_strategy.setConvertDAItoLUSDonCurve(
        False, {"from": test_strategy.strategist()}
    )

    # Start without any funds
    assert test_strategy.totalETHBalance() == 0
    assert test_strategy.totalLQTYBalance() == 0
    assert test_strategy.totalLUSDBalance() == 0
    assert dai.balanceOf(test_strategy) == 0

    # We simulate a trigger in LQTY rewards and ETH from liquidations
    # that transfers 10 ETH and 1000 LQTY to the strategy
    accounts.at(weth, force=True).transfer(test_strategy, Wei("10 ether"))
    lqty.transfer(test_strategy, 1_000 * (10 ** lqty.decimals()), {"from": lqty_whale})

    test_strategy.claimRewards()

    print(
        f"Swapped 10 ETH and 1000 LQTY for {lusd.balanceOf(test_strategy)/1e18:.2f} LUSD"
    )

    assert dai.balanceOf(test_strategy) == 0
    assert test_strategy.totalLQTYBalance() == 0
    assert test_strategy.totalETHBalance() == 0
    assert lusd.balanceOf(test_strategy) > 0
