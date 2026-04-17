import { expect } from "chai";
import { ethers } from "hardhat";
import { VendingMachine } from "../typechain-types";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";

describe("VendingMachine", function () {
  let contract: VendingMachine;
  let owner: HardhatEthersSigner;
  let buyer: HardhatEthersSigner;
  let other: HardhatEthersSigner;

  // Product IDs as deployed in constructor
  const COLA_ID = 1;
  const COLA_PRICE = ethers.parseEther("0.001");

  beforeEach(async function () {
    [owner, buyer, other] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("VendingMachine");
    contract = await Factory.deploy();
    await contract.waitForDeployment();
  });

  // Test 1: Successful purchase of 1 item
  it("allows a user to buy 1 item successfully", async function () {
    const productsBefore = await contract.getProducts();
    const stockBefore = productsBefore.find(p => p.id === BigInt(COLA_ID))!.stock;

    await contract.connect(buyer).buyProduct(COLA_ID, 1, { value: COLA_PRICE });

    const productsAfter = await contract.getProducts();
    const stockAfter = productsAfter.find(p => p.id === BigInt(COLA_ID))!.stock;

    expect(stockAfter).to.equal(stockBefore - BigInt(1));
  });

  // Test 2: Successful purchase of multiple qty
  it("tracks ownership correctly when buying multiple qty", async function () {
    const qty = 3;
    const totalCost = COLA_PRICE * BigInt(qty);

    await contract.connect(buyer).buyProduct(COLA_ID, qty, { value: totalCost });

    const owned = await contract.getOwnershipCount(buyer.address, COLA_ID);
    expect(owned).to.equal(BigInt(qty));
  });

  // Test 3: Purchase fails — insufficient payment
  it("reverts when payment is insufficient", async function () {
    const tooLittle = ethers.parseEther("0.0001"); // less than 0.001 ETH price
    await expect(
      contract.connect(buyer).buyProduct(COLA_ID, 1, { value: tooLittle })
    ).to.be.revertedWith("Insufficient payment");
  });

  // Test 4: Purchase fails — out of stock
  it("reverts when product is out of stock", async function () {
    // Buy all 10 Cola first
    const totalCost = COLA_PRICE * BigInt(10);
    await contract.connect(buyer).buyProduct(COLA_ID, 10, { value: totalCost });

    // Now try to buy 1 more — should revert
    await expect(
      contract.connect(other).buyProduct(COLA_ID, 1, { value: COLA_PRICE })
    ).to.be.revertedWith("Insufficient stock");
  });

  // Test 5: Non-owner cannot restock
  it("reverts when non-owner tries to restock", async function () {
    await expect(
      contract.connect(buyer).restockProduct(COLA_ID, 5)
    ).to.be.revertedWith("Not owner");
  });

  // Test 6: Owner restock succeeds + event emitted
  it("allows owner to restock and emits ProductRestocked event", async function () {
    const productsBefore = await contract.getProducts();
    const stockBefore = productsBefore.find(p => p.id === BigInt(COLA_ID))!.stock;

    await expect(contract.connect(owner).restockProduct(COLA_ID, 5))
      .to.emit(contract, "ProductRestocked")
      .withArgs(BigInt(COLA_ID), stockBefore + BigInt(5));

    const productsAfter = await contract.getProducts();
    const stockAfter = productsAfter.find(p => p.id === BigInt(COLA_ID))!.stock;
    expect(stockAfter).to.equal(stockBefore + BigInt(5));
  });

  // Test 7: State verification after purchase — both ownership and stock correct
  it("correctly updates both stock and ownership after a purchase", async function () {
    const qty = 2;
    const totalCost = COLA_PRICE * BigInt(qty);

    const productsBefore = await contract.getProducts();
    const stockBefore = productsBefore.find(p => p.id === BigInt(COLA_ID))!.stock;
    const ownedBefore = await contract.getOwnershipCount(buyer.address, COLA_ID);

    await contract.connect(buyer).buyProduct(COLA_ID, qty, { value: totalCost });

    const productsAfter = await contract.getProducts();
    const stockAfter = productsAfter.find(p => p.id === BigInt(COLA_ID))!.stock;
    const ownedAfter = await contract.getOwnershipCount(buyer.address, COLA_ID);

    expect(stockAfter).to.equal(stockBefore - BigInt(qty));
    expect(ownedAfter).to.equal(ownedBefore + BigInt(qty));
  });
});
