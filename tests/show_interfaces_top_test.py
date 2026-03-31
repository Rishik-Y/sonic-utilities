import json
from unittest import mock

from click.testing import CliRunner

import show.main as show
from show.interfaces import top as top_module


def test_portstat_layer():
    ratestat_dict = {
        "Ethernet0": mock.Mock(rx_bps=1000000.0, tx_bps=2000000.0),
        "Ethernet4": mock.Mock(rx_bps=3000000.0, tx_bps=4000000.0),
    }

    with mock.patch("show.interfaces.top.Portstat") as mock_portstat_cls:
        mock_portstat = mock_portstat_cls.return_value
        mock_portstat.get_cnstat_dict.return_value = ({"time": "now"}, ratestat_dict)

        result = top_module.fetch_interface_rates(namespace=None, display_option="all")

    assert result == {
        "Ethernet0": {"rx_bps": 1000000.0, "tx_bps": 2000000.0},
        "Ethernet4": {"rx_bps": 3000000.0, "tx_bps": 4000000.0},
    }
    mock_portstat_cls.assert_called_once_with(None, "all")


def test_ranking_logic():
    port_rates = {
        "Ethernet0": {"rx_bps": 3_000_000.0, "tx_bps": 1_000_000.0},
        "Ethernet4": {"rx_bps": 2_000_000.0, "tx_bps": 6_000_000.0},
        "Ethernet8": {"rx_bps": 2_500_000.0, "tx_bps": 2_500_000.0},
    }

    ranked = top_module.rank_interfaces_by_traffic(port_rates, 2)

    assert ranked == [
        {
            "interface": "Ethernet4",
            "rx_mbps": 2.0,
            "tx_mbps": 6.0,
            "total_mbps": 8.0,
            "rank": 1,
        },
        {
            "interface": "Ethernet8",
            "rx_mbps": 2.5,
            "tx_mbps": 2.5,
            "total_mbps": 5.0,
            "rank": 2,
        },
    ]


def test_top_default():
    sample_rates = {
        "Ethernet0": {"rx_bps": 10_000_000, "tx_bps": 5_000_000},
        "Ethernet1": {"rx_bps": 9_000_000, "tx_bps": 5_000_000},
        "Ethernet2": {"rx_bps": 8_000_000, "tx_bps": 5_000_000},
        "Ethernet3": {"rx_bps": 7_000_000, "tx_bps": 5_000_000},
        "Ethernet4": {"rx_bps": 6_000_000, "tx_bps": 5_000_000},
        "Ethernet5": {"rx_bps": 5_000_000, "tx_bps": 5_000_000},
    }

    runner = CliRunner()
    with mock.patch("show.interfaces.top.fetch_interface_rates", return_value=sample_rates), \
         mock.patch("show.interfaces.top.time.sleep", return_value=None):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], [])

    assert result.exit_code == 0
    data_lines = [line for line in result.output.splitlines() if line.strip() and line.strip()[0].isdigit()]
    assert len(data_lines) == 5


def test_top_count_3():
    sample_rates = {
        "Ethernet0": {"rx_bps": 10_000_000, "tx_bps": 5_000_000},
        "Ethernet1": {"rx_bps": 9_000_000, "tx_bps": 5_000_000},
        "Ethernet2": {"rx_bps": 8_000_000, "tx_bps": 5_000_000},
        "Ethernet3": {"rx_bps": 7_000_000, "tx_bps": 5_000_000},
    }

    runner = CliRunner()
    with mock.patch("show.interfaces.top.fetch_interface_rates", return_value=sample_rates), \
         mock.patch("show.interfaces.top.time.sleep", return_value=None):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], ["--count", "3"])

    assert result.exit_code == 0
    data_lines = [line for line in result.output.splitlines() if line.strip() and line.strip()[0].isdigit()]
    assert len(data_lines) == 3


def test_top_json_output():
    sample_rates = {
        "Ethernet0": {"rx_bps": 10_000_000, "tx_bps": 5_000_000},
        "Ethernet1": {"rx_bps": 9_000_000, "tx_bps": 5_000_000},
    }

    runner = CliRunner()
    with mock.patch("show.interfaces.top.fetch_interface_rates", return_value=sample_rates), \
         mock.patch("show.interfaces.top.time.sleep", return_value=None):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], ["--json", "--count", "2", "--interval", "2"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "timestamp" in payload
    assert "interval_seconds" in payload
    assert payload["interval_seconds"] == 2.0
    assert "top_interfaces" in payload
    assert len(payload["top_interfaces"]) == 2
    assert payload["top_interfaces"][0]["rank"] == 1


def test_top_empty_counters():
    runner = CliRunner()
    with mock.patch("show.interfaces.top.fetch_interface_rates", return_value={}), \
         mock.patch("show.interfaces.top.time.sleep", return_value=None):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], [])

    assert result.exit_code == 0
    data_lines = [line for line in result.output.splitlines() if line.strip() and line.strip()[0].isdigit()]
    assert len(data_lines) == 0


def test_top_portstat_error():
    runner = CliRunner(mix_stderr=True)
    with mock.patch("show.interfaces.top.fetch_interface_rates", side_effect=Exception("DB connection failed")), \
         mock.patch("show.interfaces.top.time.sleep", return_value=None):
        result = runner.invoke(show.cli.commands["interfaces"].commands["top"], [])

    assert result.exit_code == 1
    assert "Error fetching interface rates: DB connection failed" in result.output
