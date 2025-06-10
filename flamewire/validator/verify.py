#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests
from bittensor import logging
from flamewire.api import gateway_rpc_call
from .scoring import MinerScorer

SYSTEM_EVENTS_KEY = "0x26aa394eea5630e07c48ae0c9558cef780d41e5e16056765bc8461851072c9d7"
ReferenceBlockData = Tuple[int, str, Optional[str], Optional[dict], int, str]


def _shorten(obj: Any, max_len: int = 64) -> str:
    s = str(obj)
    return s if len(s) <= max_len else f"{s[:max_len]}...[{len(s)} chars]"


@dataclass
class BlockCheckResult:
    block_hash_check: bool = False
    extrinsic_check: bool = False
    error_message: Optional[str] = None


@dataclass
class StateCheckResult:
    success: bool = False
    data_matches: Optional[bool] = None


@dataclass
class NodeTestResult:
    passed_all_checks: bool = True
    errors: List[str] = field(default_factory=list)
    duration: int = 0
    block_checks: List[BlockCheckResult] = field(default_factory=list)
    storage_state_checks: List[StateCheckResult] = field(default_factory=list)


@dataclass
class NodeResult:
    overall_status_passed: bool
    storage_checks_successful: int
    storage_data_matches: int
    uid: int
    hotkey: str
    duration: float
    score: float
    error_details: Optional[str] = None


def _rpc_call(
    session: requests.Session,
    url: str,
    method: str,
    params: list,
    timeout: int = 5,
) -> dict:
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    logging.debug(f"RPC {url} {method} {_shorten(params)}")
    resp = session.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    logging.debug(_shorten(data))
    return data



