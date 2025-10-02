# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 Opentensor Foundation

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import os
import subprocess
import argparse
import bittensor as bt
from .logging import setup_events_logger


def load_env(env_path: str = ".env"):
    """Load environment variables from a .env file if it exists."""
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())
    except Exception as e:
        bt.logging.warning(f"Failed to load {env_path}: {e}")

def check_config(cls, config: "bt.Config"):
    r"""Checks/validates the config namespace object."""
    bt.logging.check_config(config)

    full_path = os.path.expanduser(
        "{}/{}/{}/netuid{}/{}".format(
            config.logging.logging_dir,  
            config.wallet.name,
            config.wallet.hotkey,
            config.netuid,
            config.neuron.name,
        )
    )
    print("full path:", full_path)
    config.neuron.full_path = os.path.expanduser(full_path)
    if not os.path.exists(config.neuron.full_path):
        os.makedirs(config.neuron.full_path, exist_ok=True)

    if not config.neuron.dont_save_events:
        # Add custom event logger for the events.
        events_logger = setup_events_logger(
            config.neuron.full_path, config.neuron.events_retention_size
        )
        bt.logging.register_primary_logger(events_logger.name)


def add_args(cls, parser):
    """
    Adds relevant arguments to the parser for operation.
    """

    parser.add_argument("--netuid", type=int, help="Subnet netuid", default=97)

    parser.add_argument(
        "--neuron.epoch_length",
        type=int,
        help="The default epoch length (how often we set weights, measured in 12 second blocks).",
        default=360,
    )

    parser.add_argument(
        "--neuron.block_per_tempo",
        type=int,
        help="The number of blocks per tempo.",
        default=360,
    )

    parser.add_argument(
        "--neuron.events_retention_size",
        type=str,
        help="Events retention size.",
        default=2 * 1024 * 1024 * 1024,  # 2 GB
    )

    parser.add_argument(
        "--neuron.dont_save_events",
        action="store_true",
        help="If set, we dont save events to a log file.",
        default=False,
    )

    parser.add_argument(
        "--wandb.off",
        action="store_true",
        help="Turn off wandb.",
        default=False,
    )

    parser.add_argument(
        "--wandb.offline",
        action="store_true",
        help="Runs wandb in offline mode.",
        default=False,
    )

    parser.add_argument(
        "--wandb.notes",
        type=str,
        help="Notes to add to the wandb run.",
        default="",
    )

def add_validator_args(cls, parser):
    """Add validator specific arguments to the parser."""

    parser.add_argument(
        "--neuron.name",
        type=str,
        help="Trials for this neuron go in neuron.root / (wallet_cold - wallet_hot) / neuron.name. ",
        default="validator",
    )

    parser.add_argument(
        "--neuron.timeout",
        type=float,
        help="The timeout for each forward call in seconds.",
        default=10,
    )

    parser.add_argument(
        "--neuron.num_concurrent_verifications",
        type=int,
        help="The number of concurrent verifications running at any time.",
        default=1,
    )

    parser.add_argument(
        "--rpc_url",
        type=str,
        help="The RPC URL for the validator.",
        default="http://localhost:9944",
    )

    parser.add_argument(
        "--api_key",
        type=str,
        help="The API key for the validator.",
        default="",
    )

    parser.add_argument(
        "--gateway_url",
        type=str,
        help="The gateway URL.",
        default="https://gateway.flamewire.io",
    )

    parser.add_argument(
        "--neuron.vpermit_tao_limit",
        type=int,
        help="The maximum number of TAO allowed to query a validator with a vpermit.",
        default=4096,
    )

def config(cls):
    """
    Returns the configuration object specific to this miner or validator after adding relevant arguments.
    """
    load_env()
    parser = argparse.ArgumentParser()
    bt.wallet.add_args(parser)
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.axon.add_args(parser)
    cls.add_args(parser)

    cfg = bt.config(parser)

    # Override sensitive settings from environment variables if present
    cfg.rpc_url = os.getenv("RPC_URL", cfg.rpc_url)
    cfg.api_key = os.getenv("API_KEY", cfg.api_key)
    cfg.gateway_url = os.getenv("GATEWAY_URL", cfg.gateway_url)
    cfg.wallet.name = os.getenv("WALLET_NAME", cfg.wallet.name)
    cfg.wallet.hotkey = os.getenv("WALLET_HOTKEY", cfg.wallet.hotkey)
    cfg.subtensor.network = os.getenv("SUBTENSOR_NETWORK", cfg.subtensor.network)

    return cfg