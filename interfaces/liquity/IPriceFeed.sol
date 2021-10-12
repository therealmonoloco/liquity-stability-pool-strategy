// SPDX-License-Identifier: MIT

pragma solidity 0.6.12;

interface IPriceFeed {
    // --- Events ---
    event LastGoodPriceUpdated(uint256 _lastGoodPrice);

    // --- Function ---
    function fetchPrice() external returns (uint256);

    function lastGoodPrice() external view returns (uint256);
}
