import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";

const config: HardhatUserConfig = {
  solidity: "0.8.20",
  networks: {
    ganache: {
      url: "http://127.0.0.1:8545",
      accounts: {
        // Dev-only: matches `ganache --deterministic` mnemonic, never use on public networks
        mnemonic: "myth like bonus scare over problem client lizard pioneer submit female collect"
      }
    }
  }
};

export default config;
