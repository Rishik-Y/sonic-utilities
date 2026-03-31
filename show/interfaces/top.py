import json
import time
from datetime import datetime, timezone

import click
from tabulate import tabulate

import utilities_common.multi_asic as multi_asic_util
from utilities_common.portstat import Portstat


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fetch_interface_rates(namespace, display_option):
    portstat = Portstat(namespace, display_option)
    _, ratestat_dict = portstat.get_cnstat_dict()

    rates = {}
    for port_name, stat in ratestat_dict.items():
        rates[port_name] = {
            "rx_bps": _safe_float(stat.rx_bps),
            "tx_bps": _safe_float(stat.tx_bps),
        }
    return rates


def rank_interfaces_by_traffic(port_rates, count):
    ranked = []
    for interface, rates in port_rates.items():
        rx_bps = _safe_float(rates.get("rx_bps"))
        tx_bps = _safe_float(rates.get("tx_bps"))
        total_bps = rx_bps + tx_bps
        ranked.append({
            "interface": interface,
            "rx_mbps": rx_bps / 1_000_000,
            "tx_mbps": tx_bps / 1_000_000,
            "total_mbps": total_bps / 1_000_000,
        })

    ranked.sort(key=lambda entry: (-entry["total_mbps"], entry["interface"]))
    top_n = ranked[:count]

    for index, row in enumerate(top_n, start=1):
        row["rank"] = index

    return top_n


@click.command(name="top")
@multi_asic_util.multi_asic_click_options
@click.option("--count", type=click.IntRange(min=1), default=5, show_default=True, help="Number of top interfaces")
@click.option("--interval", type=click.IntRange(min=0), default=1, show_default=True, help="Sampling interval in seconds")
@click.option("--json", "json_fmt", is_flag=True, help="Print in JSON format")
def top(namespace, display, count, interval, json_fmt):
    """Show top N interfaces by traffic (RX + TX).

    The command reads interface rate counters for the selected namespace/display
    scope, ranks interfaces by total throughput, and prints table or JSON output.
    """

    rates = fetch_interface_rates(namespace, display)
    if interval > 0:
        time.sleep(interval)
        rates = fetch_interface_rates(namespace, display)

    top_interfaces = rank_interfaces_by_traffic(rates, count)

    if json_fmt:
        click.echo(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "top_interfaces": top_interfaces
        }))
        return

    headers = ["Rank", "Interface", "RX (Mbps)", "TX (Mbps)", "Total (Mbps)"]
    rows = []
    for row in top_interfaces:
        rows.append([
            row["rank"],
            row["interface"],
            f"{row['rx_mbps']:.2f}",
            f"{row['tx_mbps']:.2f}",
            f"{row['total_mbps']:.2f}",
        ])

    click.echo(tabulate(rows, headers=headers))
