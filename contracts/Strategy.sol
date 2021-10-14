// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

// These are the core Yearn libraries
import {
    BaseStrategy,
    StrategyParams
} from "@yearnvaults/contracts/BaseStrategy.sol";
import "@openzeppelin/contracts/math/Math.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "../interfaces/liquity/IPriceFeed.sol";
import "../interfaces/liquity/IStabilityPool.sol";
import "../interfaces/uniswap/IAndreOnChainOracle.sol";
import "../interfaces/uniswap/ISwapRouter.sol";

contract Strategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    // LQTY rewards accrue to Stability Providers who deposit LUSD to the Stability Pool
    IERC20 internal constant LQTY =
        IERC20(0x6DEA81C8171D0bA574754EF6F8b412F2Ed88c54D);

    // Source of liquidity to repay debt from liquidated troves
    IStabilityPool internal constant stabilityPool =
        IStabilityPool(0x66017D22b0f8556afDd19FC67041899Eb65a21bb);

    // Chainlink ETH:USD with Tellor ETH:USD as fallback
    IPriceFeed internal constant priceFeed =
        IPriceFeed(0x4c517D4e2C851CA76d7eC94B805269Df0f2201De);

    // Uniswap v3 router to do LQTY->ETH
    ISwapRouter internal constant router =
        ISwapRouter(0xE592427A0AEce92De3Edee1F18E0157C05861564);

    // Use Uniswap v3 TWAP to fetch LQTY price in ETH
    IAndreOnChainOracle internal constant twapOracle =
        IAndreOnChainOracle(0x0F1f5A87f99f0918e6C81F16E59F3518698221Ff);

    // Wrapped Ether - Used for swaps routing
    IERC20 internal constant WETH =
        IERC20(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);

    // DAI - Used for swaps routing
    IERC20 internal constant DAI =
        IERC20(0x6B175474E89094C44Da98b954EedeAC495271d0F);

    constructor(address _vault) public BaseStrategy(_vault) {
        // You can set these parameters on deployment to whatever you want
        // maxReportDelay = 6300;
        // profitFactor = 100;
        // debtThreshold = 0;
    }

    // Strategy should be able to receive ETH
    receive() external payable {}

    function name() external view override returns (string memory) {
        return "StrategyLiquityStabilityPoolLUSD";
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        uint256 lqtyInETH =
            totalLQTYBalance().mul(1e18).div(
                twapOracle.ethToAsset(1e18, address(LQTY), 60)
            );
        uint256 ethBalanceIncludingRewards = totalETHBalance().add(lqtyInETH);

        return
            totalLUSDBalance().add(
                ethBalanceIncludingRewards.mul(priceFeed.lastGoodPrice()).div(
                    1e18
                )
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
        // How much do we owe to the LUSD vault?
        uint256 totalDebt = vault.strategies(address(this)).totalDebt;

        // Claim LQTY/ETH and sell them for more LUSD
        _claimRewards();

        // At this point all ETH and LQTY has been converted to LUSD
        uint256 totalAssetsAfterProfit = totalLUSDBalance();

        _profit = totalAssetsAfterProfit > totalDebt
            ? totalAssetsAfterProfit.sub(totalDebt)
            : 0;

        uint256 _amountFreed;
        (_amountFreed, _loss) = liquidatePosition(
            _debtOutstanding.add(_profit)
        );
        _debtPayment = Math.min(_debtOutstanding, _amountFreed);

        if (_loss > _profit) {
            _loss = _loss.sub(_profit);
            _profit = 0;
        } else {
            _profit = _profit.sub(_loss);
            _loss = 0;
        }
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        // Provide any leftover balance to the stability pool
        // Use zero address for frontend as we are interacting with the contracts directly
        uint256 wantBalance = balanceOfWant();
        if (wantBalance > _debtOutstanding) {
            stabilityPool.provideToSP(
                wantBalance.sub(_debtOutstanding),
                address(0)
            );
        }
    }

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
        uint256 amountToWithdraw = _amountNeeded.sub(balance);

        // Cannot withdraw more than what we have in deposit
        amountToWithdraw = Math.min(
            amountToWithdraw,
            stabilityPool.getCompoundedLUSDDeposit(address(this))
        );

        if (amountToWithdraw > 0) {
            stabilityPool.withdrawFromSP(amountToWithdraw);
        }

        // After withdrawing from the stability pool it could happen that we have
        // enough LQTY / ETH to cover a loss before reporting it.
        // However, doing a swap at this point could make withdrawals insecure
        // and front-runnable, so we assume LUSD that cannot be returned is a
        // realized loss.
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
        (_amountFreed, ) = liquidatePosition(estimatedTotalAssets());
    }

    function prepareMigration(address _newStrategy) internal override {
        if (stabilityPool.getCompoundedLUSDDeposit(address(this)) <= 0) {
            return;
        }

        // Withdraw entire LUSD balance from Stability Pool
        // ETH + LQTY gains should be harvested before migrating
        // `migrate` will automatically forward all `want` in this strategy to the new one
        stabilityPool.withdrawFromSP(
            stabilityPool.getCompoundedLUSDDeposit(address(this))
        );
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
            balanceOfWant().add(
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
        // Withdraw minimum amount to force LQTY and ETH to be claimed
        if (stabilityPool.getCompoundedLUSDDeposit(address(this)) > 0) {
            stabilityPool.withdrawFromSP(1);
        }

        // Convert LQTY rewards to DAI
        if (LQTY.balanceOf(address(this)) > 0) {
            _sellLQTYforDAI();
        }

        // Convert ETH obtained from liquidations to DAI
        if (address(this).balance > 0) {
            _sellETHforDAI();
        }

        // Use DAI-LUSD 0.05% pool in Uniswap V3 to get LUSD
        if (DAI.balanceOf(address(this)) > 0) {
            _sellDAIforLUSD();
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

    function _sellDAIforLUSD() internal {
        _checkAllowance(address(router), DAI, DAI.balanceOf(address(this)));

        ISwapRouter.ExactInputSingleParams memory params =
            ISwapRouter.ExactInputSingleParams(
                address(DAI), // tokenIn
                address(want), // tokenOut
                500, // 0.05% fee
                address(this), // recipient
                now, // deadline
                DAI.balanceOf(address(this)), // amountIn
                0, // amountOut
                0 // sqrtPriceLimitX96
            );
        router.exactInputSingle(params);
    }
}
