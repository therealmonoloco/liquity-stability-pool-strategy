// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "./Strategy.sol";

// The purpose of this wrapper contract is to expose internal functions
// that may contain application logic and therefore need to be tested
contract TestStrategy is Strategy {

      constructor(address _vault) public Strategy(_vault) {}

      function sellLQTYforDAI() public {
        _sellLQTYforDAI();
      }

      function sellETHforDAI() public {
        _sellETHforDAI();
      }

      function sellDAIforLUSD() public {
        _sellDAIforLUSD();
      }

      function claimRewards() public {
        _claimRewards();
      }
}