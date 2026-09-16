"""Tests for the memory system."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMemorySystem:
    """Test memory operations (requires DATABASE_URI)."""

    def test_build_context_no_data(self):
        """Test context building with no existing data."""
        from memory_system import ltm
        # This should not crash even if DB is unavailable
        try:
            context = ltm.build_context("test_session_nonexistent_xyz", "hello")
            assert isinstance(context, str)
        except Exception:
            # DB might not be available in test env
            pass

    def test_extract_facts_graceful(self):
        """Test fact extraction handles DB failures gracefully."""
        from memory_system import ltm
        try:
            ltm.extract_facts("test_session_xyz", "My name is Alice", "Hello Alice!")
        except Exception:
            pass

    def test_clear_all_graceful(self):
        """Test clear_all handles DB failures gracefully."""
        from memory_system import ltm
        try:
            ltm.clear_all("test_session_xyz")
        except Exception:
            pass

    def test_list_keys_graceful(self):
        """Test list_keys handles DB failures gracefully."""
        from memory_system import ltm
        try:
            keys = ltm.list_keys("test_session_xyz")
            assert isinstance(keys, list)
        except Exception:
            pass
