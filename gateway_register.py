#!/usr/bin/env python3

import os
import bittensor
import sys
import json
from urllib.parse import urlparse
from flamewire.api import register_miner
from loguru import logger

logger.remove()
logger.add(sys.stderr, colorize=True, format="<level>{level: <8}</level> {message}")

FINNEY_NETUID = 97
TESTNET_NETUID = 0
REGISTER_URL = "https://gateway.flamewire.io/v1/miners/register"

def prompt_with_default(prompt, default):
    response = input(f"{prompt} (default: {default}): ").strip()
    return response if response else default

def get_config(network):
    config = bittensor.Config()
    config.subtensor = bittensor.subtensor.config()
    config.subtensor.network = network

    return config

def main():
    wallets_input = prompt_with_default("Enter wallets path", "~/.bittensor/wallets")
    wallets_path = os.path.expanduser(wallets_input)
    coldkey_name = prompt_with_default("Enter wallet name", "default")
    hotkey_name = prompt_with_default("Enter hotkey name", "default")
    network = prompt_with_default("Enter network", "finney")
    wallet = None
    netuid = None

    try:
        wallet = bittensor.wallet(path=wallets_path, name=coldkey_name, hotkey=hotkey_name)
        wallet.unlock_coldkey()
        logger.success("Wallet unlocked successfully.")
    except Exception as e:
        logger.error(f"Failed to unlock wallet: {e}")
        return
    
    if network == "finney":
        netuid = FINNEY_NETUID
    elif network == "testnet":
        netuid = TESTNET_NETUID
    else:
        print("Error: Invalid network!")
        return

    config = get_config(network)
    sub = bittensor.subtensor(config=config)

    neuron = sub.get_neuron_for_pubkey_and_subnet(wallet.hotkey.ss58_address, netuid)
    if neuron == neuron.get_null_neuron():
        print(f"Error: You are not registered on subnet {netuid} on {network}!")
        return

    logger.info(f"Neuron: {neuron}")
    uid = neuron.uid;
    
    message = f"{uid}:{wallet.hotkey.ss58_address}"
    signature = wallet.hotkey.sign(message.encode("utf-8")).hex()
    logger.info(f"Signature: {signature}")

    node_url = input("Enter Bittensor node URL: ").strip()
    parsed_url = urlparse(node_url)
    if parsed_url.scheme not in ("ws", "wss", "http", "https") or not parsed_url.netloc:
        print(f"Error: Invalid node URL: {node_url}")
        return

    logger.info("\nRegistration settings:")
    logger.info(f"Wallet {{ coldkey: {coldkey_name}, hotkey: {hotkey_name} }}")
    logger.info(f"Message: {message}")
    logger.info(f"Node URL: {node_url}")

    payload = {
        "hotkey": wallet.hotkey.ss58_address,
        "uid": uid,
        "rpc_urls": [{"blockchain": "bittensor", "url": node_url}],
        "signature": signature,
        "message": message
    }
    try:
        data = register_miner(REGISTER_URL, payload)
        api_key = data.get("api_key")
        if api_key:
            logger.success("Registration successful!")
            try:
                with open("miner.json", "w") as f:
                    json.dump({"api_key": api_key}, f, indent=4)
                logger.info("API key saved to miner.json")
            except Exception as e:
                logger.error(f"Failed to write miner.json: {e}")
        else:
            logger.warning(f"Registration succeeded but no api_key found: {data}")
    except Exception as e:
        logger.error(f"Registration failed: {e}")

if __name__ == "__main__":
    main() 