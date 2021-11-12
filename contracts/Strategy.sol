// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import {BaseStrategy} from "@yearnvaults/contracts/BaseStrategy.sol";
import "@openzeppelin/contracts/math/Math.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "../interfaces/curve/IStableSwapExchange.sol";
import "../interfaces/liquity/IPriceFeed.sol";
import "../interfaces/liquity/IStabilityPool.sol";
import "../interfaces/uniswap/ISwapRouter.sol";

contract Strategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    // LQTY rewards accrue to Stability Providers who deposit LUSD to the Stability Pool
    IERC20 internal constant LQTY =
        IERC20(0x6DEA81C8171D0bA574754EF6F8b412F2Ed88c54D);

    // LUSD will be the investment token to deposit
    IERC20 internal constant LUSD =
        IERC20(0x5f98805A4E8be255a32880FDeC7F6728C6568bA0);

    // Source of liquidity to repay debt from liquidated troves
    IStabilityPool internal constant stabilityPool =
        IStabilityPool(0x66017D22b0f8556afDd19FC67041899Eb65a21bb);

    // Chainlink ETH:USD with Tellor ETH:USD as fallback
    IPriceFeed internal constant priceFeed =
        IPriceFeed(0x4c517D4e2C851CA76d7eC94B805269Df0f2201De);

    // Uniswap v3 router to do LQTY->ETH
    ISwapRouter internal constant router =
        ISwapRouter(0xE592427A0AEce92De3Edee1F18E0157C05861564);

    // LUSD3CRV Curve Metapool
    IStableSwapExchange internal constant curvePool =
        IStableSwapExchange(0xEd279fDD11cA84bEef15AF5D39BB4d4bEE23F0cA);

    // Wrapped Ether - Used for swaps routing
    IERC20 internal constant WETH =
        IERC20(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);

    // DAI - Used for swaps routing
    IERC20 internal constant DAI =
        IERC20(0x6B175474E89094C44Da98b954EedeAC495271d0F);

    constructor(address _vault) public BaseStrategy(_vault) {
        // Set health check to health.ychad.eth
        healthCheck = 0xDDCea799fF1699e98EDF118e0629A974Df7DF012;
    }

    // Strategy should be able to receive ETH
    receive() external payable {}

    // ----------------- SETTERS & EXTERNAL CONFIGURATION -----------------

    // Allow governance to claim any outstanding ETH balance
    // This is done to provide additional flexibility since this is ETH and not WETH
    // so gov cannot sweep it
    function swallowETH() external onlyGovernance {
        (bool sent, ) = msg.sender.call{value: address(this).balance}("");
        require(sent); // dev: could not send ether to governance
    }

    // Wrapper around `provideToSP` to allow forcing a deposit externally
    // This could be useful to trigger LQTY / ETH transfers without harvesting.
    // `provideToSP` will revert if not enough funds are provided so no need
    // to have an additional check.
    function depositLUSD(uint256 _amount) external onlyEmergencyAuthorized {
        stabilityPool.provideToSP(_amount, address(0));
    }

    // Wrapper around `withdrawFromSP` to allow forcing a withdrawal externally.
    // This could be useful to trigger LQTY / ETH transfers without harvesting
    // or bypassing any scenario where strategy funds are locked (e.g: bad accounting).
    // `withdrawFromSP` will revert if there are no deposits. If _amount is larger
    // than the deposit it will return all remaining balance.
    function withdrawLUSD(uint256 _amount) external onlyEmergencyAuthorized {
        stabilityPool.withdrawFromSP(_amount);
    }

    // ----------------- BASE STRATEGY FUNCTIONS -----------------

    function name() external view override returns (string memory) {
        return "StrategyLiquityStabilityPoolLUSD";
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        // Assume 1 DAI = 1 LUSD = 1 USD for estimation purposes
        return
            balanceOfWant().add(totalLUSDBalance()).add(
                totalETHBalance().mul(priceFeed.lastGoodPrice()).div(1e18)
            );
    }

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        // How much do we owe to the DAI vault?
        uint256 totalDebt = vault.strategies(address(this)).totalDebt;

        // Claim LQTY/ETH and sell them for more DAI
        _claimRewards();

        // At this point all ETH and LQTY has been converted to DAI
        uint256 totalAssetsAfterClaim = balanceOfWant().add(totalLUSDBalance());

        // Assume 1 DAI = 1 LUSD - any loss due to peg will be accounted for next
        if (totalAssetsAfterClaim > totalDebt) {
            _profit = totalAssetsAfterClaim.sub(totalDebt);
            _loss = 0;
        } else {
            _profit = 0;
            _loss = totalDebt.sub(totalAssetsAfterClaim);
        }

        uint256 _amountFreed;
        uint256 _liquidationLoss;
        (_amountFreed, _liquidationLoss) = liquidatePosition(
            _debtOutstanding.add(_profit)
        );
        _debtPayment = Math.min(_debtOutstanding, _amountFreed);

        // Account for any additional loss in liquidatePosition
        if (_liquidationLoss > 0) {
            uint256 diff = Math.min(_liquidationLoss, _profit);
            _profit = _profit.sub(diff);
            _liquidationLoss = _liquidationLoss.sub(diff);
            _loss = _loss.add(_liquidationLoss);
        }
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        // Provide any leftover balance to the stability pool
        // Use zero address for frontend as we are interacting with the contracts directly
        uint256 wantBalance = balanceOfWant();

        if (wantBalance > _debtOutstanding) {
            _sellDAIforLUSD(wantBalance.sub(_debtOutstanding));
        }

        // Deposit any LUSD left
        if (LUSD.balanceOf(address(this)) > 0) {
            stabilityPool.provideToSP(
                LUSD.balanceOf(address(this)),
                address(0)
            );
        }
    }

    /**
        ***IMPORTANT***
        This method might perform token conversions (LUSD->DAI) and it is
        assumed to be called only from prepareReturn through flahshbots.
        Strategy will be placed at the end of yvDAI queue so no withdrawals
        take place.
     **/
    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 balance = balanceOfWant();

        // Check if we can handle it without withdrawing from stability pool
        if (balance >= _amountNeeded) {
            return (_amountNeeded, 0);
        }

        // Only need to free the amount of want not readily available
        // Assume we need an additional 5% to cover fees and slippage
        // Will get reinvested if is more than needed
        uint256 amountToWithdraw = _amountNeeded.sub(balance).mul(105).div(100);

        // Cannot withdraw more than what we have in deposit
        amountToWithdraw = Math.min(
            amountToWithdraw,
            stabilityPool.getCompoundedLUSDDeposit(address(this))
        );

        if (amountToWithdraw > 0) {
            stabilityPool.withdrawFromSP(amountToWithdraw);
        }

        _sellLUSDforDAI(amountToWithdraw);

        uint256 looseWant = balanceOfWant();
        if (_amountNeeded > looseWant) {
            _liquidatedAmount = looseWant;
            _loss = _amountNeeded.sub(looseWant);
        } else {
            _liquidatedAmount = _amountNeeded;
            _loss = 0;
        }
    }

    function liquidateAllPositions()
        internal
        override
        returns (uint256 _amountFreed)
    {
        (_amountFreed, ) = liquidatePosition(
            balanceOfWant().add(totalLUSDBalance())
        );
    }

    // This method will perform token conversions so should be called in a
    // stealth transaction (i.e: using flashbots)
    function prepareMigration(address _newStrategy) internal override {
        stabilityPool.withdrawFromSP(
            stabilityPool.getCompoundedLUSDDeposit(address(this))
        );

        _claimRewards();
        _sellLUSDforDAI(LUSD.balanceOf(address(this)));
    }

    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    function ethToWant(uint256 _amtInWei)
        public
        view
        virtual
        override
        returns (uint256)
    {
        return _amtInWei.mul(priceFeed.lastGoodPrice()).div(1e18);
    }

    // ----------------- PUBLIC BALANCES -----------------

    function balanceOfWant() public view returns (uint256) {
        return want.balanceOf(address(this));
    }

    function totalLUSDBalance() public view returns (uint256) {
        return
            LUSD.balanceOf(address(this)).add(
                stabilityPool.getCompoundedLUSDDeposit(address(this))
            );
    }

    function totalLQTYBalance() public view returns (uint256) {
        return
            LQTY.balanceOf(address(this)).add(
                stabilityPool.getDepositorLQTYGain(address(this))
            );
    }

    function totalETHBalance() public view returns (uint256) {
        return
            address(this).balance.add(
                stabilityPool.getDepositorETHGain(address(this))
            );
    }

    // ----------------- SUPPORT FUNCTIONS ----------

    function _checkAllowance(
        address _contract,
        IERC20 _token,
        uint256 _amount
    ) internal {
        if (_token.allowance(address(this), _contract) < _amount) {
            _token.safeApprove(_contract, 0);
            _token.safeApprove(_contract, type(uint256).max);
        }
    }

    function _claimRewards() internal {
        // Need to interact with SP so rewards are sent to the strategy
        if (stabilityPool.getCompoundedLUSDDeposit(address(this)) > 0) {
            stabilityPool.withdrawFromSP(0);
        }

        // Convert LQTY rewards to DAI
        if (LQTY.balanceOf(address(this)) > 0) {
            _sellLQTYforDAI();
        }

        // Convert ETH obtained from liquidations to DAI
        if (address(this).balance > 0) {
            _sellETHforDAI();
        }
    }

    // ----------------- TOKEN CONVERSIONS -----------------

    function _sellLQTYforDAI() internal {
        _checkAllowance(address(router), LQTY, LQTY.balanceOf(address(this)));

        bytes memory path =
            abi.encodePacked(
                address(LQTY), // LQTY-ETH 0.3%
                uint24(3000),
                address(WETH), // ETH-DAI 0.3%
                uint24(3000),
                address(DAI)
            );

        router.exactInput(
            ISwapRouter.ExactInputParams(
                path,
                address(this),
                now,
                LQTY.balanceOf(address(this)),
                0
            )
        );
    }

    function _sellETHforDAI() internal {
        ISwapRouter.ExactInputSingleParams memory params =
            ISwapRouter.ExactInputSingleParams(
                address(WETH), // tokenIn
                address(DAI), // tokenOut
                3000, // 0.3% fee
                address(this), // recipient
                now, // deadline
                address(this).balance, // amountIn
                0, // amountOut
                0 // sqrtPriceLimitX96
            );

        router.exactInputSingle{value: address(this).balance}(params);
        router.refundETH();
    }

    function _sellDAIforLUSD(uint256 _daiAmount) internal {
        if (_daiAmount > 0) {
            _swapStables(DAI, _daiAmount);
        }
    }

    function _sellLUSDforDAI(uint256 _lusdAmount) internal {
        if (_lusdAmount > 0) {
            _swapStables(LUSD, _lusdAmount);
        }
    }

    function _swapStables(IERC20 _from, uint256 _amount) internal {
        int128 i = _from == LUSD ? 0 : 1;
        int128 j = i == 1 ? 0 : 1;

        _checkAllowance(address(curvePool), _from, _amount);

        // DAI is underlying index 1 - LUSD is 0
        uint256 expectedDy = curvePool.get_dy_underlying(i, j, _amount);

        // As a safety measure expect to receive at least 95% of the underlying
        // poolpi's comment: Since get_dy_underlying is manipulable through flash-loan,
        // doing a non 0 min out is unneeded.
        curvePool.exchange_underlying(
            i,
            j,
            _amount,
            expectedDy.mul(95).div(100)
        );
    }
}
