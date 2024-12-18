import pytest
from unittest.mock import patch, MagicMock, call
from scanner.argument_parser import ArgumentParser
from scanner.resource_scanner_registry import ResourceScannerRegistry
import sys
import os

# Test parsing valid arguments
def test_parse_arguments_with_valid_args():
    test_args = ["main.py", "--organization-role", "OrgRole", "--runner-role", "RunnerRole"]
    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        assert args.organization_role == "OrgRole"
        assert args.runner_role == "RunnerRole"


# Test the list scanners functionality
def test_get_scanners_list_scanners():
    """
    Test get_scanners when --list-scanners flag is used.
    """
    test_args = ["main.py", "--list-scanners"]
    mock_scanners = ["Scanner1", "Scanner2"]

    with patch.object(ResourceScannerRegistry, 'list_scanners', return_value=mock_scanners), \
         patch("builtins.print") as mock_print, \
         patch.object(sys, 'argv', test_args), \
         patch("sys.exit") as mock_exit:  # Mock sys.exit to prevent exiting

        args = ArgumentParser.parse_arguments()
        ArgumentParser.get_scanners(args)

        # Ensure sys.exit(0) was called after listing scanners
        mock_exit.assert_called_once_with(0)


# Test when the --all-scanners flag is used
def test_get_scanners_all_scanners():
    test_args = ["main.py", "--scanners", "all", "--organization-role", "TestRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        assert args.scanners == "all"


# Test when specific scanners are provided via arguments
def test_get_scanners_specific_scanners():
    test_args = ["main.py", "--scanners", "Scanner1,Scanner2", "--organization-role", "TestRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        scanners = args.scanners.split(",")
        assert scanners == ["Scanner1", "Scanner2"]


# Test getting scanners when the CS_SCANNERS environment variable is set
def test_get_scanners_env_var():
    os.environ["CS_SCANNERS"] = "Scanner1,Scanner2"
    
    test_args = ["main.py", "--organization-role", "TestRole", "--runner-role", "ScannerRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()

        # Assert that the environment variable value was used
        assert args.scanners == "Scanner1,Scanner2"

    # Clean up environment variable after test
    del os.environ["CS_SCANNERS"]


# Test getting regions when the --all-regions flag is used
def test_get_regions_all_regions():
    test_args = ["main.py",  "--organization-role", "TestRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        assert args.regions == "all"


# Test getting regions when specific regions are provided
def test_get_regions_specific_regions():
    test_args = ["main.py", "--regions", "us-east-1,us-west-2", "--organization-role", "TestRole", "--runner-role", "RunnerRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        regions = ArgumentParser.get_regions(args)
        assert regions == ["us-east-1", "us-west-2"]


# Test when the CS_REGIONS environment variable is set
def test_get_regions_env_var():
    os.environ["CS_REGIONS"] = "us-east-1,us-west-2"

    test_args = ["main.py", "--organization-role", "TestRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        regions = ArgumentParser.get_regions(args)

        # Assert that the environment variable value was used
        assert regions == ["us-east-1", "us-west-2"]

    # Clean up environment variable after test
    del os.environ["CS_REGIONS"]


# Test getting days-threshold with environment variable logic
def test_get_days_threshold_env_var():
    os.environ["CS_DAYS_THRESHOLD"] = "120"

    test_args = ["main.py", "--organization-role", "TestRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        assert args.days_threshold == 120

    # Clean up environment variable after test
    del os.environ["CS_DAYS_THRESHOLD"]


# Test the max workers functionality with default value
def test_get_max_workers_default():
    test_args = ["main.py", "--regions", "us-east-1,us-west-2", "--organization-role", "TestRole", "--runner-role", "RunnerRole"]

    with patch("os.cpu_count", return_value=8), patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        max_workers = ArgumentParser.get_max_workers(args)
        assert max_workers == 7  # 8 - 1 = 7


# Test the max workers functionality with a custom value
def test_get_max_workers_custom_value():
    test_args = ["main.py", "--regions", "us-east-1,us-west-2", "--organization-role", "TestRole", "--runner-role", "RunnerRole", "--max-workers", "10"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        max_workers = ArgumentParser.get_max_workers(args)
        assert max_workers == 10