def _select_unpredictable_blocks(current: int, count: int, seed: bytes) -> List[int]:
    if count == 0:
        return []
    h = hashlib.blake2b(digest_size=64)
    h.update(int(time.time_ns()).to_bytes(16, "big"))
    h.update(seed)
    h.update(current.to_bytes(4, "big"))
    rng = random.Random(h.digest())
    blocks: List[int] = []

    for _ in range(max(count // 3, 1)):
        if current > 50000:
            blocks.append(rng.randint(1000, max(current // 20, 1001)))
        elif current > 1000:
            blocks.append(rng.randint(1, max(current // 10, 1)))
        elif current > 1:
            blocks.append(rng.randint(1, current - 1))

    for _ in range(max(count // 4, 1)):
        if current > 500:
            cand = current - 300 - rng.randint(0, min(50, current - 301))
            if cand > 0:
                blocks.append(cand)

    for _ in range(max(count // 4, 1)):
        if current > 5000:
            lo, hi = max(current // 4, 1), max((current * 3) // 4, 2)
            blocks.append(rng.randint(lo, hi - 1))

    for _ in range(max(count // 4, 1)):
        if current > 1000:
            lo, hi = max(current - 200, 1), max(current - 10, 2)
            blocks.append(rng.randint(lo, hi - 1))
        elif current > 100:
            blocks.append(max(current - rng.randint(10, min(50, current - 1)), 1))

    if not blocks and current > 1 and count:
        blocks.append(max(current // 2, 1))

    if len(blocks) >= 3 and current > 10000:
        cascade = ((blocks[0] + blocks[1] + blocks[2]) % max(current - 1000, 1)) + 500
        if 0 < cascade < current:
            blocks.append(cascade)

    if blocks and current > 10000:
        extra = min(max(count // 5, 1), len(blocks))
        for i in range(extra):
            h2 = hashlib.blake2b(blocks[i].to_bytes(4, "big") + bytes([i]), digest_size=64).digest()
            d = (int.from_bytes(h2[:4], "big") % max(current - 1000, 1)) + 500
            if 0 < d < current:
                blocks.append(d)

    blocks = sorted({b for b in blocks if 0 < b < current})
    if not blocks and count:
        blocks.append(max(current - 1, 1))

    random.shuffle(blocks)
    return blocks[:count]


def prepare_reference_data(
    reference_url: str,
    user_seed: bytes,
    num_blocks: int,
) -> Tuple[List[ReferenceBlockData], int]:
    session = requests.Session()
    session.timeout = 15
    finalized_hash = _rpc_call(session, reference_url, "chain_getFinalizedHead", [])["result"]
    current_block = int(
        _rpc_call(session, reference_url, "chain_getBlock", [finalized_hash])["result"]["block"]["header"]["number"], 16
    )
    block_numbers = _select_unpredictable_blocks(current_block, num_blocks, user_seed)
    if not block_numbers and num_blocks:
        block_numbers = [current_block - i * 2 for i in range(1, num_blocks + 1)] if current_block > num_blocks * 2 else [max(current_block, 1)]
    references: List[ReferenceBlockData] = []
    for num in block_numbers:
        if not 0 < num < current_block:
            continue
        block_hash = _rpc_call(session, reference_url, "chain_getBlockHash", [num]).get("result")
        if not block_hash:
            continue
        events = _rpc_call(session, reference_url, "state_getStorage", [SYSTEM_EVENTS_KEY, block_hash]).get("result")
        metadata = _rpc_call(session, reference_url, "state_call", ["Metadata_metadata", "", block_hash]).get("result")
        blk = _rpc_call(session, reference_url, "chain_getBlock", [block_hash])
        extrinsics = blk["result"]["block"].get("extrinsics", [])
        idx, sender = None, None
        for i, ext_hex in enumerate(extrinsics):
            if isinstance(ext_hex, str):
                ext = bytes.fromhex(ext_hex.removeprefix("0x"))
                if len(ext) >= 36 and ext[0] & 0x80:
                    idx, sender = i, ext[4:36].hex()
                    break
        if idx is not None:
            references.append((num, block_hash, events, metadata, idx, sender))
    if not references and num_blocks:
        raise RuntimeError("Reference data empty")
    return references, current_block


def _storage_ok(
    session: requests.Session,
    gateway_url: str,
    miner: Dict[str, Any],
    block_hash: str,
    expected_events: Optional[str],
    expected_metadata: Optional[dict],
    api_key: str,
) -> tuple:
    events, rt1 = gateway_rpc_call(session, gateway_url, "state_getStorage", [SYSTEM_EVENTS_KEY, block_hash], miner, api_key)
    if events != expected_events:
        return False, rt1
    meta, rt2 = gateway_rpc_call(session, gateway_url, "state_call", ["Metadata_metadata", "", block_hash], miner, api_key)
    return (expected_metadata is None or meta == expected_metadata), rt1 + rt2


def _test_once(
    gateway_url: str,
    reference_blocks: List[ReferenceBlockData],
    session: requests.Session,
    miner: Dict[str, Any],
    api_key: str,
) -> NodeTestResult:
    res = NodeTestResult()
    total_response_time_ms = 0
    for num, ref_hash, events, metadata, ext_idx, sender_pk in reference_blocks:
        try:
            ok, rt_storage = _storage_ok(session, gateway_url, miner, ref_hash, events, metadata, api_key)
            total_response_time_ms += rt_storage
        except Exception as e:
            logging.warning(f"Storage check error {num} {e}")
            ok = False
        res.storage_state_checks.append(StateCheckResult(success=ok, data_matches=ok))
        res.passed_all_checks &= ok
        try:
            actual_hash, rt_hash = gateway_rpc_call(session, gateway_url, "chain_getBlockHash", [num], miner, api_key)
            total_response_time_ms += rt_hash
        except Exception as e:
            logging.warning(f"BlockHash error {num} {e}")
            actual_hash = None
        blk_res = BlockCheckResult()
        if actual_hash == ref_hash:
            blk_res.block_hash_check = True
            try:
                blk, rt_blk = gateway_rpc_call(session, gateway_url, "chain_getBlock", [actual_hash], miner, api_key)
                total_response_time_ms += rt_blk
                exts = blk.get("block", {}).get("extrinsics", [])
                if ext_idx < len(exts):
                    ext_hex = exts[ext_idx]
                    if isinstance(ext_hex, str):
                        ext = bytes.fromhex(ext_hex.removeprefix("0x"))
                        if len(ext) >= 36 and ext[0] & 0x80 and ext[4:36].hex() == sender_pk:
                            blk_res.extrinsic_check = True
            except Exception as e:
                logging.warning(f"Block RPC error {num} {e}")
        if not blk_res.block_hash_check:
            blk_res.error_message = f"Block hash mismatch {num}"
            res.errors.append(blk_res.error_message)
            res.passed_all_checks = False
        elif not blk_res.extrinsic_check:
            blk_res.error_message = f"Extrinsic PK mismatch {num}"
            res.errors.append(blk_res.error_message)
            res.passed_all_checks = False
        res.block_checks.append(blk_res)
        if not res.passed_all_checks:
            break
    res.duration = total_response_time_ms
    return res


def _aggregate(tests: List[NodeTestResult], ref_blocks: List[ReferenceBlockData]) -> Tuple[bool, int, int, float, Optional[str]]:
    success = sum(sc.success for t in tests for sc in t.storage_state_checks)
    matches = sum(sc.data_matches for t in tests for sc in t.storage_state_checks if sc.success)
    expected = len(ref_blocks) * len(tests)
    overall = bool(ref_blocks) and all(t.passed_all_checks for t in tests) and matches == expected
    duration = sum(t.duration for t in tests) if tests else 0.0
    errors: Dict[str, int] = {}
    for t in tests:
        for e in t.errors:
            errors[e] = errors.get(e, 0) + 1
    err_details = "; ".join(f"{e} ({c})" for e, c in sorted(errors.items(), key=lambda x: x[1], reverse=True)[:5]) if errors else None
    return overall, success, matches, duration, err_details


def test_node_multiple(
    gateway_url: str,
    reference_blocks: List[ReferenceBlockData],
    test_runs: int,
    miner: Dict[str, Any],
    api_key: str,
) -> NodeResult:
    session = requests.Session()
    tests = [_test_once(gateway_url, reference_blocks, session, miner, api_key) for _ in range(test_runs)]
    overall, success, matches, duration, err_details = _aggregate(tests, reference_blocks)
    last_n_checks = [t.passed_all_checks for t in tests]
    last_n_response_times = [t.duration / 1000.0 for t in tests]
    if last_n_checks and last_n_response_times:
        score = MinerScorer.quick_score(last_n_checks, last_n_response_times)
    else:
        score = 0.0
    duration = sum(t.duration for t in tests)
    return NodeResult(
        overall_status_passed=overall,
        storage_checks_successful=success,
        storage_data_matches=matches,
        uid=miner["uid"],
        hotkey=miner["hotkey"],
        duration=duration,
        score=score,
        error_details=err_details,
    )


def check_bittensor_nodes(
    rpc_url: str,
    gateway_url: str,
    miners: List[Dict[str, Any]],
    num_ref_blocks: int,
    test_runs: int,
    api_key: str,
) -> List[NodeResult]:
    seed = int(time.time_ns()).to_bytes(16, "big") + gateway_url.encode()
    reference_blocks, _ = prepare_reference_data(rpc_url, seed, num_ref_blocks)
    if not reference_blocks:
        raise RuntimeError("No reference blocks available")
    formatted = [m if isinstance(m, dict) else {"uid": m.uid, "hotkey": m.hotkey} for m in miners]
    results = [test_node_multiple(gateway_url, reference_blocks, test_runs, m, api_key) for m in formatted]
    print_detailed_scores(results, test_runs)
    return results


def print_detailed_scores(node_results, test_runs=1):
    from .scoring import MinerScorer
    scorer = MinerScorer()
    for node in node_results:
        last_n_checks = [node.overall_status_passed] * test_runs
        avg_time = node.duration / test_runs / 1000.0
        last_n_response_times = [avg_time] * test_runs
        checks = last_n_checks[-scorer.window_size:] if len(last_n_checks) > scorer.window_size else last_n_checks
        response_times = last_n_response_times[-scorer.window_size:] if len(last_n_response_times) > scorer.window_size else last_n_response_times
        success_rate = sum(checks) / len(checks) if checks else 0.0
        penalized = False
        if len(last_n_checks) < scorer.window_size:
            success_rate *= 0.8
            penalized = True
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        speed_score = max(0.0, min(1.0, (3.0 - avg_response_time) / (3.0 - 0.5)))
        fail_streak = 0
        for check in reversed(checks):
            if not check:
                fail_streak += 1
            else:
                break
        fail_streak_penalty = min(fail_streak * scorer.penalty_per_fail, scorer.max_penalty)
        print(f"Miner {node.uid} ({node.hotkey}):")
        print(f"  Score: {node.score:.3f}")
        print(f"  Success rate: {success_rate:.2%}" + (" (PENALIZED - below min window size)" if penalized else ""))
        print(f"  Avg response time: {avg_response_time:.3f}s")
        print(f"  Speed score: {speed_score:.2f}")
        print(f"  Fail streak: {fail_streak} (Penalty: {fail_streak_penalty:.2f})")
        print("-" * 40)