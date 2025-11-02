# data.py
from __future__ import annotations
import time, random
from typing import Any, Dict, List, Tuple
import requests
import json as pyjson

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "polymarket-chile-probabilities/1.0 (educational script)",
}

class ApiError(Exception):
    pass

def _sleep_with_jitter(base: float, attempt: int) -> None:
    delay = base * (2 ** attempt) + random.uniform(0, 0.25)
    time.sleep(min(delay, 8.0))

def _request_with_retries(
    method: str,
    url: str,
    *,
    session: requests.Session,
    json: Any | None = None,
    params: Dict[str, Any] | None = None,
    max_retries: int = 4,
) -> requests.Response:
    """Retry en 429/5xx con backoff exponencial + jitter; error para el resto."""
    for attempt in range(max_retries + 1):
        resp = session.request(method, url, json=json, params=params, timeout=20)
        status = resp.status_code
        if status < 400:
            return resp
        if status == 429 or 500 <= status < 600:
            if attempt < max_retries:
                _sleep_with_jitter(0.5, attempt)
                continue
        raise ApiError(f"{method} {url} -> {status}: {resp.text[:300]}")

def _ensure_list(value: Any) -> List[str]:
    """Normaliza lista / string JSON / 'a,b' / escalar -> lista[str]."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        s = value.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            try:
                decoded = pyjson.loads(s)
                if isinstance(decoded, list):
                    return [str(x) for x in decoded]
            except Exception:
                pass
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    return [str(value)]

def fetch_event_and_markets(event_id: int) -> Dict[str, Any]:
    """GET /events?id=... -> evento (incluye .markets)."""
    with requests.Session() as s:
        s.headers.update(DEFAULT_HEADERS)
        resp = _request_with_retries("GET", f"{GAMMA_BASE}/events", session=s, params={"id": event_id})
        data = resp.json()
        if not isinstance(data, list) or not data:
            raise ApiError("Evento no encontrado o respuesta inesperada")
        return data[0]

def build_price_params(markets: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Payload para POST /prices: para cada token pedimos BUY y SELL en un batch."""
    params: List[Dict[str, str]] = []
    for m in markets:
        token_ids = _ensure_list(m.get("clobTokenIds"))
        for tid in token_ids:
            if not tid:
                continue
            params.append({"token_id": tid, "side": "BUY"})
            params.append({"token_id": tid, "side": "SELL"})
    return params

def fetch_prices(token_side_params: List[Dict[str, str]]) -> Dict[str, Dict[str, float]]:
    """POST /prices -> { token_id: {BUY: float|str, SELL: float|str}, ... }"""
    if not token_side_params:
        return {}
    with requests.Session() as s:
        s.headers.update(DEFAULT_HEADERS)
        resp = _request_with_retries("POST", f"{CLOB_BASE}/prices", session=s, json=token_side_params)
        return resp.json()

def market_outcomes_and_tokens(market: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Pares (label_outcome, token_id) alineados por índice."""
    labels = market.get("shortOutcomes") or market.get("outcomes")
    labels_list = _ensure_list(labels)
    token_ids = _ensure_list(market.get("clobTokenIds"))
    pairs: List[Tuple[str, str]] = []
    for i, tid in enumerate(token_ids):
        label = labels_list[i] if i < len(labels_list) else f"Outcome {i}"
        pairs.append((label, tid))
    return pairs

def compute_mid(bid: float | None, ask: float | None) -> float | None:
    if bid is not None and ask is not None:
        return (bid + ask) / 2.0
    return bid if bid is not None else ask
