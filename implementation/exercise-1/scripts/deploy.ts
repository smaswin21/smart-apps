import { ethers } from "hardhat";

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  const VendingMachine = await ethers.getContractFactory("VendingMachine");
  const contract = await VendingMachine.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("VendingMachine deployed to:", address);
  console.log("Add this to app/.env as CONTRACT_ADDRESS=", address);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
