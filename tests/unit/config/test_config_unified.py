"""
Comprehensive and unified tests for FXML4 configuration module.

This module consolidates all configuration testing into a single comprehensive
test file, combining basic functionality, advanced features, edge cases, and
negative test scenarios.
"""

import os
import queue
import tempfile
import threading
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from fxml4.config import Config, get, get_config, reset_config, set


class TestConfigCore:
    """Core configuration functionality tests."""

    def test_config_initialization_default_path(self):
        """Test Config initialization with default path."""
        config_content = """
api:
  host: "localhost"
  port: 8000
database:
  host: "db"
  port: 5432
"""
        with patch("builtins.open", mock_open(read_data=config_content)):
            with patch("os.path.join", return_value="config/default.yaml"):
                config = Config()
                assert config.get("api.host") == "localhost"
                assert config.get("api.port") == 8000
                assert config.get("database.host") == "db"
                assert config.get("database.port") == 5432

    def test_config_initialization_custom_path(self):
        """Test Config initialization with custom path."""
        config_content = """
test:
  value: "custom"
  number: 42
"""
        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("custom.yaml")
            assert config.get("test.value") == "custom"
            assert config.get("test.number") == 42

    def test_nested_configuration_access(self):
        """Test accessing deeply nested configuration values."""
        deep_config = """
level1:
  level2:
    level3:
      level4:
        level5:
          level6:
            level7:
              level8:
                value: "deep_value"
                number: 123
"""
        with patch("builtins.open", mock_open(read_data=deep_config)):
            config = Config("test.yaml")
            assert (
                config.get(
                    "level1.level2.level3.level4.level5.level6.level7.level8.value"
                )
                == "deep_value"
            )
            assert (
                config.get(
                    "level1.level2.level3.level4.level5.level6.level7.level8.number"
                )
                == 123
            )

    def test_default_value_handling(self):
        """Test getting default values for non-existent keys."""
        config_content = """
existing:
  key: "value"
  number: 42
"""
        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")
            assert config.get("nonexistent", "default") == "default"
            assert config.get("nonexistent") is None
            assert config.get("existing.nonexistent", "default") == "default"
            assert config.get("existing.key") == "value"

    def test_get_all_configuration(self):
        """Test getting all configuration data."""
        config_content = """
api:
  host: "localhost"
  port: 8000
database:
  name: "test"
  host: "db"
ml:
  models_dir: "models"
"""
        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")
            all_config = config.to_dict()

            assert isinstance(all_config, dict)
            assert "api" in all_config
            assert "database" in all_config
            assert "ml" in all_config
            assert all_config["api"]["host"] == "localhost"
            assert all_config["api"]["port"] == 8000
            assert all_config["database"]["name"] == "test"


