# The MIT License (MIT)
# Copyright © 2025 UnitOne Labs

import hashlib
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, TypeVar, Iterator, Tuple, Callable

import bittensor as bt

from flamewire.gateway import Node, MinerNode, CheckStats, StatisticsResponse, ReferenceBlock, SYSTEM_EVENTS_KEY

T = TypeVar("T")


def batched(items: List[T], batch_size: int) -> Iterator[List[T]]:
    """
    Split a list into batches of specified size.

    Args:
        items: List of items to batch
        batch_size: Maximum size of each batch

    Yields:
        Lists of items, each with at most batch_size elements
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def build_miner_nodes(
    nodes_by_hotkey: Dict[str, List[Node]],
    stats: StatisticsResponse,
) -> List[MinerNode]:
    """
    Build a list of MinerNode objects from nodes and statistics.

    Args:
        nodes_by_hotkey: Dict mapping miner hotkey to list of Node objects
        stats: Statistics response from gateway

    Returns:
        List of MinerNode objects with health stats
    """
    stats_by_node = {s.node_id: s.health for s in stats.statistics}

    miner_nodes = []
    for hotkey, nodes in nodes_by_hotkey.items():
        for node in nodes:
            health = stats_by_node.get(node.id, CheckStats(total=0, passed=0))
            miner_nodes.append(MinerNode(
                miner_hotkey=hotkey,
                node_id=node.id,
                region=node.region,
                health=health,
            ))

    return miner_nodes


def get_random_blocks(current_block: int) -> Tuple[int, int, int]:
    """
    Get random blocks from three intervals (old, middle, new).

    Args:
        current_block: The current block number

    Returns:
        Tuple of (old_block, middle_block, new_block)
    """
    interval_size = current_block // 3

    old_block = random.randint(0, interval_size - 1)
    middle_block = random.randint(interval_size, 2 * interval_size - 1)
    new_block = random.randint(2 * interval_size, current_block - 1)

    return old_block, middle_block, new_block


def verify_node_data(
    node: MinerNode,
    reference_blocks: List[ReferenceBlock],
    rpc_call_fn,
) -> Tuple[bool, List[int]]:
    """
    Verify a miner node's data against reference blocks.

    Args:
        node: The miner node to verify
        reference_blocks: List of reference blocks to check against
        rpc_call_fn: Function to make RPC calls (gateway.rpc_call)

    Returns:
        Tuple of (passed, latencies) where latencies is a list of latency_ms values
    """
    latencies = []

    for ref_block in reference_blocks:
        try:
            # Get events data from the miner's node
            response = rpc_call_fn(
                "state_getStorage",
                node.node_id,
                node.region,
                [SYSTEM_EVENTS_KEY, ref_block.block_hash],
            )

            # Collect latency if available
            if response.latency_ms is not None:
                latencies.append(response.latency_ms)

            if response.is_error():
                bt.logging.warning(
                    f"Node {node.node_id} RPC error on block {ref_block.block_number}: {response.error.message}"
                )
                return False, latencies

            # Hash the raw data
            raw_data = response.result or ""
            events_hash = hashlib.sha256(raw_data.encode()).hexdigest()

            # Compare with reference
            if events_hash != ref_block.events_hash:
                bt.logging.warning(
                    f"Node {node.node_id} hash mismatch on block {ref_block.block_number} "
                    f"({ref_block.verification_type}): expected {ref_block.events_hash[:16]}... got {events_hash[:16]}..."
                )
                return False, latencies

        except Exception as e:
            bt.logging.warning(f"Node {node.node_id} verification error: {e}")
            return False, latencies

    return True, latencies


def verify_all_nodes(
    miner_nodes: List[MinerNode],
    reference_blocks: List[ReferenceBlock],
    rpc_call_fn: Callable,
    max_workers: int = 32,
) -> Tuple[int, int]:
    """
    Verify all miner nodes against reference blocks in parallel.

    Args:
        miner_nodes: List of miner nodes to verify
        reference_blocks: List of reference blocks to check against
        rpc_call_fn: Function to make RPC calls (gateway.rpc_call)
        max_workers: Maximum number of concurrent verifications

    Returns:
        Tuple of (verified_count, failed_count)
    """
    if not miner_nodes or not reference_blocks:
        return 0, 0

    verified_count = 0
    failed_count = 0

    def verify_single_node(node: MinerNode) -> Tuple[MinerNode, bool, List[int]]:
        passed, latencies = verify_node_data(node, reference_blocks, rpc_call_fn)
        return node, passed, latencies

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(verify_single_node, node): node for node in miner_nodes}

        for future in as_completed(futures):
            try:
                node, passed, latencies = future.result()
                node.data_verified = passed

                # Calculate average latency
                if latencies:
                    node.avg_latency_ms = sum(latencies) / len(latencies)

                if passed:
                    verified_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                node = futures[future]
                node.data_verified = False
                failed_count += 1
                bt.logging.error(f"Node {node.node_id} verification failed with exception: {e}")

    return verified_count, failed_count
