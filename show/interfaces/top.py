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


def fetch_interface_rates(namespace, display_option, interval=1):
    try:
        portstat = Portstat(namespace, display_option)
        cnstat_dict_1, _ = portstat.get_cnstat_dict()
        if interval > 0:
            time.sleep(interval)
            cnstat_dict_2, _ = portstat.get_cnstat_dict()
        else:
            cnstat_dict_2 = cnstat_dict_1
    except Exception as e:
        raise click.ClickException(f"Error fetching interface rates: {e}") from e

    rates = {}
    for port_name in set(cnstat_dict_1.keys()) & set(cnstat_dict_2.keys()):
        stat_1 = cnstat_dict_1.get(port_name)
        stat_2 = cnstat_dict_2.get(port_name)
        if not hasattr(stat_1, "get") and not hasattr(stat_1, "rx_byt"):
            continue
        if not hasattr(stat_2, "get") and not hasattr(stat_2, "rx_byt"):
            continue

        if hasattr(stat_1, "get"):
            sample1_rx_byt = _safe_float(stat_1.get("rx_byt"))
            sample1_tx_byt = _safe_float(stat_1.get("tx_byt"))
        else:
            sample1_rx_byt = _safe_float(getattr(stat_1, "rx_byt", 0.0))
            sample1_tx_byt = _safe_float(getattr(stat_1, "tx_byt", 0.0))

        if hasattr(stat_2, "get"):
            sample2_rx_byt = _safe_float(stat_2.get("rx_byt"))
            sample2_tx_byt = _safe_float(stat_2.get("tx_byt"))
        else:
            sample2_rx_byt = _safe_float(getattr(stat_2, "rx_byt", 0.0))
            sample2_tx_byt = _safe_float(getattr(stat_2, "tx_byt", 0.0))

        if interval > 0:
            rx_mbps = max(0.0, sample2_rx_byt - sample1_rx_byt) * 8 / interval / 1_000_000
            tx_mbps = max(0.0, sample2_tx_byt - sample1_tx_byt) * 8 / interval / 1_000_000
        else:
            rx_mbps = 0.0
            tx_mbps = 0.0

        rates[port_name] = {"rx_mbps": rx_mbps, "tx_mbps": tx_mbps}
    return rates


def rank_interfaces_by_traffic(port_rates, count):
    ranked = []
    for interface, rates in port_rates.items():
        rx_mbps = _safe_float(rates.get("rx_mbps"))
        tx_mbps = _safe_float(rates.get("tx_mbps"))
        total_mbps = rx_mbps + tx_mbps
        ranked.append({
            "interface": interface,
            "rx_mbps": rx_mbps,
            "tx_mbps": tx_mbps,
            "total_mbps": total_mbps,
        })

    ranked.sort(key=lambda entry: (-entry["total_mbps"], entry["interface"]))
    top_n = ranked[:count]

    for index, row in enumerate(top_n, start=1):
        row["rank"] = index

    return top_n


@click.command(name="top")
@multi_asic_util.multi_asic_click_options
@click.option("--count", type=click.IntRange(min=1), default=5, show_default=True, help="Number of top interfaces")
@click.option(
    "--interval",
    type=click.IntRange(min=0),
    default=1,
    show_default=True,
    help="Sampling interval in seconds"
)
@click.option("-j", "--json", "json_fmt", is_flag=True, help="Print in JSON format")
def top(namespace, display, count, interval, json_fmt):
    """Show top N interfaces by traffic (RX + TX).

    The command reads interface rate counters for the selected namespace/display
    scope, ranks interfaces by total throughput, and prints table or JSON output.
    """

    rates = fetch_interface_rates(namespace, display, interval)

    top_interfaces = rank_interfaces_by_traffic(rates, count)

    if json_fmt:
        click.echo(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "interval_seconds": float(interval),
            "top_interfaces": top_interfaces
        }, indent=4))
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
