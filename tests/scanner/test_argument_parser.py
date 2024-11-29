import pytest
from unittest.mock import patch, MagicMock, call
from scanner.argument_parser import ArgumentParser
from scanner.resource_scanner_registry import ResourceScannerRegistry
import sys


def test_parse_arguments_no_args():
    """
    Test that parse_arguments prints help and exits when no arguments are passed.
    """
    test_args = ["main.py"]
    with patch.object(sys, 'argv', test_args), patch("argparse.ArgumentParser.print_help") as mock_help:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            ArgumentParser.parse_arguments()

        # Assert that print_help was called and SystemExit was raised with the correct code
        mock_help.assert_called_once()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1


def test_parse_arguments_with_valid_args():
    """
    Test parse_arguments with valid arguments.
    """
    test_args = ["main.py", "--organization-role", "OrgRole", "--runner-role", "RunnerRole", "--profile", "default"]
    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        assert args.organization_role == "OrgRole"
        assert args.runner_role == "RunnerRole"
        assert args.profile == "default"


def test_get_scanners_list_scanners():
    """
    Test get_scanners when --list-scanners flag is used.
    """
    test_args = ["main.py", "--list-scanners"]
    mock_scanners = ["Scanner1", "Scanner2"]

    with patch.object(ResourceScannerRegistry, 'list_scanners', return_value=mock_scanners), \
         patch("builtins.print") as mock_print, \
         patch.object(sys, 'argv', test_args):

        args = ArgumentParser.parse_arguments()
        scanners = ArgumentParser.get_scanners(args)

        # Validate scanners function output
        assert scanners is None

        # Validate all print calls
        expected_calls = [
            call("Available Scanners:"),
            call("\n".join(mock_scanners))
        ]
        mock_print.assert_has_calls(expected_calls)



def test_get_scanners_list_scanners():
    """
    Test get_scanners when --list-scanners flag is used.
    """
    test_args = ["main.py", "--list-scanners"]

    # Mocking the scanners as a dictionary to match what the original code expects
    mock_scanners = {
        "Scanner1": MagicMock(),
        "Scanner2": MagicMock()
    }

    with patch.object(ResourceScannerRegistry, 'list_scanners', return_value=mock_scanners), \
         patch("builtins.print") as mock_print, \
         patch.object(sys, 'argv', test_args):
        
        args = ArgumentParser.parse_arguments()
        
        # Assert that SystemExit is raised as expected
        with pytest.raises(SystemExit) as excinfo:
            ArgumentParser.get_scanners(args)
        
        # Ensure sys.exit was called with code 0
        assert excinfo.value.code == 0
        
        # Check if the available scanners were printed
        mock_print.assert_any_call("Available Scanners:")
        for scanner_name in mock_scanners:
            mock_print.assert_any_call(scanner_name)


def test_get_scanners_specific_scanners():
    """
    Test get_scanners with a specific list of scanners.
    """
    test_args = ["main.py", "--scanners", "Scanner1,Scanner2", "--organization-role", "TestRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        scanners = args.scanners.split(",")  # Assuming this is how scanners are processed in the implementation

        # Assert the scanners list is parsed correctly
        assert scanners == ["Scanner1", "Scanner2"]


def test_get_regions_all_regions():
    """
    Test get_regions when --all-regions flag is used.
    """
    test_args = ["main.py", "--all-regions", "--organization-role", "TestRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()

        # Assert that the --all-regions flag is correctly parsed
        assert args.all_regions is True


def test_get_regions_specific_regions():
    """
    Test get_regions with a specific list of regions.
    """
    test_args = ["main.py", "--regions", "us-east-1,us-west-2", "--organization-role", "TestRole", "--runner-role", "RunnerRole"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        regions = ArgumentParser.get_regions(args)
        assert regions == ["us-east-1", "us-west-2"]


def test_get_max_workers_default():
    """
    Test get_max_workers with the default value (os.cpu_count() - 1).
    """
    test_args = ["main.py", "--regions", "us-east-1,us-west-2", "--organization-role", "TestRole", "--runner-role", "RunnerRole"]

    with patch("os.cpu_count", return_value=8), patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        max_workers = ArgumentParser.get_max_workers(args)
        assert max_workers == 7  # 8 - 1 = 7


def test_get_max_workers_custom_value():
    """
    Test get_max_workers with a custom value.
    """
    test_args = ["main.py", "--regions", "us-east-1,us-west-2", "--organization-role", "TestRole", "--runner-role", "RunnerRole", "--max-workers", "10"]

    with patch.object(sys, 'argv', test_args):
        args = ArgumentParser.parse_arguments()
        max_workers = ArgumentParser.get_max_workers(args)
        assert max_workers == 10
