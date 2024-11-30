# test_report_generator.py
import pytest
from unittest.mock import patch, mock_open, MagicMock
import os
from datetime import datetime
import pytz
from tests.reports.html.test_report_generator import *

@pytest.fixture
def mock_directories():
    return "/fake/path/templates", "/fake/path/assets"

@pytest.fixture
def sample_scan_results():
    return [{
        "account_id": "123456789012",
        "account_name": "Test Account",
        "regions": ["us-east-1", "Global"],
        "scan_results": {
            "us-east-1": {
                "ec2": [{
                    "ResourceName": "test-instance",
                    "ResourceId": "i-1234",
                    "Reason": "No activity",
                    "Cost": {"EC2 Instances": {
                        "hourly": 0.5,
                        "daily": 12,
                        "monthly": 360,
                        "yearly": 4320,
                        "lifetime": "N/A"
                    }}
                }]
            }
        }
    }]

@pytest.fixture
def sample_scan_metrics():
    return {
        "total_run_time": 3665,  # 1 hour, 1 minute, 5 seconds
        "start_time": 1677666000
    }

def test_get_directories():
    with patch('os.path') as mock_path:
        mock_path.dirname.return_value = "/fake/path"
        mock_path.join.side_effect = lambda *args: "/".join(args)
        mock_path.exists.return_value = True
        
        template_dir, asset_dir = get_directories()
        
        assert "templates" in template_dir
        assert "assets" in asset_dir

def test_get_directories_missing_template():
    with patch('os.path') as mock_path:
        mock_path.dirname.return_value = "/fake/path"
        mock_path.join.side_effect = lambda *args: "/".join(args)
        mock_path.exists.side_effect = [False, True]
        
        with pytest.raises(FileNotFoundError):
            get_directories()

def test_load_asset():
    content = "test content"
    with patch('builtins.open', mock_open(read_data=content)):
        result = load_asset("fake/path")
        assert result == content

def test_calculate_duration():
    test_cases = [
        (3665, "1 hour(s) 1 minute(s)"),
        (86500, "1 day(s) 0 hour(s)"),
        (45, "45 second(s)"),
    ]
    
    for seconds, expected in test_cases:
        duration, duration_str = calculate_duration(seconds)
        assert duration_str == expected

def test_calculate_totals():
    costs = {
        "EC2": {
            "hourly": 1.0,
            "daily": 24.0,
            "monthly": 720.0,
            "yearly": 8760.0,
            "lifetime": 1000.0
        },
        "RDS": {
            "hourly": 2.0,
            "daily": 48.0,
            "monthly": 1440.0,
            "yearly": 17520.0,
            "lifetime": "N/A"
        }
    }
    
    result = calculate_totals(costs)
    assert "Totals" in result
    assert result["Totals"]["hourly"] == 3.0

def test_format_report_time():
    timestamp = 1677666000
    formatted = format_report_time(timestamp)
    assert isinstance(formatted, str)
    assert "2023" in formatted

@patch('report_generator.ResourceScannerRegistry')
def test_extract_scan_data(mock_registry, sample_scan_results):
    mock_scanner = MagicMock()
    mock_scanner.label = "EC2 Instances"
    mock_registry.get_scanner.return_value = mock_scanner
    
    accounts_regions, type_counts, resources, costs = extract_scan_data(sample_scan_results)
    
    assert isinstance(accounts_regions, dict)
    assert isinstance(type_counts, dict)
    assert isinstance(resources, list)
    assert isinstance(costs, dict)

def test_format_resource_details():
    test_cases = [
        ({"key": "value"}, "key: value"),
        (["item1", "item2"], "item1\nitem2"),
        ("plain text", "plain text")
    ]
    
    for input_data, expected in test_cases:
        result = format_resource_details(input_data)
        assert expected in result

@patch('report_generator.Environment')
def test_render_html(mock_env):
    mock_template = MagicMock()
    mock_env.return_value.get_template.return_value = mock_template
    mock_template.render.return_value = "<html>test</html>"
    
    result = render_html("/fake/path", "template.j2", {"key": "value"})
    assert result == "<html>test</html>"

def test_save_html():
    content = "<html>test</html>"
    mo = mock_open()
    with patch('builtins.open', mo):
        save_html(content, "test.html")
    mo.assert_called_once_with("test.html", 'w')

@patch('report_generator.get_directories')
@patch('report_generator.extract_scan_data')
@patch('report_generator.load_asset')
@patch('report_generator.render_html')
@patch('report_generator.save_html')
def test_generate_html_report(
    mock_save,
    mock_render,
    mock_load_asset,
    mock_extract,
    mock_get_dirs,
    sample_scan_results,
    sample_scan_metrics
):
    mock_get_dirs.return_value = ("/templates", "/assets")
    mock_extract.return_value = ({}, {}, [], {})
    mock_load_asset.return_value = ""
    mock_render.return_value = "<html>test</html>"
    
    result = generate_html_report(sample_scan_results, 1677666000, sample_scan_metrics)
    
    assert isinstance(result, str)
    mock_save.assert_called_once()
    mock_render.assert_called_once()