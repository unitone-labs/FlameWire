import requests
from typing import Any, Dict, List

from flamewire.utils.url_sanitizer import (
    safe_http_error_message,
    safe_exception_message,
)


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
    try:
        resp = session.post(url, json=payload, timeout=timeout, headers={"x-api-key": api_key})
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(safe_http_error_message(resp, e)) from None
    except Exception as e:
        raise RuntimeError(safe_exception_message(e)) from None
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
    url = f"{gateway_url.rstrip('/')}/v1/validators/bittensor/nodes"
    try:
        resp = requests.post(url, json={"nodes": nodes}, headers={"x-api-key": api_key}, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(safe_http_error_message(resp, e)) from None
    except Exception as e:
        raise RuntimeError(safe_exception_message(e)) from None


def get_validator_nodes(gateway_url: str, api_key: str, uids: List[int]) -> Dict[str, Any]:
    query = ",".join(str(u) for u in uids)
    url = f"{gateway_url.rstrip('/')}/v1/validators/bittensor/nodes"
    try:
        resp = requests.get(url, params={"uids": query}, headers={"x-api-key": api_key}, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(safe_http_error_message(resp, e)) from None
    except Exception as e:
        raise RuntimeError(safe_exception_message(e)) from None
    return resp.json()


def register_miner(register_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = requests.post(register_url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(safe_http_error_message(resp, e)) from None
    except Exception as e:
        raise RuntimeError(safe_exception_message(e)) from None

    return resp.json()

def unregister_miner(register_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(register_url, json=payload, timeout=10)
    resp.raise_for_status()