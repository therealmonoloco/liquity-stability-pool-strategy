from brownie import ZERO_ADDRESS
import pytest


def test_vault_shutdown_can_withdraw(chain, token, vault, strategy, user, amount):
    ## Deposit in Vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    if token.balanceOf(user) > 0:
        token.transfer(ZERO_ADDRESS, token.balanceOf(user), {"from": user})

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    chain.sleep(3600 * 7)
    chain.mine(1)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-2) == amount

    ## Set Emergency
    vault.setEmergencyShutdown(True)

    ## Withdraw (does it work, do you get what you expect) - accept 2% loss in conversion
    vault.withdraw(vault.balanceOf(user), user, 200, {"from": user})

    assert pytest.approx(token.balanceOf(user), rel=1e-2) == amount


def test_basic_shutdown(chain, token, vault, strategy, user, strategist, amount):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    chain.mine(100)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-2) == amount

    ## Earn interest
    chain.sleep(3600 * 24 * 1)  ## Sleep 1 day
    chain.mine(1)

    # Harvest 2: Realize profit
    chain.sleep(1)
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    ## Set emergency
    strategy.setEmergencyExit({"from": strategist})
    strategy.setDoHealthCheck(False, {"from": vault.management()})

    chain.sleep(1)
    strategy.harvest()  ## Remove funds from strategy

    assert vault.strategies(strategy).dict()["debtRatio"] == 0
    assert vault.strategies(strategy).dict()["totalDebt"] == 0
    assert token.balanceOf(strategy) == 0
    assert (
        pytest.approx(token.balanceOf(vault), rel=1e-3) == amount
    )  ## The vault has all funds
