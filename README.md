![Flamewire Cover](./flamewire-cover.png)
# SN97 - FlameWire: Decentralized Infrastructure

![Subnet 97 Badge](https://img.shields.io/badge/Subnet-97-blue)

**FlameWire** is a specialized **subnet within the Bittensor network** designed to provide **decentralized RPC, node, and API services** for multiple blockchains.

Like Alchemy, Ankr, or other infrastructure providers—but fully decentralized FlameWire democratizes blockchain infrastructure access, beginning with **Ethereum**, **Bittensor**, and **SUI**, and expanding further.

---

## Quick Navigation

| Section | Description |
|---------|-------------|
| [Key Components](#key-components) | Overview of Miners, Validators, and Subnet Owner roles |
| [Economic Model](#economic-model) | Tokenomics and reward structure |
| [Setup for Miners and Validators](#setup-for-miners-and-validators) | Registration and setup instructions |
| [Competitive Advantages](#competitive-advantages) | Key benefits of FlameWire |
| [Development Directions](#development-directions) | Future roadmap and planned features |

---

## Overview

- **Decentralized infrastructure** for RPC and API services  
- **Multi-chain support**: Ethereum, Bittensor, SUI (and more coming)  
- **Scalable, secure, and resilient** architecture  
- Designed for developers, validators, and network operators

---

## Key Components

### Miners  
Provide the underlying infrastructure:

- **Multi-Chain Node Operators**: Serve Ethereum, Bittensor, SUI, etc.  
- **Global Coverage**: Deploy nodes across regions for low-latency access  
- **Redundant Infrastructure**: Ensures continuous service availability  
- **Secure Communication**: Verified via cryptographic signatures  
- **Scalability**: Easily extend node capacity as demand grows  

### Validators  
Ensure performance and honesty of the network:

- **Uptime Monitoring**: Ensure consistent availability of nodes  
- **Integrity Verification**: Validate correctness of RPC/API responses  
- **Performance Evaluation**: Monitor latency, reliability, and throughput  
- **Weight Allocation**: Assign performance-based rewards  
- **Honesty Checks**: Detect and penalize misbehavior or downtime  

### Subnet Owner  
Coordinates and manages network activity:

- **Traffic Direction**: Distributes API/RPC requests to optimal nodes  
- **Access Management**: Controls permissions for users and developers  
- **Network Optimization**: Improves performance and resource efficiency  

---

## Economic Model

- **Stake-Based Free-Tier Access**: Users get free access based on staked Alpha Tokens 
- **Pay-as-you-go**: Developers pay based on resource consumption  
- **Circular Tokenomics**: Payments are recycled into subnet liquidity  
- **Performance-Based Rewards**: High-quality service providers earn more  

---

## Setup for Miners and Validators

### Registration 

To register as a miner or validator on FlameWire subnet, follow these steps:

1. **Install Bittensor**
   ```bash
   pip install bittensor-cli
   ```

2. **Create a Wallet**
   ```bash
   btcli wallet new --wallet.name flamewire_wallet
   ```

3. **Register Neuron**
   ```bash
   btcli subnet register --wallet.name flamewire_wallet --wallet.hotkey default --subtensor.network finney --subnet.netuid 97
   ```

4. **Verify Registration**
   ```bash
   btcli subnet list --subtensor.network finney --subnet.netuid 97
   ```
### Miners 

After registering your neuron, miners need to set up and run the gateway service:

1. **Clone the Repository**
   ```bash
   git clone https://github.com/unitone-labs/FlameWire
   cd FlameWire
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```


3. **Register Gateway**
   ```bash
   python3 gateway_register.py
   ```
    Enter wallets path (default: ~/.bittensor/wallets): 
    Enter wallet name (default: default): 
    Enter hotkey name (default: default): 
    Enter network (default: finney):
    Enter Bittensor node URL:


The gateway registration process will:
- Register your services with the flamewire gateway
- Begin serving RPC/API requests
- Start earning rewards based on performance

Monitor your miner's performance using:
```bash
btcli subnet metagraph --subtensor.network finney --subnet.netuid 97
```

### Validators

To run a validator on FlameWire subnet, follow these steps:

1. **Install Dependencies**
   ```bash
   # Install Python dependencies
   pip install -r requirements.txt
   pip install -e .

   # Install PM2 for process management
   npm install -g pm2
   ```

2. **Get Validator API Key**
   - Join our Discord: https://discord.flamewire.io
   - Request a validator API key from the team
   - This key is required for validator operations


3. **Start Validator**
   Using PM2 for process management:
   ```bash
   # Copy the example environment file and edit with your credentials
   cp .env.example .env
   # Start validator with PM2 (values are read from .env)
    pm2 start neurons/validator.py --name flamewire-validator --interpreter python3 -- \
      --netuid 97 \
      --logging.debug

   # Monitor validator
   pm2 monit

   # View logs
   pm2 logs flamewire-validator

   # Restart if needed
   pm2 restart flamewire-validator
   ```

5. **Validator Management Commands**
   ```bash
   # Check validator status
   pm2 status

   # Stop validator
   pm2 stop flamewire-validator

   # Delete validator from PM2
   pm2 delete flamewire-validator

   # Save PM2 process list
   pm2 save

   # Setup PM2 to start on system boot
   pm2 startup
   ```

Important Notes:
- The validator API key is required and can be obtained from our Discord
- RPC_URL can be your own local archive node or any third-party provider
- Store `WALLET_NAME`, `WALLET_HOTKEY`, `SUBTENSOR_NETWORK`, `RPC_URL`, `API_KEY`, and `WANDB_API_KEY` in a `.env` file
- Ensure your system has sufficient resources (CPU, RAM, network)
- Monitor your validator's performance regularly
- Keep your API key and wallet credentials secure

### Evaluation and Rewards

- Validators assign scores and weights to miners  
- Alpha token rewards are distributed based on performance  
- User payments re-enter the subnet economy  

---

## Competitive Advantages

- **True Decentralization**: No central point of control or failure  
- **Cost Efficiency**: Competition reduces access costs  
- **Global Availability**: Regional node access ensures speed and uptime  
- **Resilient Architecture**: Built-in redundancy across providers  
- **Unified Multi-Chain Access**: One platform for multiple blockchains  
- **Stake-Driven Free Access**: Lowers barriers for new users  

---

## Development Directions

- Expansion to additional blockchains  
- Introduction of chain-specific APIs  
- Enhanced monitoring and analytics tools  
- Foundation partnerships for staked-access models  
- AI-based optimization of request routing  