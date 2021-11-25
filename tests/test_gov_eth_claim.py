from brownie import reverts, Wei


def test_wrap_eth_acl(strategy, gov, strategist, management, guardian, user):
    with reverts("!authorized"):
        strategy.wrapETH({"from": management})

    with reverts("!authorized"):
        strategy.wrapETH({"from": strategist})

    with reverts("!authorized"):
        strategy.wrapETH({"from": guardian})

    with reverts("!authorized"):
        strategy.wrapETH({"from": user})

    strategy.wrapETH({"from": gov})


def test_wrap_eth(
    strategy, gov, strategist, management, guardian, user, accounts, weth
):
    accounts.at(weth, force=True).transfer(strategy, Wei("10 ether"))
    assert strategy.balance() == Wei("10 ether")
    assert weth.balanceOf(strategy) == 0

    strategy.wrapETH({"from": gov})
    assert strategy.balance() == 0
    assert weth.balanceOf(strategy) == Wei("10 ether")


def test_swallow_eth_acl(strategy, gov, strategist, management, guardian, user):
    strategy.swallowETH({"from": gov})

    with reverts("!authorized"):
        strategy.swallowETH({"from": management})

    with reverts("!authorized"):
        strategy.swallowETH({"from": strategist})

    with reverts("!authorized"):
        strategy.swallowETH({"from": guardian})

    with reverts("!authorized"):
        strategy.swallowETH({"from": user})


def test_swallow_eth(strategy, accounts, gov, weth):
    accounts.at(weth, force=True).transfer(strategy, Wei("100 ether"))

    assert strategy.balance() == Wei("100 ether")

    prev_balance = gov.balance()
    strategy.swallowETH({"from": gov})

    assert strategy.balance() == 0
    assert gov.balance() == prev_balance + Wei("100 ether")
