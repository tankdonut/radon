#!/usr/bin/env python3
"""
Interactive Brokers Order Management — Cancel & Modify

Connects to TWS/IB Gateway to cancel or modify open orders.
All output is JSON to stdout for API route parsing.

Usage:
  python3 scripts/ib_order_manage.py cancel --order-id 10 --perm-id 12345
  python3 scripts/ib_order_manage.py modify --order-id 10 --perm-id 12345 --new-price 22.50
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from ib_insync import IB
except ImportError:
    print(json.dumps({"status": "error", "message": "ib_insync not installed"}))
    sys.exit(1)

# Add parent so utils is importable when run from project root
sys.path.insert(0, str(Path(__file__).parent))

from utils.ib_connection import (
    CLIENT_IDS,
    DEFAULT_HOST,
    DEFAULT_GATEWAY_PORT,
)

DEFAULT_PORT = DEFAULT_GATEWAY_PORT
DEFAULT_CLIENT_ID = CLIENT_IDS["ib_order_manage"]


def output(status: str, message: str, **extra):
    """Print JSON result and exit."""
    print(json.dumps({"status": status, "message": message, **extra}))
    sys.exit(0 if status == "ok" else 1)


def find_trade(ib: IB, order_id: int, perm_id: int):
    """Find an open trade by permId (preferred) or orderId."""
    ib.reqAllOpenOrders()
    ib.sleep(1)
    trades = ib.openTrades()

    # Prefer permId (globally unique across IB sessions)
    if perm_id > 0:
        for trade in trades:
            if trade.order.permId == perm_id:
                return trade

    # Fallback to orderId
    if order_id > 0:
        for trade in trades:
            if trade.order.orderId == order_id:
                return trade

    return None


def cancel_order(ib: IB, order_id: int, perm_id: int):
    """Cancel an open order."""
    trade = find_trade(ib, order_id, perm_id)
    if trade is None:
        output("error", f"Trade not found (orderId={order_id}, permId={perm_id})")

    status = trade.orderStatus.status
    if status in ("Filled", "Cancelled", "ApiCancelled"):
        output("error", f"Order already {status} — cannot cancel")

    ib.cancelOrder(trade.order)
    # Wait for status change
    for _ in range(10):
        ib.sleep(0.5)
        if trade.orderStatus.status in ("Cancelled", "ApiCancelled"):
            break

    final_status = trade.orderStatus.status
    if final_status in ("Cancelled", "ApiCancelled"):
        output("ok", f"Order cancelled (orderId={trade.order.orderId})",
               orderId=trade.order.orderId, finalStatus=final_status)
    else:
        output("ok", f"Cancel requested — current status: {final_status}",
               orderId=trade.order.orderId, finalStatus=final_status)


def modify_order(ib: IB, order_id: int, perm_id: int, new_price: float):
    """Modify limit price of an open order."""
    trade = find_trade(ib, order_id, perm_id)
    if trade is None:
        output("error", f"Trade not found (orderId={order_id}, permId={perm_id})")

    status = trade.orderStatus.status
    if status in ("Filled", "Cancelled", "ApiCancelled"):
        output("error", f"Order already {status} — cannot modify")

    order_type = trade.order.orderType
    if order_type not in ("LMT", "STP LMT"):
        output("error", f"Cannot modify price on {order_type} order — only LMT and STP LMT supported")

    if new_price <= 0:
        output("error", "New price must be > 0")

    old_price = trade.order.lmtPrice
    trade.order.lmtPrice = new_price
    ib.placeOrder(trade.contract, trade.order)

    # Wait for acknowledgement
    for _ in range(10):
        ib.sleep(0.5)
        if trade.orderStatus.status in ("Submitted", "PreSubmitted"):
            break

    final_status = trade.orderStatus.status
    output("ok", f"Order modified: ${old_price} → ${new_price}",
           orderId=trade.order.orderId, oldPrice=old_price,
           newPrice=new_price, finalStatus=final_status)


def main():
    parser = argparse.ArgumentParser(description="Cancel or modify IB orders")
    sub = parser.add_subparsers(dest="action", required=True)

    cancel_p = sub.add_parser("cancel")
    cancel_p.add_argument("--order-id", type=int, default=0)
    cancel_p.add_argument("--perm-id", type=int, default=0)
    cancel_p.add_argument("--host", default=DEFAULT_HOST)
    cancel_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    modify_p = sub.add_parser("modify")
    modify_p.add_argument("--order-id", type=int, default=0)
    modify_p.add_argument("--perm-id", type=int, default=0)
    modify_p.add_argument("--new-price", type=float, required=True)
    modify_p.add_argument("--host", default=DEFAULT_HOST)
    modify_p.add_argument("--port", type=int, default=DEFAULT_PORT)

    args = parser.parse_args()

    if args.order_id == 0 and args.perm_id == 0:
        output("error", "Must provide --order-id or --perm-id")

    ib = IB()
    try:
        ib.connect(args.host, args.port, clientId=DEFAULT_CLIENT_ID)
    except Exception as e:
        output("error", f"IB connection failed: {e}")

    try:
        if args.action == "cancel":
            cancel_order(ib, args.order_id, args.perm_id)
        elif args.action == "modify":
            modify_order(ib, args.order_id, args.perm_id, args.new_price)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
