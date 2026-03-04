"""Tests for ib_order_manage.py — mocks IB connection."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ib_order_manage import find_trade, cancel_order, modify_order, output


# ─── Helpers ────────────────────────────────────────────

def make_trade(order_id=10, perm_id=12345, status="Submitted", order_type="LMT", lmt_price=22.50):
    trade = MagicMock()
    trade.order.orderId = order_id
    trade.order.permId = perm_id
    trade.order.orderType = order_type
    trade.order.lmtPrice = lmt_price
    trade.orderStatus.status = status
    trade.contract = MagicMock()
    return trade


def make_ib(trades=None):
    ib = MagicMock()
    ib.openTrades.return_value = trades or []
    ib.sleep = MagicMock()
    return ib


# ─── find_trade ─────────────────────────────────────────

class TestFindTrade:
    def test_find_by_perm_id(self):
        t = make_trade(order_id=10, perm_id=999)
        ib = make_ib([t])
        assert find_trade(ib, 0, 999) is t

    def test_find_by_order_id(self):
        t = make_trade(order_id=42, perm_id=0)
        ib = make_ib([t])
        assert find_trade(ib, 42, 0) is t

    def test_perm_id_preferred_over_order_id(self):
        t1 = make_trade(order_id=10, perm_id=100)
        t2 = make_trade(order_id=10, perm_id=200)
        ib = make_ib([t1, t2])
        assert find_trade(ib, 10, 200) is t2

    def test_not_found(self):
        ib = make_ib([make_trade(order_id=10, perm_id=100)])
        assert find_trade(ib, 99, 88) is None


# ─── cancel_order ───────────────────────────────────────

class TestCancelOrder:
    def test_cancel_success(self):
        t = make_trade(status="Submitted")
        # After cancel, status changes
        t.orderStatus.status = "Submitted"

        def side_effect(order):
            t.orderStatus.status = "Cancelled"

        ib = make_ib([t])
        ib.cancelOrder = MagicMock(side_effect=side_effect)

        with pytest.raises(SystemExit) as exc:
            cancel_order(ib, 10, 12345)
        assert exc.value.code == 0
        ib.cancelOrder.assert_called_once_with(t.order)

    def test_cancel_already_filled(self):
        t = make_trade(status="Filled")
        ib = make_ib([t])

        with pytest.raises(SystemExit) as exc:
            cancel_order(ib, 10, 12345)
        assert exc.value.code == 1

    def test_cancel_not_found(self):
        ib = make_ib([])

        with pytest.raises(SystemExit) as exc:
            cancel_order(ib, 99, 88)
        assert exc.value.code == 1


# ─── modify_order ───────────────────────────────────────

class TestModifyOrder:
    def test_modify_success(self):
        t = make_trade(status="Submitted", order_type="LMT", lmt_price=20.00)
        ib = make_ib([t])
        ib.placeOrder = MagicMock()

        with pytest.raises(SystemExit) as exc:
            modify_order(ib, 10, 12345, 22.50)
        assert exc.value.code == 0
        assert t.order.lmtPrice == 22.50
        ib.placeOrder.assert_called_once_with(t.contract, t.order)

    def test_modify_non_lmt_fails(self):
        t = make_trade(status="Submitted", order_type="MKT")
        ib = make_ib([t])

        with pytest.raises(SystemExit) as exc:
            modify_order(ib, 10, 12345, 22.50)
        assert exc.value.code == 1

    def test_modify_already_filled(self):
        t = make_trade(status="Filled", order_type="LMT")
        ib = make_ib([t])

        with pytest.raises(SystemExit) as exc:
            modify_order(ib, 10, 12345, 22.50)
        assert exc.value.code == 1

    def test_modify_zero_price_fails(self):
        t = make_trade(status="Submitted", order_type="LMT")
        ib = make_ib([t])

        with pytest.raises(SystemExit) as exc:
            modify_order(ib, 10, 12345, 0)
        assert exc.value.code == 1

    def test_modify_not_found(self):
        ib = make_ib([])

        with pytest.raises(SystemExit) as exc:
            modify_order(ib, 99, 88, 22.50)
        assert exc.value.code == 1

    def test_modify_stp_lmt_allowed(self):
        t = make_trade(status="Submitted", order_type="STP LMT", lmt_price=18.00)
        ib = make_ib([t])
        ib.placeOrder = MagicMock()

        with pytest.raises(SystemExit) as exc:
            modify_order(ib, 10, 12345, 19.00)
        assert exc.value.code == 0
        assert t.order.lmtPrice == 19.00


# ─── output ─────────────────────────────────────────────

class TestOutput:
    def test_output_ok(self, capsys):
        with pytest.raises(SystemExit) as exc:
            output("ok", "done")
        assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ok"
        assert data["message"] == "done"

    def test_output_error(self, capsys):
        with pytest.raises(SystemExit) as exc:
            output("error", "fail")
        assert exc.value.code == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"

    def test_output_extra_fields(self, capsys):
        with pytest.raises(SystemExit) as exc:
            output("ok", "done", orderId=42, newPrice=22.5)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["orderId"] == 42
        assert data["newPrice"] == 22.5
