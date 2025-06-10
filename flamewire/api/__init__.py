import requests
from typing import Any, Dict, List


def _shorten(obj: Any, max_len: int = 64) -> str:
    s = str(obj)
    return s if len(s) <= max_len else f"{s[:max_len]}...[{len(s)} chars]"


def gateway_rpc_call(
    session: requests.Session,
    gateway_url: str,
    method: str,
    params: list,
    miner: Dict[str, Any],
    api_key: str,
    timeout: int = 5,
) -> tuple:
    payload = {"method": method, "params": params, "id": 1, "miners": [miner]}
    url = f"{gateway_url.rstrip('/')}/v1/validators/bittensor"
    resp = session.post(url, json=payload, timeout=timeout, headers={"x-api-key": api_key})
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text[:500]
        raise RuntimeError(f"{detail}") from None
    data = resp.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"Empty gateway response {_shorten(data)}")
    inner = data[0].get("result")
    if inner is None:
        raise RuntimeError(f"Gateway result missing {_shorten(data[0])}")
    response_time_ms = data[0].get("response_time_ms", 0)
    result = inner["result"] if isinstance(inner, dict) and "result" in inner else inner
    return result, response_time_ms


def post_node_results(gateway_url: str, api_key: str, nodes: List[Dict[str, Any]]) -> None:
    url = f"{gateway_url.rstrip('/')}/v1/validators/nodes"
    resp = requests.post(url, json={"nodes": nodes}, headers={"x-api-key": api_key}, timeout=10)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text[:500]
        raise RuntimeError(f"{detail}") from None


def register_miner(register_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(register_url, json=payload, timeout=10)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text[:500]

        raise RuntimeError(f"{detail}") from None

    return resp.json()