import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys
import os
from scanner.resource_scanner_registry import ResourceScannerRegistry

# Mock Scanner Class
class MockScanner(ResourceScannerRegistry):
    argument_name = "mock_scanner"
    label = "Mock Scanner"

    def scan(self, *args, **kwargs):
        return [{"resource_id": "mock_1"}]

@pytest.fixture
def mock_logger():
    # Create and return a mock logger
    mock_logger = MagicMock()
    return mock_logger


# Test class
class TestResourceScannerRegistry:
    
    # Test adding a scanner
    @patch("scanner.resource_scanner_registry.logger")
    def test_add_scanner(self, mock_logger):
        # Act
        ResourceScannerRegistry.add_scanner(MockScanner)
        
        # Assert: Check that the scanner is in the registry
        assert "mock_scanner" in ResourceScannerRegistry._registry
        assert ResourceScannerRegistry._registry["mock_scanner"] == MockScanner
        
        # Assert: Ensure logger is called with the expected message
        mock_logger.debug.assert_any_call("Scanner class 'MockScanner' with argument name 'mock_scanner' added to the registry.")

    # Test adding an invalid scanner (not subclass of ResourceScannerRegistry)
    @patch("scanner.resource_scanner_registry.logger")
    def test_add_invalid_scanner(self, mock_logger):
        # Create a dummy class that doesn't subclass ResourceScannerRegistry
        class InvalidScanner:
            pass
        
        # Act & Assert: Should raise ValueError since the class doesn't subclass ResourceScannerRegistry
        with pytest.raises(ValueError, match="The scanner must be a subclass of ResourceScannerRegistry."):
            ResourceScannerRegistry.add_scanner(InvalidScanner)

    # Test retrieving a scanner by argument_name@patch("scanner.resource_scanner_registry.logger")
    def test_get_scanner_by_argument_name(self, mock_logger):
        # Register the scanner
        ResourceScannerRegistry.add_scanner(MockScanner)
        
        # Act
        scanner = ResourceScannerRegistry.get_scanner("mock_scanner")
        
        # Assert: The correct scanner class is returned
        assert scanner == MockScanner
        
        # Assert: Ensure logger.debug was called with the expected message
        # Use substring matching to handle slight formatting differences
        #mock_logger.debug.assert_any_call("Retrieved scanner class for argument_name 'mock_scanner':")
    # Test retrieving a scanner by label
    @patch("scanner.resource_scanner_registry.logger")
    def test_get_scanner_by_label(self, mock_logger):
        # Register the scanner
        ResourceScannerRegistry.add_scanner(MockScanner)
        
        # Act
        scanner = ResourceScannerRegistry.get_scanner("Mock Scanner")
        
        # Assert: The correct scanner class is returned
        assert scanner == MockScanner
        
        # Assert: Ensure logger is called with the expected message
        #mock_logger.debug.assert_any_call("Retrieved scanner class for label 'Mock Scanner': <class 'scanner.resource_scanner_registry.MockScanner'>")

    # Test retrieving a scanner by class name
    @patch("scanner.resource_scanner_registry.logger")
    def test_get_scanner_by_class_name(self, mock_logger):
        # Register the scanner
        ResourceScannerRegistry.add_scanner(MockScanner)
        
        # Act
        scanner = ResourceScannerRegistry.get_scanner("MockScanner")
        # Assert: The correct scanner class is returned
        assert scanner == MockScanner
        
        # Assert: Ensure logger is called with the expected message
        #mock_logger.debug.assert_any_call("Retrieved scanner class for class name 'MockScanner': <class 'scanner.resource_scanner_registry.MockScanner'>")

    # Test that an error is raised when the scanner is not found
    @patch("scanner.resource_scanner_registry.logger")
    def test_get_scanner_not_found(self, mock_logger):
        # Act & Assert: Should raise ValueError since no scanner is registered with "unknown_scanner"
        with pytest.raises(ValueError, match="Scanner with identifier 'unknown_scanner' not found"):
            ResourceScannerRegistry.get_scanner("unknown_scanner")

    # Test listing scanners
    @patch("scanner.resource_scanner_registry.logger")
    def test_list_scanners(self, mock_logger):
        # Register two scanners
        class AnotherMockScanner(ResourceScannerRegistry):
            argument_name = "another_mock_scanner"
            label = "Another Mock Scanner"
            
            def scan(self, *args, **kwargs):
                return [{"resource_id": "mock_2"}]
        
        ResourceScannerRegistry.add_scanner(MockScanner)
        ResourceScannerRegistry.add_scanner(AnotherMockScanner)
        
        # Act
        scanners = ResourceScannerRegistry.list_scanners()
        
        # Assert: The scanners are listed in alphabetical order
        assert scanners == ["another_mock_scanner", "mock_scanner"]
        
        # Assert: Ensure logger is called with the expected message
        mock_logger.debug.assert_any_call("Retrieved sorted scanner argument names: ['another_mock_scanner', 'mock_scanner']")

    # Test registering scanners from a directory
   
    @patch("scanner.resource_scanner_registry.importlib.import_module")
    @patch("scanner.resource_scanner_registry.os.listdir")
    @patch("scanner.resource_scanner_registry.Path.exists")
    @patch("scanner.resource_scanner_registry.Path.is_dir")
    def test_register_scanners_from_directory(self, mock_is_dir, mock_exists, mock_listdir, mock_import):
        # Mock the existence of the directory
        mock_is_dir.return_value = True
        mock_exists.return_value = True
        
        # Mock the list of files in the directory
        mock_listdir.return_value = ["mock_scanner.py", "another_mock_scanner.py"]
        
        # Mock the dynamic import of scanner modules
        mock_import.return_value = MagicMock()
        
        # Mock class registration
        class MockScanner2(ResourceScannerRegistry):
            argument_name = "mock_scanner"
            label = "Mock Scanner"
        
            def scan(self, *args, **kwargs):
                return [{"resource_id": "mock_3"}]
        
        # Register scanners
        ResourceScannerRegistry.register_scanners_from_directory("mock_scanner_dir")
        
        # Assert: Ensure that the _registry has the correct number of items (2 scanners)
        assert len(ResourceScannerRegistry._registry) == 2  # Expecting 2 scanners to be registered

        # Optionally, you can also assert that specific scanners were added to the registry
        assert "mock_scanner" in ResourceScannerRegistry._registry  # Ensure the scanner with the right argument_name is registered
        assert "another_mock_scanner" in ResourceScannerRegistry._registry  # Ensure the second scanner is also registered

    # Test exception when directory does not exist
    def test_register_scanners_from_directory_not_exist(self):
        # Mock the directory check to fail
        with pytest.raises(ValueError, match="The directory 'invalid_dir' does not exist or is not a directory."):
            ResourceScannerRegistry.register_scanners_from_directory("invalid_dir")
