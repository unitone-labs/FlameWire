# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2025 UnitOne Labs

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import bittensor as bt

from flamewire.base.validator import BaseValidatorNeuron
from flamewire.gateway import GatewayClient, RpcClient
from flamewire.gateway.types import LatencyStats
from flamewire.utils.metagraph import get_miner_hotkeys
from flamewire.utils.helpers import batched, build_miner_nodes, get_random_blocks, verify_all_nodes
from flamewire.utils.wandb_logging import log_verification_metrics


class Validator(BaseValidatorNeuron):
    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)

        # Initialize gateway client
        self.gateway = GatewayClient(
            api_key=self.config.validator.api_key,
            base_url=self.config.gateway.url,
        )
        bt.logging.info(f"Gateway client initialized: {self.config.gateway.url}")

        # Initialize RPC client using gateway's public RPC endpoint
        self.rpc = RpcClient(self.gateway.public_rpc_call)

    async def verify(self):
        """Lookup nodes for all miners and verify them."""
        miner_hotkeys = get_miner_hotkeys(self.metagraph, self.uid)
        if not miner_hotkeys:
            return

        # Lookup nodes for all miners
        all_nodes = {}
        for batch in batched(miner_hotkeys, 100):
            nodes = self.gateway.lookup_nodes(batch)
            all_nodes.update(nodes)

        # Get verification statistics
        stats = self.gateway.get_statistics()

        # Build MinerNode array
        miner_nodes = build_miner_nodes(all_nodes, stats)

        # Get current block
        current_block = self.rpc.get_current_block()
        bt.logging.info(f"Current block: {current_block}")

        # Get random blocks from each interval
        old_block, middle_block, new_block = get_random_blocks(current_block)
        bt.logging.info(f"Random blocks - old: {old_block}, middle: {middle_block}, new: {new_block}")

        # Fetch reference blocks
        reference_blocks = []
        for block_num, verification_type in [
            (old_block, "old"),
            (middle_block, "middle"),
            (new_block, "new"),
        ]:
            ref_block = self.rpc.get_reference_block(block_num, verification_type)
            if ref_block:
                reference_blocks.append(ref_block)
                bt.logging.info(f"Reference block {verification_type}: #{ref_block.block_number} hash={ref_block.block_hash[:16]}... size={ref_block.events_data_size}")

        # Verify all miner nodes against reference blocks (parallel)
        bt.logging.info(f"Verifying {len(miner_nodes)} nodes against {len(reference_blocks)} reference blocks (max_workers={self.config.validator.max_workers})...")
        verified_count, failed_count = verify_all_nodes(
            miner_nodes,
            reference_blocks,
            self.gateway.rpc_call,
            max_workers=self.config.validator.max_workers,
        )
        bt.logging.info(f"Verification complete: {verified_count} passed, {failed_count} failed")

        latencies = [n.avg_latency_ms for n in miner_nodes if n.avg_latency_ms is not None]
        latency_stats = LatencyStats.from_latencies(latencies)
        unique_miners = set(n.miner_hotkey for n in miner_nodes)

        log_verification_metrics(
            self.wandb,
            step=self.step,
            block=self.block,
            verified_count=verified_count,
            failed_count=failed_count,
            total_nodes=len(miner_nodes),
            total_miners=len(unique_miners),
            latency_stats=latency_stats,
        )


if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
