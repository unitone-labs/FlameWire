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
REGISTER_URL = "https://gateway.flamewire.io/v1/miners/unregister"

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



    logger.info("\nUnregistration settings:")
    logger.info(f"Wallet {{ coldkey: {coldkey_name}, hotkey: {hotkey_name} }}")
    logger.info(f"Message: {message}")


    payload = {
        "hotkey": wallet.hotkey.ss58_address,
        "uid": uid
    }
    try:
        data = register_miner(REGISTER_URL, payload)
        logger.success("Unregistration successful!")
        
    except Exception as e:
        logger.error(f"Unregistration failed: {e}")

if __name__ == "__main__":
    main() 