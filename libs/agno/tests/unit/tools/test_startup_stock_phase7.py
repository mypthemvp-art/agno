"""Unit tests for startup stock phase 7: option pool, 409A, SAFE/SAFT."""

import tempfile
from pathlib import Path

import pytest

from agno.tools.startup_stock.instruments import (
    InstrumentStore,
    convert_safe,
)
from agno.tools.startup_stock.option_pool import OptionPoolStore
from agno.tools.startup_stock.valuation import (
    Valuation409AStore,
    compute_option_intrinsic_value,
    suggest_strike_from_409a,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestOptionPool:
    def test_set_and_grant(self, temp_dir):
        store = OptionPoolStore(str(Path(temp_dir) / "pool.db"))
        summary = store.set_authorized_shares(10000)
        assert summary["authorized_shares"] == 10000
        assert summary["available_shares"] == 10000

        result = store.grant_options("Eve", shares=1000, strike_price=0.5)
        assert "error" not in result
        assert result["grant"]["shares"] == 1000
        assert result["pool"]["available_shares"] == 9000

    def test_over_grant_rejected(self, temp_dir):
        store = OptionPoolStore(str(Path(temp_dir) / "pool.db"))
        store.set_authorized_shares(500)
        result = store.grant_options("Eve", shares=600, strike_price=0.1)
        assert "error" in result

    def test_exercise_and_cancel(self, temp_dir):
        store = OptionPoolStore(str(Path(temp_dir) / "pool.db"))
        store.set_authorized_shares(5000)
        grant = store.grant_options("Eve", shares=1000, strike_price=0.25)["grant"]
        store.update_vested_shares(grant["grant_id"], 400)
        exercised = store.exercise_options(grant["grant_id"], 200)
        assert exercised["exercised_now"] == 200
        assert exercised["exercise_cost"] == 50.0
        assert exercised["grant"]["exercised_shares"] == 200

        cancelled = store.cancel_grant(grant["grant_id"])
        assert cancelled["status"] == "cancelled"
        assert store.get_pool_summary()["available_shares"] == 5000


class TestValuation409A:
    def test_record_and_latest(self, temp_dir):
        store = Valuation409AStore(str(Path(temp_dir) / "val.db"))
        recorded = store.record_valuation(fair_market_value=0.42, firm="Acme Valuations")
        assert recorded["fair_market_value"] == 0.42
        latest = store.get_latest()
        assert latest is not None
        assert latest.firm == "Acme Valuations"
        status = store.is_current()
        assert status["current"] is True

    def test_intrinsic_and_strike(self):
        intrinsic = compute_option_intrinsic_value(1.0, 0.4, 1000)
        assert intrinsic["intrinsic_value"] == 600.0
        assert intrinsic["in_the_money"] is True
        strike = suggest_strike_from_409a(0.5)
        assert strike["suggested_strike"] == 0.5


class TestInstruments:
    def test_add_and_convert_safe(self, temp_dir):
        store = InstrumentStore(str(Path(temp_dir) / "inst.db"))
        instrument = store.add_instrument(
            investor_name="Seed Fund",
            instrument_type="safe",
            investment_amount=250_000,
            valuation_cap=5_000_000,
            discount_rate=0.2,
        )
        assert instrument["status"] == "outstanding"

        conversion = convert_safe(
            investment_amount=250_000,
            priced_round_price_per_share=2.0,
            pre_money_shares=2_500_000,
            valuation_cap=5_000_000,
            discount_rate=0.2,
        )
        # Cap price = 5e6 / 2.5e6 = 2.0; discount price = 2.0 * 0.8 = 1.6 -> discount wins
        assert conversion["conversion_method"] == "discount"
        assert conversion["conversion_price"] == 1.6
        assert conversion["converted_shares"] == 156250.0

        marked = store.mark_converted(
            instrument["instrument_id"],
            converted_shares=conversion["converted_shares"],
            conversion_price=conversion["conversion_price"],
        )
        assert marked["status"] == "converted"
        summary = store.summary()
        assert summary["converted_count"] == 1
        assert summary["outstanding_count"] == 0

    def test_cap_beats_discount(self):
        conversion = convert_safe(
            investment_amount=100_000,
            priced_round_price_per_share=10.0,
            pre_money_shares=1_000_000,
            valuation_cap=4_000_000,
            discount_rate=0.1,
        )
        # Cap price = 4.0; discount price = 9.0 -> cap wins
        assert conversion["conversion_method"] == "valuation_cap"
        assert conversion["conversion_price"] == 4.0
        assert conversion["converted_shares"] == 25000.0
