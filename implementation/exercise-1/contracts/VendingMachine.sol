// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title VendingMachine
/// @notice A decentralised vending machine. Stores product catalog, stock,
///         and purchase ownership on-chain. ETH flows directly through the contract.
contract VendingMachine {

    struct Product {
        uint id;
        string name;
        uint priceWei;
        uint stock;
        bool exists;
    }

    address public owner;
    uint private nextProductId;

    mapping(uint => Product) public products;
    mapping(address => mapping(uint => uint)) public ownership;
    uint[] public productIds;

    event ProductPurchased(
        address indexed buyer,
        uint productId,
        uint qty,
        uint totalPaid
    );

    event ProductRestocked(uint indexed productId, uint newStock);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        nextProductId = 1;

        // Pre-load 4 products
        _addProduct("Cola",      0.001 ether, 10);
        _addProduct("Chocolate", 0.002 ether, 10);
        _addProduct("Coffee",    0.003 ether, 10);
        _addProduct("Juice",     0.0025 ether, 10);
    }

    /// @notice Internal helper used by constructor and addProduct()
    function _addProduct(string memory name, uint priceWei, uint stock) internal {
        uint id = nextProductId++;
        products[id] = Product(id, name, priceWei, stock, true);
        productIds.push(id);
    }

    /// @notice Buy one or more units of a product. ETH accumulates in contract; owner withdraws via withdraw().
    function buyProduct(uint id, uint qty) external payable {
        require(products[id].exists, "Product does not exist");
        require(qty > 0, "Quantity must be > 0");
        require(products[id].stock >= qty, "Insufficient stock");
        require(msg.value >= products[id].priceWei * qty, "Insufficient payment");

        products[id].stock -= qty;
        ownership[msg.sender][id] += qty;

        emit ProductPurchased(msg.sender, id, qty, msg.value);
    }

    /// @notice Returns the full product list.
    function getProducts() external view returns (Product[] memory) {
        Product[] memory list = new Product[](productIds.length);
        for (uint i = 0; i < productIds.length; i++) {
            list[i] = products[productIds[i]];
        }
        return list;
    }

    /// @notice Returns how many units of product `id` that `addr` owns.
    function getOwnershipCount(address addr, uint id) external view returns (uint) {
        return ownership[addr][id];
    }

    /// @notice Restock an existing product. Owner only.
    function restockProduct(uint id, uint qty) external onlyOwner {
        require(products[id].exists, "Product does not exist");
        require(qty > 0, "Quantity must be > 0");
        products[id].stock += qty;
        emit ProductRestocked(id, products[id].stock);
    }

    /// @notice Add a new product to the machine. Owner only.
    function addProduct(string memory name, uint priceWei, uint stock) external onlyOwner {
        require(bytes(name).length > 0, "Name required");
        require(priceWei > 0, "Price must be > 0");
        _addProduct(name, priceWei, stock);
    }

    /// @notice Withdraw accumulated ETH from purchases. Owner only.
    function withdraw() external onlyOwner {
        uint balance = address(this).balance;
        require(balance > 0, "Nothing to withdraw");
        (bool sent, ) = payable(owner).call{value: balance}("");
        require(sent, "Withdraw failed");
    }
}
