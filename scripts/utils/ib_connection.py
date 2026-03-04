"""Shared Interactive Brokers connection utilities.

Centralises client-ID registry, default host/port constants, and a
convenience ``connect_ib`` helper used by every IB script.
"""

from ib_insync import IB

# Client-ID registry — each script gets a unique ID to avoid conflicts.
CLIENT_IDS: dict = {
    "ib_sync": 1,
    "ib_order": 2,
    "ib_orders": 11,
    "ib_fill_monitor": 52,
    "exit_order_service": 60,
    "ib_reconcile": 90,
    "fetch_analyst_ratings": 99,
    "ib_order_manage": 12,
    "ib_realtime_server": 100,
}

DEFAULT_HOST = "127.0.0.1"
DEFAULT_GATEWAY_PORT = 4001
DEFAULT_TWS_PORT = 7497


def connect_ib(
    client_name: str,
    host: str = None,
    port: int = None,
    client_id: int = None,
    timeout: int = 10,
) -> IB:
    """Connect to TWS / IB Gateway and return an ``IB`` instance.

    Args:
        client_name: Key in ``CLIENT_IDS`` (e.g. ``"ib_sync"``).
        host: Override host (default ``DEFAULT_HOST``).
        port: Override port (default ``DEFAULT_GATEWAY_PORT``).
        client_id: Override the registry client-ID.
        timeout: Connection timeout in seconds.

    Returns:
        Connected ``IB`` instance.

    Raises:
        ValueError: If *client_name* is not in the registry
            **and** no *client_id* override is given.
        ConnectionRefusedError (or similar): If IB is not reachable.
    """
    if client_id is None:
        if client_name not in CLIENT_IDS:
            raise ValueError(
                f"Unknown client name '{client_name}'. "
                f"Known names: {sorted(CLIENT_IDS.keys())}"
            )
        client_id = CLIENT_IDS[client_name]

    ib = IB()
    ib.connect(
        host or DEFAULT_HOST,
        port or DEFAULT_GATEWAY_PORT,
        clientId=client_id,
        timeout=timeout,
    )
    return ib
