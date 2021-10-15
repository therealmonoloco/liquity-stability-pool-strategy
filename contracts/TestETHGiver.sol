// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

contract TestETHGiver {
    receive() external payable {}

    function sendETHGainToDepositor(uint256 _amount) external {
        if (_amount == 0) {
            return;
        }

        (bool success, ) = msg.sender.call{value: _amount}("");
        require(success, "StabilityPool: sending ETH failed");
    }
}
