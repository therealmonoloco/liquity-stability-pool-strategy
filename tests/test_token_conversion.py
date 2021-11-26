from brownie import reverts, Wei


def test_set_min_expected_swap_percentage_acl(
    strategy, gov, strategist, management, keeper, guardian, user
):
    strategy.setMinExpectedSwapPercentage(1, {"from": gov})
    assert strategy.minExpectedSwapPercentage() == 1

    strategy.setMinExpectedSwapPercentage(2, {"from": strategist})
    assert strategy.minExpectedSwapPercentage() == 2

    strategy.setMinExpectedSwapPercentage(3, {"from": management})
    assert strategy.minExpectedSwapPercentage() == 3

    strategy.setMinExpectedSwapPercentage(4, {"from": guardian})
    assert strategy.minExpectedSwapPercentage() == 4

    with reverts():
        strategy.setMinExpectedSwapPercentage(5, {"from": keeper})

    with reverts():
        strategy.setMinExpectedSwapPercentage(6, {"from": user})


def test_set_swap_fees_acl(
    strategy, gov, strategist, management, keeper, guardian, user
):
    # Check default swap fees
    assert strategy.lqtyToEthFee() == 3000  # 0.3% pool
    assert strategy.ethToDaiFee() == 500  # 0.05% pool
    assert strategy.daiToLusdFee() == 500  # 0.05% pool

    strategy.setSwapFees(100, 200, 300, {"from": gov})
    assert strategy.lqtyToEthFee() == 100
    assert strategy.ethToDaiFee() == 200
    assert strategy.daiToLusdFee() == 300

    strategy.setSwapFees(400, 500, 600, {"from": strategist})
    assert strategy.lqtyToEthFee() == 400
    assert strategy.ethToDaiFee() == 500
    assert strategy.daiToLusdFee() == 600

    strategy.setSwapFees(700, 800, 900, {"from": guardian})
    assert strategy.lqtyToEthFee() == 700
    assert strategy.ethToDaiFee() == 800
    assert strategy.daiToLusdFee() == 900

    strategy.setSwapFees(1000, 1100, 1200, {"from": management})
    assert strategy.lqtyToEthFee() == 1000
    assert strategy.ethToDaiFee() == 1100
    assert strategy.daiToLusdFee() == 1200

    with reverts("!authorized"):
        strategy.setSwapFees(1, 2, 3, {"from": keeper})

    with reverts("!authorized"):
        strategy.setSwapFees(4, 5, 6, {"from": user})


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


def test_lqty_to_dai_with_invalid_lqty_eth_fee_reverts(
    test_strategy, dai, lqty, lqty_whale
):
    test_strategy.setSwapFees(
        123, test_strategy.ethToDaiFee(), test_strategy.daiToLusdFee()
    )
    lqty.transfer(test_strategy, 1_000 * (10 ** lqty.decimals()), {"from": lqty_whale})
    with reverts():
        test_strategy.sellLQTYforDAI()


def test_lqty_to_dai_with_invalid_eth_dai_fee_reverts(
    test_strategy, dai, lqty, lqty_whale
):
    test_strategy.setSwapFees(
        test_strategy.lqtyToEthFee(), 123123, test_strategy.daiToLusdFee()
    )
    lqty.transfer(test_strategy, 1_000 * (10 ** lqty.decimals()), {"from": lqty_whale})
    with reverts():
        test_strategy.sellLQTYforDAI()


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


def test_eth_to_dai_with_invalid_fee_reverts(test_strategy, accounts, weth):
    test_strategy.setSwapFees(
        test_strategy.lqtyToEthFee(), 5511, test_strategy.daiToLusdFee()
    )

    accounts.at(weth, force=True).transfer(test_strategy, Wei("100 ether"))
    with reverts():
        test_strategy.sellETHforDAI()


def test_eth_to_dai_with_no_slippage_reverts(test_strategy, accounts, weth, dai):
    accounts.at(weth, force=True).transfer(test_strategy, Wei("100 ether"))

    # Set min expected swap to 102% of current chainlink price
    test_strategy.setMinExpectedSwapPercentage(10200)

    with reverts():
        test_strategy.sellETHforDAI()


def test_eth_to_dai_swap(test_strategy, accounts, weth, dai):
    assert test_strategy.totalETHBalance() == 0
    assert test_strategy.totalLQTYBalance() == 0
    assert dai.balanceOf(test_strategy) == 0

    accounts.at(weth, force=True).transfer(test_strategy, Wei("100 ether"))
    test_strategy.sellETHforDAI()

    print(f"Swapped 100 ETH for {dai.balanceOf(test_strategy)/1e18:.2f} DAI")

    assert test_strategy.totalETHBalance() == 0
    assert dai.balanceOf(test_strategy) > 0


def test_dai_to_lusd_with_invalid_fee_reverts(test_strategy, dai, dai_whale, lusd):
    test_strategy.setConvertDAItoLUSDonCurve(
        False, {"from": test_strategy.strategist()}
    )

    test_strategy.setSwapFees(
        test_strategy.lqtyToEthFee(), test_strategy.ethToDaiFee(), 90000
    )
    dai.transfer(test_strategy, 1_000 * (10 ** dai.decimals()), {"from": dai_whale})

    with reverts():
        test_strategy.sellDAIforLUSD()


def test_dai_to_lusd_swap_on_uniswap_with_no_slippage_reverts(
    test_strategy, dai, dai_whale, lusd
):
    test_strategy.setConvertDAItoLUSDonCurve(
        False, {"from": test_strategy.strategist()}
    )

    # Set min expected swap to 105% of balance
    test_strategy.setMinExpectedSwapPercentage(10500)

    dai.transfer(test_strategy, 1_000 * (10 ** dai.decimals()), {"from": dai_whale})

    with reverts():
        test_strategy.sellDAIforLUSD()


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


def test_dai_to_lusd_swap_on_curve_with_no_slippage_reverts(
    test_strategy, dai, dai_whale, lusd
):
    test_strategy.setConvertDAItoLUSDonCurve(True, {"from": test_strategy.strategist()})

    # Set min expected swap to 105% of balance
    test_strategy.setMinExpectedSwapPercentage(10500)

    dai.transfer(test_strategy, 1_000 * (10 ** dai.decimals()), {"from": dai_whale})

    with reverts():
        test_strategy.sellDAIforLUSD()


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
