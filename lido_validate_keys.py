import json
from typing import List

import click
import lido_sdk.config

from web3 import Web3
from lido_sdk import Lido

from helpers import pick_by, count_by


@click.group()
@click.option(
    "--rpc",
    type=str,
    required=True,
    help="RPC provider for network calls.",
)
@click.option(
    "--multicall_max_bunch",
    type=int,
    required=False,
    help="Batch amount of function calls to fit into one RPC call.",
)
@click.option(
    "--multicall_max_workers",
    type=int,
    required=False,
    help="Maximum parallel calls to RPC.",
)
@click.option(
    "--multicall_max_retries",
    type=int,
    required=False,
    help="Retries to make success call to RPC before exception will be raised.",
)
@click.pass_context
def cli(ctx, rpc, multicall_max_bunch, multicall_max_workers, multicall_max_retries):
    """CLI utility to load Node Operators keys from file or network and check for duplicates and invalid signatures."""
    w3 = Web3(Web3.HTTPProvider(rpc))
    chain_id = w3.eth.chainId

    if chain_id == 5:
        from web3.middleware import geth_poa_middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    lido = Lido(
        w3,
        MULTICALL_MAX_BUNCH=multicall_max_bunch or lido_sdk.config.MULTICALL_MAX_BUNCH,
        MULTICALL_MAX_WORKERS=multicall_max_workers or lido_sdk.config.MULTICALL_MAX_WORKERS,
        MULTICALL_MAX_RETRIES=multicall_max_retries or lido_sdk.config.MULTICALL_MAX_RETRIES,
    )

    # Passing computed items as context to command functions
    ctx.ensure_object(dict)
    ctx.obj["lido"] = lido


@cli.command("validate_network_keys")
@click.pass_context
def validate_network_keys(ctx):
    """Checking node operator keys from network."""
    lido: Lido = ctx.obj["lido"]
    _load_base_data(lido)
    _validate_keys(lido)
    _find_duplicated_keys(lido)
    click.secho("Finished", fg="green")


@click.option(
    "--file",
    type=str,
    default="input.json",
    help="JSON input file with proposed keys",
)
@cli.command("validate_file_keys")
@click.pass_context
def validate_file_keys(ctx, file):
    """Checking node operator keys from input file."""

    # Loading variables from context
    lido = ctx.obj["lido"]
    keys = []

    # Load and format JSON file
    # Formatting eth2deposit cli input fields
    input_raw = json.load(open(file))
    for item in input_raw:
        item["key"] = bytes.fromhex(item["pubkey"])
        item["depositSignature"] = bytes.fromhex(item["signature"])
        del item["pubkey"]
        del item["signature"]
        keys.append(item)

    _load_base_data(lido)
    _validate_keys(lido, keys, strict=True)
    _find_duplicated_keys(lido, keys)

    click.secho("Finished.")


def _load_base_data(lido):
    click.secho("Start fetching data...", fg="green")
    lido.get_operators_indexes()
    click.secho("Operators count fetch done.", fg="green")
    click.secho("--------", fg="green")
    click.secho("Fetch operators details...", fg="green")
    lido.get_operators_data()
    click.secho("Operator details fetch done.", fg="green")
    click.secho("--------", fg="green")
    click.secho("Fetch operator's keys...", fg="green")
    lido.get_operators_keys()
    click.secho("Keys fetch done.", fg="green")
    click.secho("--------", fg="green")


def _validate_keys(lido, keys=None, strict=False):
    click.secho("Validating keys...", fg="green")
    invalid_keys = lido.validate_keys(keys, strict)

    if invalid_keys:
        click.secho("Invalid keys found:", fg="red")
        for key in invalid_keys:
            operator = next(operator for operator in lido.operators if operator["index"] == key["operator_index"])

            _print_key(key, operator)
    else:
        click.secho("No invalid keys found.", fg="red")
    click.secho("--------", fg="green")


def _find_duplicated_keys(lido, keys=None):
    click.secho("Search for duplicates...", fg="green")

    if keys is None:
        duplicated_keys = lido.find_duplicated_keys()
    else:
        duplicated_keys = lido.find_duplicated_keys([*lido.keys, *keys])

    if duplicated_keys:
        click.secho("Duplicated keys found:", fg="red")
        for dk in duplicated_keys:
            click.secho("Pair:", fg="red")
            operator = next(operator for operator in lido.operators if operator["index"] == dk[0]["operator_index"])
            _print_key(dk[0], operator)

            operator = next(operator for operator in lido.operators if operator["index"] == dk[1]["operator_index"])
            _print_key(dk[1], operator)
    else:
        click.secho("No duplicated keys found", fg="red")
    click.secho("--------", fg="green")


def _print_key(key, operator=None):
    if operator is None:
        click.secho(f"Key: ${key['key']}", fg="red")
    else:
        key_used = 'USED' if key['used'] else 'NOT USED'
        click.secho(f"${operator['name']} (${operator['index']}) key ${key['index']} ${key_used} - OP Active: ${operator['stakingLimit']} Key used: ${operator['usedSigningKeys']}.", fg="red")


if __name__ == "__main__":
    cli(obj={})
