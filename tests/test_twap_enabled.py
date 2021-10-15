from brownie import reverts


def test_twap_setter_acl(strategy, gov, strategist, management, keeper, guardian, user):
    # Check that default is set to True
    assert strategy.twapEnabled() == True
    
    strategy.setTwapEnabled(False, {"from": gov})
    assert strategy.twapEnabled() == False

    strategy.setTwapEnabled(True, {"from": management})
    assert strategy.twapEnabled() == True

    strategy.setTwapEnabled(False, {"from": strategist})
    assert strategy.twapEnabled() == False

    strategy.setTwapEnabled(True, {"from": guardian})
    assert strategy.twapEnabled() == True

    with reverts("!authorized"):
        strategy.setTwapEnabled(False, {"from": keeper})

    with reverts("!authorized"):
        strategy.setTwapEnabled(False, {"from": user})


def test_twap_enabled_fetches_price(strategy, lqty, lqty_whale, strategist):
    assert strategy.estimatedTotalAssets() == 0

    # send some lqty rewards for profit
    lqty.transfer(strategy, 20 * (10 ** lqty.decimals()), {"from": lqty_whale})

    strategy.setTwapEnabled(True, {"from": strategist})
    assert strategy.estimatedTotalAssets() > 0


def test_twap_disabled_does_not_fetch_price(strategy, lqty, lqty_whale, strategist):
    assert strategy.estimatedTotalAssets() == 0

    # send some lqty rewards for profit
    lqty.transfer(strategy, 20 * (10 ** lqty.decimals()), {"from": lqty_whale})

    strategy.setTwapEnabled(False, {"from": strategist})
    assert strategy.estimatedTotalAssets() == 0
