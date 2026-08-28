"""Unit tests for startup stock phase 5: audit trail and schemas."""

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from agno.tools.startup_stock.audit import AuditStore
from agno.tools.startup_stock.schemas import EquityIntelligenceReport, PipelineStatus


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestAuditStore:
    def test_record_and_list(self, temp_dir):
        store = AuditStore(str(Path(temp_dir) / "audit.db"))
        event = store.record(
            action="add_investor",
            actor="0x1111111111111111111111111111111111111111",
            target="0x2222222222222222222222222222222222222222",
            detail={"shares": 1000},
        )
        assert event.action == "add_investor"
        events = store.list_events(limit=10)
        assert len(events) == 1
        assert events[0].actor.startswith("0x")

    def test_filter_by_action(self, temp_dir):
        store = AuditStore(str(Path(temp_dir) / "audit.db"))
        store.record("sync_cap_table", "0xaaa")
        store.record("add_investor", "0xaaa", target="0xbbb")
        filtered = store.list_events(action="add_investor")
        assert len(filtered) == 1
        assert filtered[0].action == "add_investor"


class TestSchemas:
    def test_equity_intelligence_report(self):
        report = EquityIntelligenceReport(
            summary="Cap table healthy",
            token_symbol="ACME",
            total_investors=2,
            total_shares=100000.0,
            sync_health="healthy",
            recommendations=["Run dry-run sync before live mint"],
        )
        assert report.token_symbol == "ACME"
        assert len(report.recommendations) == 1

    def test_equity_intelligence_report_requires_fields(self):
        with pytest.raises(ValidationError):
            EquityIntelligenceReport(summary="incomplete")

    def test_pipeline_status(self):
        status = PipelineStatus(step="import", status="ok", detail="3 investors")
        assert status.step == "import"