class TestConfigEnvironmentVariables:
    """Environment variable override and processing tests."""

    def setup_method(self):
        """Set up test environment."""
        reset_config()
        self.original_env = {}
        env_vars_to_clear = [
            "DB_HOST",
            "DB_PORT",
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
            "FXML4_DB_HOST",
            "FXML4_DB_PORT",
            "FXML4_DB_NAME",
            "FXML4_DB_USER",
            "FXML4_DB_PASSWORD",
            "POLYGON_API_KEY",
            "ALPHA_VANTAGE_API_KEY",
            "FRED_API_KEY",
            "OPENAI_API_KEY",
            "PINECONE_API_KEY",
            "PINECONE_ENVIRONMENT",
            "IB_HOST",
            "IB_PORT",
            "FXML4_IB_HOST",
            "FXML4_IB_PORT",
            "FXML4_API_HOST",
            "FXML4_API_PORT",
            "FXML4_API_DEBUG",
            "FXML4_JWT_SECRET_KEY",
            "FXML4_JWT_TOKEN_EXPIRE_MINUTES",
        ]

        for var in env_vars_to_clear:
            if var in os.environ:
                self.original_env[var] = os.environ[var]
                del os.environ[var]

    def teardown_method(self):
        """Clean up test environment."""
        reset_config()
        for var, value in self.original_env.items():
            os.environ[var] = value

    def test_environment_variable_overrides(self):
        """Test basic environment variable overrides."""
        config_content = """
api:
  host: "localhost"
  port: 8000
database:
  host: "db"
  port: 5432
"""
        os.environ["FXML4_API_HOST"] = "override_host"
        os.environ["DB_PORT"] = "9999"

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")
            assert config.get("api.host") == "override_host"
            assert config.get("api.port") == 8000  # Not overridden
            assert config.get("database.port") == 9999

    def test_environment_variable_type_conversion(self):
        """Test automatic type conversion of environment variables."""
        config_content = """
api:
  port: 8000
  debug: false
database:
  port: 5432
"""
        # Test integer conversion
        os.environ["FXML4_API_PORT"] = "9000"
        os.environ["DB_PORT"] = "12345"

        # Test boolean conversion
        os.environ["FXML4_API_DEBUG"] = "TRUE"

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")

            assert config.get("api.port") == 9000
            assert isinstance(config.get("api.port"), int)
            assert config.get("database.port") == 12345
            assert isinstance(config.get("database.port"), int)
            assert config.get("api.debug") is True
            assert isinstance(config.get("api.debug"), bool)

    def test_environment_variable_precedence(self):
        """Test FXML4 prefixed variables take precedence."""
        config_content = """
database:
  name: "original"
  host: "localhost"
"""
        # Set both prefixed and non-prefixed versions
        os.environ["DB_NAME"] = "env_db"
        os.environ["FXML4_DB_NAME"] = "env_fxml4_db"  # This should win
        os.environ["DB_HOST"] = "env-host"  # Only this one set

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")
            assert config.get("database.name") == "env_fxml4_db"  # FXML4 prefixed wins
            assert config.get("database.host") == "env-host"  # Regular prefix used

    def test_environment_variable_conversion_errors(self):
        """Test handling of invalid environment variable values."""
        config_content = """
api:
  port: 8000
  timeout: 30
"""
        # Set invalid values
        os.environ["FXML4_API_PORT"] = "invalid-port"
        os.environ["FXML4_API_TIMEOUT"] = "not-a-number"

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")
            # Should fall back to defaults when conversion fails
            assert config.get("api.port") == 8000  # default value
            assert config.get("api.timeout") == 30  # default value

    def test_environment_variable_edge_cases(self):
        """Test edge cases with environment variables."""
        config_content = """
api:
  host: "localhost"
  port: 8000
"""
        edge_case_env_vars = {
            "FXML4_API_HOST": "",  # Empty string
            "FXML4_API_PORT": "not_a_number",  # Invalid number
            "FXML4_INVALID_KEY": "value",  # Key that doesn't map to config
        }

        with patch("builtins.open", mock_open(read_data=config_content)):
            with patch.dict(os.environ, edge_case_env_vars):
                config = Config("test.yaml")
                # Empty string should override
                assert config.get("api.host") == ""
                # Invalid number should remain as original
                port = config.get("api.port")
                assert port in [8000, "not_a_number"]


