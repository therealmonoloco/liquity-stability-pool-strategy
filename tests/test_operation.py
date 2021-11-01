import pytest

from brownie import chain, reverts, Wei


def test_operation(chain, token, vault, strategy, user, amount, RELATIVE_APPROX):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # harvest
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # tend()
    strategy.tend()

    # withdrawal
    vault.withdraw({"from": user})
    assert (
        pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
    )


def test_emergency_exit(chain, token, vault, strategy, user, amount, RELATIVE_APPROX):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # set emergency and exit
    strategy.setEmergencyExit()
    chain.sleep(1)
    strategy.harvest()
    assert strategy.estimatedTotalAssets() < amount


def test_profitable_harvest(
    chain, token, vault, strategy, user, amount, lqty, lqty_whale, RELATIVE_APPROX
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # Simulate profit
    before_pps = vault.pricePerShare()
    lqty.transfer(strategy, 20 * (10 ** lqty.decimals()), {"from": lqty_whale})

    # Harvest 2: Realize profit
    chain.sleep(1)
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault

    assert strategy.estimatedTotalAssets() + profit > amount
    assert vault.pricePerShare() > before_pps
    assert vault.totalAssets() > amount


def test_profitable_harvest_with_full_withdrawal(
    chain, token, vault, strategy, user, amount, lqty, lqty_whale, RELATIVE_APPROX
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # Simulate profit
    before_pps = vault.pricePerShare()
    lqty.transfer(strategy, 20 * (10 ** lqty.decimals()), {"from": lqty_whale})

    # Harvest 2: Realize profit
    chain.sleep(1)
    vault.updateStrategyDebtRatio(strategy, 0, {"from": vault.governance()})

    # Since there might be a loss
    strategy.setDoHealthCheck(False, {"from": vault.governance()})
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    assert vault.strategies(strategy).dict()["totalDebt"] == 0
    assert vault.strategies(strategy).dict()["totalGain"] > 0


def test_change_debt(chain, gov, token, vault, strategy, user, amount, RELATIVE_APPROX):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    half = int(amount / 2)

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half


def test_sweep(gov, vault, strategy, token, user, amount):
    # Strategy want token doesn't work
    token.transfer(strategy, amount, {"from": user})
    assert token.address == strategy.want()
    assert token.balanceOf(strategy) > 0
    with reverts("!want"):
        strategy.sweep(token, {"from": gov})

    # Vault share token doesn't work
    with reverts("!shares"):
        strategy.sweep(vault.address, {"from": gov})


def test_triggers(chain, gov, vault, strategy, token, amount, user):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()

    strategy.harvestTrigger(0)
    strategy.tendTrigger(0)


def test_loss_in_lusd_due_to_eth_price_declining_faster(
    chain,
    token,
    vault,
    strategy,
    accounts,
    lusd_whale,
    lqty,
    lqty_whale,
    weth,
    gov,
    RELATIVE_APPROX,
):
    amount = 50_000 * (10 ** token.decimals())

    # Deposit to the vault
    token.approve(vault.address, amount, {"from": lusd_whale})
    vault.deposit(amount, {"from": lusd_whale})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # Simulate loss. We are going to send 1 eth and 10 lqty to the strategy but
    # perform an external withdraw of 20000 LUSD
    before_pps = vault.pricePerShare()
    accounts.at(weth, force=True).transfer(strategy, Wei("1 ether"))
    lqty.transfer(strategy, 10 * (10 ** lqty.decimals()), {"from": lqty_whale})
    strategy.withdrawLUSD(
        20_000 * (10 ** token.decimals()), {"from": strategy.strategist()}
    )

    # Send LUSD away so it is not in the strategy's balance
    token.transfer(lusd_whale, token.balanceOf(strategy), {"from": strategy})

    # Turn off healthcheck for this one as the loss is going to be big
    strategy.setDoHealthCheck(False, {"from": gov})

    # Harvest 2: Realize loss
    chain.sleep(1)
    strategy.harvest()

    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    assert strategy.estimatedTotalAssets() < amount
    assert vault.pricePerShare() < before_pps
    assert vault.totalAssets() < amount
    assert vault.strategies(strategy).dict()["totalLoss"] > 0
    assert vault.strategies(strategy).dict()["totalGain"] == 0


def test_loss_in_lusd_but_ends_in_profit_because_lqty_rewards_are_higher(
    chain,
    token,
    vault,
    strategy,
    accounts,
    lusd_whale,
    lqty,
    lqty_whale,
    weth,
    gov,
    RELATIVE_APPROX,
):
    amount = 50_000 * (10 ** token.decimals())

    # Deposit to the vault
    token.approve(vault.address, amount, {"from": lusd_whale})
    vault.deposit(amount, {"from": lusd_whale})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # Simulate ETH price went further down than the 10% premium we got
    # We are going to send 1 eth and 1500 lqty to the strategy but
    # perform an external withdraw of 10000 LUSD
    # LQTY should be worth more than LUSD loss, ending in LUSD profit after swap
    before_pps = vault.pricePerShare()
    accounts.at(weth, force=True).transfer(strategy, Wei("1 ether"))
    lqty.transfer(strategy, 1500 * (10 ** lqty.decimals()), {"from": lqty_whale})
    strategy.withdrawLUSD(
        10_000 * (10 ** token.decimals()), {"from": strategy.strategist()}
    )

    # Send LUSD away so it is not in the strategy's balance
    token.transfer(lusd_whale, token.balanceOf(strategy), {"from": strategy})

    # Turn off healthcheck for this one
    strategy.setDoHealthCheck(False, {"from": gov})

    # Harvest 2: Loss in LUSD should be turned into profit by selling LQTY
    chain.sleep(1)
    strategy.harvest()

    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    assert strategy.estimatedTotalAssets() == amount
    assert vault.pricePerShare() > before_pps
    assert vault.totalAssets() > amount
    assert vault.strategies(strategy).dict()["totalLoss"] == 0
    assert vault.strategies(strategy).dict()["totalGain"] > 0
