# The MIT License (MIT)
# Copyright © 2025 UnitOne Labs

import hashlib
import xxhash
from typing import Optional, Tuple

import bittensor as bt

from .types import ReferenceBlock


def twox128(data: bytes) -> bytes:
    """
    Compute twox128 hash (used for Substrate storage keys).
    twox128 is xxh64(data, seed=0) || xxh64(data, seed=1)
    """
    h0 = xxhash.xxh64(data, seed=0).digest()
    h1 = xxhash.xxh64(data, seed=1).digest()
    return h0 + h1


def storage_key(module: str, storage: str) -> str:
    """
    Compute Substrate storage key for a module's storage item.

    Args:
        module: Module name (e.g., "System")
        storage: Storage item name (e.g., "Events")

    Returns:
        Hex-encoded storage key with 0x prefix
    """
    module_hash = twox128(module.encode())
    storage_hash = twox128(storage.encode())
    return "0x" + (module_hash + storage_hash).hex()


# Pre-computed storage key for System::Events
SYSTEM_EVENTS_KEY = storage_key("System", "Events")


class RpcClient:
    """
    Client for making Substrate RPC calls through the gateway.
    """

    def __init__(self, rpc_call_fn):
        """
        Initialize the RPC client.

        Args:
            rpc_call_fn: Function to make RPC calls (should accept method, params, request_id)
        """
        self._rpc_call = rpc_call_fn

    def get_current_block(self) -> int:
        """
        Get the current block number.

        Returns:
            Current block number
        """
        response = self._rpc_call("chain_getHeader")
        if response.is_error():
            raise Exception(f"RPC error: {response.error.message}")
        return int(response.result["number"], 16)

    def get_block_hash(self, block_number: int) -> str | None:
        """
        Get block hash for a given block number.

        Args:
            block_number: The block number

        Returns:
            Block hash or None if not found
        """
        response = self._rpc_call("chain_getBlockHash", [block_number])
        if response.is_error():
            return None
        return response.result

    def get_storage(self, key: str, block_hash: str) -> str | None:
        """
        Get storage value at a given key and block.

        Args:
            key: Storage key (hex-encoded)
            block_hash: Block hash to query at

        Returns:
            Storage value (hex-encoded) or None if not found
        """
        response = self._rpc_call("state_getStorage", [key, block_hash])
        if response.is_error():
            return None
        return response.result

    def get_block_events(self, block_hash: str) -> Tuple[int, str]:
        """
        Get events for a block using state_getStorage.

        Args:
            block_hash: The block hash to get events for

        Returns:
            Tuple of (data_length, events_hash) where data_length is the raw hex length
        """
        raw_data = self.get_storage(SYSTEM_EVENTS_KEY, block_hash) or ""

        # Hash the raw hex data directly
        events_hash = hashlib.sha256(raw_data.encode()).hexdigest()

        # Use raw data length as a simple metric
        data_length = len(raw_data)

        return data_length, events_hash

    def get_reference_block(self, block_number: int, verification_type: str) -> ReferenceBlock | None:
        """
        Fetch block data and create a ReferenceBlock.

        Args:
            block_number: The block number to fetch
            verification_type: Type of verification (old, middle, new)

        Returns:
            ReferenceBlock with block data, or None if error
        """
        try:
            block_hash = self.get_block_hash(block_number)
            if not block_hash:
                return None

            data_length, events_hash = self.get_block_events(block_hash)

            return ReferenceBlock(
                block_number=block_number,
                block_hash=block_hash,
                verification_type=verification_type,
                events_data_size=data_length,
                events_hash=events_hash,
            )
        except Exception as e:
            bt.logging.error(f"Failed to get reference block {block_number}: {e}")
            return None
