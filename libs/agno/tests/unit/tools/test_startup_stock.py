"""Unit tests for startup stock sync engine and toolkit."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from agno.tools.startup_stock.sync import (
    CapTableEntry,
    CapTableStore,
    CapTableSyncEngine,
)
from agno.tools.startup_stock.toolkit import shares_to_wei, wei_to_shares


class MockOnChain:
    def __init__(self):
        self.balances: dict[str, int] = {}
        self.mint_calls: list[tuple[str, int]] = []

    def get_balance(self, wallet_address: str) -> int:
        return self.balances.get(wallet_address.lower(), 0)

    def mint_shares_wei(self, wallet_address: str, amount_wei: int) -> str:
        self.mint_calls.append((wallet_address.lower(), amount_wei))
        addr = wallet_address.lower()
        self.balances[addr] = self.balances.get(addr, 0) + amount_wei
        return "0xabc123"


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield str(Path(tmpdir) / "cap_table.db")


@pytest.fixture
def store(temp_db):
    return CapTableStore(temp_db)


@pytest.fixture
def on_chain():
    return MockOnChain()


@pytest.fixture
def sync_engine(store, on_chain):
    return CapTableSyncEngine(
        store=store,
        on_chain_reader=on_chain,
        on_chain_minter=on_chain,
        shares_to_wei=shares_to_wei,
        wei_to_shares=wei_to_shares,
        max_retries=2,
        retry_delay_seconds=0.01,
    )


class TestCapTableStore:
    def test_upsert_and_list(self, store):
        entry = CapTableEntry(
            investor_name="Alice",
            wallet_address="0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
            shares=1000.0,
        )
        store.upsert_entry(entry)
        entries = store.list_entries()
        assert len(entries) == 1
        assert entries[0].investor_name == "Alice"
        assert entries[0].shares == 1000.0

    def test_get_entry(self, store):
        entry = CapTableEntry(
            investor_name="Bob",
            wallet_address="0x3Dfc53E3C77bb4e30Ce333Be1a66Ce62558bE395",
            shares=500.0,
        )
        store.upsert_entry(entry)
        fetched = store.get_entry("0x3Dfc53E3C77bb4e30Ce333Be1a66Ce62558bE395")
        assert fetched is not None
        assert fetched.investor_name == "Bob"

    def test_checksum_computed_on_upsert(self, store):
        entry = CapTableEntry(
            investor_name="Carol",
            wallet_address="0x1111111111111111111111111111111111111111",
            shares=100.0,
        )
        store.upsert_entry(entry)
        fetched = store.get_entry("0x1111111111111111111111111111111111111111")
        assert fetched is not None
        assert fetched.checksum == entry.compute_checksum()


class TestCapTableSyncEngine:
    def test_add_investor_validates_address(self, sync_engine):
        with pytest.raises(ValueError, match="Invalid wallet address"):
            sync_engine.add_investor("Bad", "not-an-address", 100.0)

    def test_add_investor_validates_shares(self, sync_engine):
        with pytest.raises(ValueError, match="Shares must be positive"):
            sync_engine.add_investor(
                "Bad",
                "0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
                0,
            )

    def test_sync_noop_when_balanced(self, sync_engine, on_chain):
        addr = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"
        sync_engine.add_investor("Alice", addr, 1000.0)
        on_chain.balances[addr.lower()] = shares_to_wei(1000.0)

        result = sync_engine.sync_all(dry_run=False)
        assert result.synced == 1
        assert result.failed == 0
        assert len(on_chain.mint_calls) == 0

    def test_sync_mints_delta(self, sync_engine, on_chain):
        addr = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"
        sync_engine.add_investor("Alice", addr, 1000.0)

        result = sync_engine.sync_all(dry_run=False)
        assert result.synced == 1
        assert len(on_chain.mint_calls) == 1
        assert on_chain.mint_calls[0][1] == shares_to_wei(1000.0)

    def test_sync_dry_run_no_mint(self, sync_engine, on_chain):
        addr = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"
        sync_engine.add_investor("Alice", addr, 500.0)

        result = sync_engine.sync_all(dry_run=True)
        assert len(on_chain.mint_calls) == 0
        assert result.skipped == 1

    def test_sync_detects_drift(self, sync_engine, on_chain):
        addr = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"
        sync_engine.add_investor("Alice", addr, 500.0)
        on_chain.balances[addr.lower()] = shares_to_wei(1000.0)

        result = sync_engine.sync_all(dry_run=False)
        assert result.drifted == 1
        assert len(on_chain.mint_calls) == 0

    def test_sync_retries_on_failure(self, store, on_chain):
        call_count = 0

        def flaky_mint(wallet_address: str, amount_wei: int) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return "error: network timeout"
            return "0xsuccess"

        engine = CapTableSyncEngine(
            store=store,
            on_chain_reader=on_chain,
            on_chain_minter=Mock(mint_shares_wei=flaky_mint),
            shares_to_wei=shares_to_wei,
            wei_to_shares=wei_to_shares,
            max_retries=3,
            retry_delay_seconds=0.01,
        )
        addr = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"
        engine.add_investor("Alice", addr, 100.0)

        result = engine.sync_all(dry_run=False)
        assert result.synced == 1
        assert call_count == 2


class TestStartupStockTools:
    @pytest.fixture
    def mock_web3_client(self):
        mock_client = Mock()
        mock_client.to_wei = Mock(return_value=1000000000)
        mock_client.eth = Mock()
        mock_client.eth.get_block = Mock(return_value={"baseFeePerGas": 20000000000})
        mock_client.eth.get_transaction_count = Mock(return_value=0)
        mock_client.eth.chain_id = 11155111
        mock_client.eth.estimate_gas = Mock(return_value=100000)
        mock_client.eth.send_raw_transaction = Mock(return_value=b"\x12\x34\x56")
        mock_client.eth.wait_for_transaction_receipt = Mock(return_value={"status": 1})
        mock_account = Mock()
        mock_account.address = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"
        mock_client.eth.account = Mock()
        mock_client.eth.account.from_key = Mock(return_value=mock_account)
        mock_signed = Mock()
        mock_signed.raw_transaction = b"signed"
        mock_client.eth.account.sign_transaction = Mock(return_value=mock_signed)
        return mock_client

    @pytest.fixture
    def mock_contract(self):
        contract = Mock()
        contract.functions.name.return_value.call.return_value = "Acme Startup"
        contract.functions.symbol.return_value.call.return_value = "ACME"
        contract.functions.decimals.return_value.call.return_value = 18
        contract.functions.totalSupply.return_value.call.return_value = 10**21
        contract.functions.maxSupply.return_value.call.return_value = 10**24
        contract.functions.paused.return_value.call.return_value = False
        contract.functions.owner.return_value.call.return_value = "0x742d35Cc6634C0532925a3b8D2A7E1234567890A"
        contract.functions.balanceOf.return_value.call.return_value = 10**20
        mint_fn = Mock()
        mint_fn.build_transaction.return_value = {"gas": None}
        contract.functions.mint.return_value = mint_fn
        transfer_fn = Mock()
        transfer_fn.build_transaction.return_value = {"gas": None}
        contract.functions.transfer.return_value = transfer_fn
        return contract

    def test_get_token_info(self, mock_web3_client, mock_contract, temp_db):
        with (
            patch("agno.tools.startup_stock.toolkit.Web3") as mock_web3_class,
            patch("agno.tools.startup_stock.toolkit.HTTPProvider"),
        ):
            mock_web3_class.return_value = mock_web3_client
            mock_web3_class.to_checksum_address = Web3_to_checksum
            mock_web3_client.eth.contract.return_value = mock_contract

            from agno.tools.startup_stock.toolkit import StartupStockTools

            tools = StartupStockTools(
                private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                rpc_url="https://0xrpc.io/sep",
                contract_address="0x3Dfc53E3C77bb4e30Ce333Be1a66Ce62558bE395",
                cap_table_db=temp_db,
            )
            result = json.loads(tools.get_token_info())
            assert result["name"] == "Acme Startup"
            assert result["symbol"] == "ACME"

    def test_add_investor(self, mock_web3_client, mock_contract, temp_db):
        with (
            patch("agno.tools.startup_stock.toolkit.Web3") as mock_web3_class,
            patch("agno.tools.startup_stock.toolkit.HTTPProvider"),
        ):
            mock_web3_class.return_value = mock_web3_client
            mock_web3_class.to_checksum_address = Web3_to_checksum
            mock_web3_client.eth.contract.return_value = mock_contract

            from agno.tools.startup_stock.toolkit import StartupStockTools

            tools = StartupStockTools(
                private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                rpc_url="https://0xrpc.io/sep",
                contract_address="0x3Dfc53E3C77bb4e30Ce333Be1a66Ce62558bE395",
                cap_table_db=temp_db,
            )
            result = json.loads(
                tools.add_investor(
                    "Alice",
                    "0x742d35Cc6634C0532925a3b8D2A7E1234567890A",
                    1000.0,
                )
            )
            assert result["investor_name"] == "Alice"
            assert result["shares"] == 1000.0

    def test_init_requires_contract_address(self, mock_web3_client):
        with (
            patch("agno.tools.startup_stock.toolkit.Web3") as mock_web3_class,
            patch("agno.tools.startup_stock.toolkit.HTTPProvider"),
            patch.dict("os.environ", {}, clear=True),
        ):
            mock_web3_class.return_value = mock_web3_client
            from agno.tools.startup_stock.toolkit import StartupStockTools

            with pytest.raises(ValueError, match="Contract address is required"):
                StartupStockTools(
                    private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                    rpc_url="https://0xrpc.io/sep",
                )


def Web3_to_checksum(address: str) -> str:
    return address
