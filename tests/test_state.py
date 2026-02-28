"""Tests for core.state — StateManager persistence and crash recovery."""

import json
import os

from core.state import StateManager


class TestStateManagerInit:
    def test_creates_default_state(self, tmp_state_file):
        sm = StateManager(tmp_state_file)
        assert sm.get_token() is None
        assert sm.get_total() == 0
        assert dict(sm.get_history()) == {}
        assert sm.get_last_run() is None
        assert sm.get_provider() is None

    def test_loads_existing_file(self, populated_state):
        assert populated_state.get_token() == "TOKEN123"
        assert populated_state.get_total() == 42
        assert populated_state.get_provider() == "gmail"

    def test_corrupted_file_returns_defaults(self, tmp_path):
        path = str(tmp_path / "corrupt.json")
        with open(path, "w") as f:
            f.write("NOT VALID JSON {{{")
        sm = StateManager(path)
        assert sm.get_token() is None
        assert sm.get_total() == 0

    def test_missing_file_returns_defaults(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        sm = StateManager(path)
        assert sm.get_token() is None


class TestStateManagerSave:
    def test_save_creates_file(self, tmp_state_file):
        sm = StateManager(tmp_state_file)
        sm.save(
            page_token="abc123",
            processed_count=10,
            history={"Dev/GitHub": 5, "Misc/Other": 5},
            provider="gmail",
        )
        assert os.path.exists(tmp_state_file)
        with open(tmp_state_file) as f:
            data = json.load(f)
        assert data["next_page_token"] == "abc123"
        assert data["total_processed"] == 10
        assert data["provider"] == "gmail"
        assert data["last_run"] is not None

    def test_save_updates_state(self, state_manager):
        state_manager.save("t1", 5, {"A": 3}, "imap")
        assert state_manager.get_token() == "t1"
        assert state_manager.get_total() == 5
        assert state_manager.get_provider() == "imap"

    def test_save_without_provider(self, state_manager):
        state_manager.save("t1", 1, {})
        assert state_manager.get_provider() is None

    def test_save_persists_across_instances(self, tmp_state_file):
        sm1 = StateManager(tmp_state_file)
        sm1.save("TOKEN_A", 100, {"Label": 50}, "outlook")

        sm2 = StateManager(tmp_state_file)
        assert sm2.get_token() == "TOKEN_A"
        assert sm2.get_total() == 100
        assert sm2.get_history()["Label"] == 50


class TestStateManagerHistory:
    def test_history_returns_defaultdict(self, populated_state):
        history = populated_state.get_history()
        assert history["Dev/GitHub"] == 10
        # Unknown keys return 0 (defaultdict behavior)
        assert history["NonExistent"] == 0

    def test_save_converts_defaultdict(self, state_manager):
        from collections import defaultdict
        dd = defaultdict(int, {"A": 1, "B": 2})
        state_manager.save(None, 3, dd)
        with open(state_manager.filename) as f:
            data = json.load(f)
        assert isinstance(data["history"], dict)
        assert data["history"]["A"] == 1


class TestStateManagerClear:
    def test_clear_resets_to_defaults(self, populated_state):
        populated_state.clear()
        assert populated_state.get_token() is None
        assert populated_state.get_total() == 0
        assert populated_state.get_last_run() is None

    def test_clear_removes_file(self, tmp_state_file):
        sm = StateManager(tmp_state_file)
        sm.save("token", 1, {})
        assert os.path.exists(tmp_state_file)
        sm.clear()
        assert not os.path.exists(tmp_state_file)

    def test_clear_nonexistent_file_no_error(self, tmp_path):
        path = str(tmp_path / "doesnt_exist.json")
        sm = StateManager(path)
        sm.clear()  # Should not raise


class TestStateManagerResumable:
    def test_not_resumable_by_default(self, state_manager):
        assert state_manager.is_resumable() is False

    def test_resumable_when_token_set(self, state_manager):
        state_manager.save("token", 5, {})
        assert state_manager.is_resumable() is True

    def test_not_resumable_after_complete(self, state_manager):
        state_manager.save(None, 100, {})
        assert state_manager.is_resumable() is False
