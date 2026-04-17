import { expect } from "chai";
import { ethers } from "hardhat";
import { TicketMarket } from "../typechain-types";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";

describe("TicketMarket", function () {
  let contract: TicketMarket;
  let owner: HardhatEthersSigner;
  let alice: HardhatEthersSigner;
  let bob: HardhatEthersSigner;

  const EVENT1_ID = 1;  // "Rock Night" — 0.01 ETH
  const EVENT1_PRICE = ethers.parseEther("0.01");

  beforeEach(async function () {
    [owner, alice, bob] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("TicketMarket");
    contract = await Factory.deploy();
    await contract.waitForDeployment();
  });

  // Test 1: Successful ticket purchase
  it("allows a user to buy a ticket and records ownership", async function () {
    await contract.connect(alice).buyTicket(EVENT1_ID, { value: EVENT1_PRICE });

    const aliceTickets = await contract.getTicketsByOwner(alice.address);
    expect(aliceTickets.length).to.equal(1);
    expect(aliceTickets[0].eventId).to.equal(BigInt(EVENT1_ID));
    expect(aliceTickets[0].owner).to.equal(alice.address);
  });

  // Test 2: Purchase fails — insufficient payment
  it("reverts when payment is below ticket price", async function () {
    const tooLittle = ethers.parseEther("0.001");
    await expect(
      contract.connect(alice).buyTicket(EVENT1_ID, { value: tooLittle })
    ).to.be.revertedWith("Insufficient payment");
  });

  // Test 3: Successful ticket transfer
  it("allows owner to transfer ticket to another address", async function () {
    await contract.connect(alice).buyTicket(EVENT1_ID, { value: EVENT1_PRICE });
    const aliceTickets = await contract.getTicketsByOwner(alice.address);
    const ticketId = aliceTickets[0].id;

    await contract.connect(alice).transferTicket(ticketId, bob.address);

    const bobTickets = await contract.getTicketsByOwner(bob.address);
    expect(bobTickets.length).to.equal(1);
    expect(bobTickets[0].owner).to.equal(bob.address);

    const aliceTicketsAfter = await contract.getTicketsByOwner(alice.address);
    expect(aliceTicketsAfter.length).to.equal(0);
  });

  // Test 4: Transfer fails — not the owner
  it("reverts when non-owner tries to transfer a ticket", async function () {
    await contract.connect(alice).buyTicket(EVENT1_ID, { value: EVENT1_PRICE });
    const aliceTickets = await contract.getTicketsByOwner(alice.address);
    const ticketId = aliceTickets[0].id;

    await expect(
      contract.connect(bob).transferTicket(ticketId, bob.address)
    ).to.be.revertedWith("Not ticket owner");
  });

  // Test 5: Successful resale flow
  it("completes full resale: list → buy → payment to seller, ownership to buyer", async function () {
    await contract.connect(alice).buyTicket(EVENT1_ID, { value: EVENT1_PRICE });
    const aliceTickets = await contract.getTicketsByOwner(alice.address);
    const ticketId = aliceTickets[0].id;

    const resalePrice = ethers.parseEther("0.015");
    await contract.connect(alice).listForResale(ticketId, resalePrice);

    const sellerBalanceBefore = await ethers.provider.getBalance(alice.address);
    await contract.connect(bob).buyResaleTicket(ticketId, { value: resalePrice });
    const sellerBalanceAfter = await ethers.provider.getBalance(alice.address);

    // seller received payment
    expect(sellerBalanceAfter).to.be.gt(sellerBalanceBefore);

    // bob now owns the ticket
    const bobTickets = await contract.getTicketsByOwner(bob.address);
    expect(bobTickets.length).to.equal(1);
    expect(bobTickets[0].owner).to.equal(bob.address);
    expect(bobTickets[0].forResale).to.equal(false);
  });

  // Test 6: Admin permission failure — non-owner cannot create event
  it("reverts when non-owner calls createEvent", async function () {
    await expect(
      contract.connect(alice).createEvent("Punk Show", "2026-06-01", "The Pit", 200, ethers.parseEther("0.02"))
    ).to.be.revertedWith("Not owner");
  });

  // Test 7: Edge case — buy ticket when event is sold out
  it("reverts when trying to buy a ticket from a sold-out event", async function () {
    await contract.connect(owner).createEvent("Tiny Gig", "2026-07-01", "Garage", 1, ethers.parseEther("0.01"));
    const evts = await contract.getEvents();
    const tinyGigId = evts[evts.length - 1].id;

    // First buyer gets the only ticket
    await contract.connect(alice).buyTicket(tinyGigId, { value: ethers.parseEther("0.01") });

    // Second buyer should fail
    await expect(
      contract.connect(bob).buyTicket(tinyGigId, { value: ethers.parseEther("0.01") })
    ).to.be.revertedWith("Sold out");
  });

  // Test 8: Final ownership after sequence of actions
  it("correctly tracks ownership after buy → list → resale purchase", async function () {
    await contract.connect(alice).buyTicket(EVENT1_ID, { value: EVENT1_PRICE });
    const aliceTickets = await contract.getTicketsByOwner(alice.address);
    const ticketId = aliceTickets[0].id;

    await contract.connect(alice).listForResale(ticketId, ethers.parseEther("0.012"));
    await contract.connect(bob).buyResaleTicket(ticketId, { value: ethers.parseEther("0.012") });

    // alice no longer owns
    const aliceFinal = await contract.getTicketsByOwner(alice.address);
    expect(aliceFinal.length).to.equal(0);

    // bob now owns
    const bobFinal = await contract.getTicketsByOwner(bob.address);
    expect(bobFinal.length).to.equal(1);
    expect(bobFinal[0].id).to.equal(ticketId);
  });
});