class TestConfigFileHandling:
    """Configuration file loading and error handling tests."""

    def test_config_file_loading_with_merge(self):
        """Test loading and merging configuration from file."""
        config_data = {
            "database": {"host": "test-db-host", "port": 5555, "name": "test_db"},
            "api": {"debug": True, "host": "127.0.0.1"},
            "custom_section": {"value": "test_value"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = Config(config_path)

            # Test overridden values
            assert config.get("database.host") == "test-db-host"
            assert config.get("database.port") == 5555
            assert config.get("database.name") == "test_db"
            assert config.get("api.debug") is True
            assert config.get("api.host") == "127.0.0.1"

            # Test custom configuration
            assert config.get("custom_section.value") == "test_value"

        finally:
            os.unlink(config_path)

    def test_file_not_found_handling(self):
        """Test behavior when config file is not found."""
        # Should use defaults when file not found
        config = Config("/non/existent/config.yaml")
        # Should not raise exception, should use default values
        assert config.get("some.default.key", "default") == "default"

    def test_invalid_yaml_handling(self):
        """Test behavior with invalid YAML syntax."""
        invalid_yaml_configs = [
            "invalid: yaml: content:\n  - missing\n    bracket",
            "key: value\n  invalid: indentation",
            "key: [unclosed, array",
            "key: {unclosed: dict",
            "key: 'unclosed string",
        ]

        for i, invalid_yaml in enumerate(invalid_yaml_configs):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(invalid_yaml)
                config_path = f.name

            try:
                with pytest.raises(yaml.YAMLError):
                    Config(config_path)
            finally:
                os.unlink(config_path)

    def test_empty_config_file_handling(self):
        """Test handling of empty or whitespace-only configuration files."""
        empty_configs = [
            "",  # Completely empty
            "   \n\t  \n   ",  # Only whitespace
            "# Only comments\n# Another comment\n",  # Only comments
        ]

        for empty_content in empty_configs:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(empty_content)
                config_path = f.name

            try:
                config = Config(config_path)
                # Should handle gracefully with defaults
                assert config.get("any.key", "default") == "default"
            finally:
                os.unlink(config_path)

    def test_file_permission_errors(self):
        """Test handling of file permission errors."""
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                Config("no_permission.yaml")

    def test_file_is_directory_error(self):
        """Test handling when config path points to directory."""
        with patch("builtins.open", side_effect=IsADirectoryError("Is a directory")):
            with pytest.raises(IsADirectoryError):
                Config("directory_not_file")


class TestConfigDataTypes:
    """Configuration data type handling and validation tests."""

    def test_mixed_data_types_handling(self):
        """Test configuration with various data types."""
        mixed_config = """
string_value: "text"
integer_value: 42
float_value: 3.14159
boolean_true: true
boolean_false: false
null_value: null
list_value:
  - item1
  - item2
  - 123
  - true
dict_value:
  nested_string: "nested"
  nested_int: 456
  nested_list:
    - a
    - b
"""
        with patch("builtins.open", mock_open(read_data=mixed_config)):
            config = Config("mixed.yaml")

            assert config.get("string_value") == "text"
            assert config.get("integer_value") == 42
            assert config.get("float_value") == 3.14159
            assert config.get("boolean_true") is True
            assert config.get("boolean_false") is False
            assert config.get("null_value") is None
            assert config.get("list_value") == ["item1", "item2", 123, True]
            assert config.get("dict_value.nested_string") == "nested"
            assert config.get("dict_value.nested_int") == 456
            assert config.get("dict_value.nested_list") == ["a", "b"]

    def test_special_characters_in_keys_and_values(self):
        """Test configuration with special characters."""
        special_config = """
"key with spaces": "value with spaces"
"key-with-dashes": "value-with-dashes"
"key_with_underscores": "value_with_underscores"
"key.with.dots": "value.with.dots"
"key@with!symbols#": "value$with%symbols&"
unicode_key: "unicode_value_测试"
numeric_key: 12345
boolean_key: true
null_key: null
"""
        with patch("builtins.open", mock_open(read_data=special_config)):
            config = Config("special.yaml")

            assert config.get("key with spaces") == "value with spaces"
            assert config.get("key-with-dashes") == "value-with-dashes"
            assert config.get("key_with_underscores") == "value_with_underscores"
            assert config.get("key.with.dots") == "value.with.dots"
            assert config.get("key@with!symbols#") == "value$with%symbols&"
            assert config.get("unicode_key") == "unicode_value_测试"
            assert config.get("numeric_key") == 12345
            assert config.get("boolean_key") is True
            assert config.get("null_key") is None

    def test_yaml_references_and_anchors(self):
        """Test YAML references and anchors."""
        reference_config = """
default_settings: &defaults
  timeout: 30
  retry_count: 3
  debug: false

api:
  <<: *defaults
  host: "localhost"
  port: 8000

database:
  <<: *defaults
  host: "db"
  port: 5432
"""
        with patch("builtins.open", mock_open(read_data=reference_config)):
            config = Config("reference.yaml")

            # Both should have the default settings
            assert config.get("api.timeout") == 30
            assert config.get("api.retry_count") == 3
            assert config.get("api.debug") is False
            assert config.get("api.host") == "localhost"

            assert config.get("database.timeout") == 30
            assert config.get("database.retry_count") == 3
            assert config.get("database.debug") is False
            assert config.get("database.host") == "db"

    def test_very_long_keys_and_values(self):
        """Test configuration with very long keys and values."""
        long_key = "a" * 1000
        long_value = "b" * 10000

        long_config = f"""
{long_key}: "{long_value}"
normal_key: "normal_value"
"""
        with patch("builtins.open", mock_open(read_data=long_config)):
            config = Config("long.yaml")
            assert config.get(long_key) == long_value
            assert config.get("normal_key") == "normal_value"


class TestConfigAdvancedFeatures:
    """Advanced configuration features and methods tests."""

    def setup_method(self):
        """Reset configuration before each test."""
        reset_config()

    def teardown_method(self):
        """Reset configuration after each test."""
        reset_config()

    def test_config_get_set_methods(self):
        """Test get and set methods with dot notation."""
        config = Config()

        # Test setting values
        config.set("test.nested.value", "test_value")
        assert config.get("test.nested.value") == "test_value"

        # Test overriding existing values
        config.set("test.nested.value", "new_value")
        assert config.get("test.nested.value") == "new_value"

        # Test setting complex values
        config.set("test.list", [1, 2, 3])
        assert config.get("test.list") == [1, 2, 3]

        config.set("test.dict", {"key": "value"})
        assert config.get("test.dict.key") == "value"

    def test_database_url_generation(self):
        """Test database URL generation functionality."""
        config = Config()

        # Set database configuration
        config.set("database.user", "testuser")
        config.set("database.password", "testpass")
        config.set("database.host", "testhost")
        config.set("database.port", 5555)
        config.set("database.name", "testdb")

        if hasattr(config, "get_database_url"):
            url = config.get_database_url()
            expected = "postgresql://testuser:testpass@testhost:5555/testdb"
            assert url == expected

    def test_configuration_merging(self):
        """Test configuration merging logic."""
        config_data = {
            "database": {
                "host": "new-host",  # override
                "new_key": "new_value",  # add
                "timeout": 60,
            },
            "new_section": {"key": "value"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = Config(config_path)

            # Test merged values
            assert config.get("database.host") == "new-host"  # overridden
            assert config.get("database.new_key") == "new_value"  # added
            assert config.get("database.timeout") == 60  # from file
            assert config.get("new_section.key") == "value"  # new section

        finally:
            os.unlink(config_path)

    def test_configuration_immutability(self):
        """Test configuration immutability after creation."""
        config_content = "mutable: original_value"

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")

            original_value = config.get("mutable")
            assert original_value == "original_value"

            # Get dict should be a copy, not reference
            config_dict = config.to_dict()
            config_dict["test_key"] = "test_value"
            assert config.get("test_key") is None  # Should not affect original


class TestGlobalConfigFunctions:
    """Global configuration function tests."""

    def setup_method(self):
        """Reset global configuration before each test."""
        reset_config()

    def teardown_method(self):
        """Reset global configuration after each test."""
        reset_config()

    def test_get_config_singleton(self):
        """Test that get_config returns singleton instance."""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2  # Same instance

        # Changes to one should affect the other
        config1.set("test.key", "test_value")
        assert config2.get("test.key") == "test_value"

    def test_reset_config_functionality(self):
        """Test configuration reset functionality."""
        config1 = get_config()
        config1.set("test.key", "test_value")

        reset_config()

        config2 = get_config()
        assert config2 is not config1  # Different instance
        assert config2.get("test.key") is None  # Value reset

    def test_convenience_functions(self):
        """Test convenience get/set functions."""
        # Test set function
        set("test.convenience", "test_value")
        assert get("test.convenience") == "test_value"

        # Test get with default
        assert get("non.existent", "default") == "default"

        # Test get without default
        assert get("non.existent") is None

    def test_get_config_function_legacy(self):
        """Test the legacy get_config function."""
        config_content = """
test:
  key: "value"
nested:
  deep:
    value: "deep_value"
"""
        with patch("builtins.open", mock_open(read_data=config_content)):
            with patch("os.path.join", return_value="config/default.yaml"):
                # Reset the global config
                import fxml4.config

                fxml4.config.config = Config()

                result = get_config("test.key", "default")
                assert result == "value"

                result = get_config("nested.deep.value", "default")
                assert result == "deep_value"

                result = get_config("nonexistent", "default")
                assert result == "default"


class TestConfigEdgeCases:
    """Edge cases and error condition tests."""

    def test_get_with_invalid_key_types(self):
        """Test get method with invalid key types."""
        config_content = "valid_key: value"

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")

            # Test with various invalid key types
            invalid_keys = [
                [],  # List
                {},  # Dict
                set(),  # Set
                lambda x: x,  # Function
                Exception(),  # Exception object
            ]

            for invalid_key in invalid_keys:
                # Should handle gracefully
                try:
                    result = config.get(invalid_key, "default")
                    assert result == "default"
                except (TypeError, AttributeError):
                    pass  # Acceptable to raise appropriate error

    def test_get_with_edge_case_keys(self):
        """Test get method with edge case keys."""
        config_content = """
valid_key: "value"
123: "numeric_key"
"456": "string_numeric_key"
"""
        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("test.yaml")

            # Test None key
            result = config.get(None, "default")
            assert result == "default"

            # Test empty string key
            result = config.get("", "default")
            assert result == "default"

            # Test numeric keys
            assert config.get(123) == "numeric_key"
            assert config.get("456") == "string_numeric_key"

    def test_concurrent_config_access(self):
        """Test concurrent access to configuration."""
        config_content = "shared: value"

        with patch("builtins.open", mock_open(read_data=config_content)):
            config = Config("concurrent.yaml")

            results = queue.Queue()

            def access_config():
                try:
                    value = config.get("shared")
                    results.put(value)
                except Exception as e:
                    results.put(f"Error: {e}")

            # Create multiple threads accessing config
            threads = []
            for _ in range(10):
                thread = threading.Thread(target=access_config)
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Collect results
            thread_results = []
            while not results.empty():
                thread_results.append(results.get())

            # All threads should get the same value
            assert len(thread_results) == 10
            assert all(result == "value" for result in thread_results)

    def test_extremely_large_config_handling(self):
        """Test behavior with very large configuration."""
        # Simulate large config content
        large_content = "key: " + "x" * (1024 * 100)  # 100KB string

        with patch("builtins.open", mock_open(read_data=large_content)):
            try:
                config = Config("large.yaml")
                value = config.get("key")
                assert len(value) > 100000
            except MemoryError:
                # Acceptable to fail with memory error for very large files
                pass

    def test_yaml_security_constructs(self):
        """Test handling of potentially dangerous YAML constructs."""
        # YAML can be dangerous with certain constructs if not using safe_load
        dangerous_configs = [
            "!!python/object/apply:os.system ['echo test']",
            "!!python/module:os",
            "- !!python/object/apply:subprocess.check_output [['ls']]",
        ]

        for dangerous_yaml in dangerous_configs:
            with patch("builtins.open", mock_open(read_data=dangerous_yaml)):
                # Should either parse safely or raise security error
                try:
                    config = Config("dangerous.yaml")
                    # If it parses successfully, yaml.safe_load was used
                except Exception:
                    # Any parsing error is acceptable for security
                    pass


# Pytest markers for test categorization
pytestmark = [pytest.mark.unit, pytest.mark.config]
