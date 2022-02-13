import json
from time import time

import click
import lido_sdk.config

from web3 import Web3
from lido_sdk import Lido

import logging

SDK_MODULE_NAME = "verified_keys_progress_logger"

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
@click.option(
    "-d",
    "--details",
    is_flag=True,
)
@click.pass_context
def validate_network_keys(ctx, details):
    """Checking node operator keys from network."""

    t1 = time()

    lido: Lido = ctx.obj["lido"]
    _load_base_data(lido, details)
    _validate_keys(lido)
    _find_duplicated_keys(lido)

    total_time = time() - t1
    click.secho(f"Finished in {round(total_time, 2)} seconds.")


@click.option(
    "--file",
    type=str,
    required=True,
    help="JSON input file with proposed keys",
)
@cli.command("validate_file_keys")
@click.pass_context
def validate_file_keys(ctx, file):
    """Checking node operator keys from input file."""

    t1 = time()

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
    _validate_keys(lido, keys)
    _find_duplicated_keys(lido, keys)

    total_time = time() - t1
    click.secho(f"Finished in {round(total_time, 2)} seconds.")


def _load_base_data(lido, show_details=False):
    click.secho("Start fetching data...", fg="green")
    operator_ids_list = lido.get_operators_indexes()
    click.secho(f"Operators count fetch done. Operators count: [{len(operator_ids_list)}]", fg="green")
    click.secho("--------", fg="green")
    click.secho("Fetch operators details...", fg="green")
    operators_details = lido.get_operators_data()
    click.secho("Operator details fetch done.", fg="green")
    if show_details:
        click.secho("Operators list:", fg="green")

        for operator in operators_details:
            click.secho(f"Index: [{operator['index'] : >2}]. "
                        f"Operator: [{operator['name']: <23}]. "
                        f"Stacking limit: [{operator['stakingLimit']: >4}]. "
                        f"Signed keys: [{operator['totalSigningKeys']: >4}]. "
                        f"Used keys: [{operator['usedSigningKeys']: >4}]")

    click.secho("--------", fg="green")
    click.secho("Fetch operator's keys...", fg="green")
    keys = lido.get_operators_keys()
    click.secho(f"Keys fetch done. Keys count: [{len(keys)}]", fg="green")
    if show_details:
        for operator in operators_details:
            operators_keys_count = sum(1 for key in keys if key['operator_index'] == operator['index'])
            click.secho(f"Index: [{operator['index'] : >2}]. "
                        f"Operator: [{operator['name']: <23}]. "
                        f"Keys fetched: [{operators_keys_count: >4}].")

    click.secho("--------", fg="green")


def _validate_keys(lido, keys=None):
    click.secho("Validating keys...", fg="green")
    logging.basicConfig(level='WARNING', format='%(message)s')
    logging.getLogger(SDK_MODULE_NAME).setLevel(level=logging.DEBUG)

    invalid_keys = lido.validate_keys(keys)

    if invalid_keys:
        click.secho("Invalid keys found:", fg="red")
        for key in invalid_keys:
            operator = next((op for op in lido.operators if op["index"] == key.get("operator_index", None)), None)
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

            operator = next((op for op in lido.operators if op["index"] == dk[0].get("operator_index", None)), None)
            _print_key(dk[0], operator)

            operator = next((op for op in lido.operators if op["index"] == dk[1].get("operator_index", None)), None)
            _print_key(dk[1], operator)
    else:
        click.secho("No duplicated keys found", fg="red")
    click.secho("--------", fg="green")


def _print_key(key, operator=None):
    if operator is None:
        click.secho(f"Key: [{key['key'].hex()}].", fg="red")
    else:
        key_used = 'USED' if key['used'] else 'NOT USED'
        click.secho(
            f"Key: [{key['key'].hex()}]. "
            f"Operator: [{operator['name']}] (index: [{operator['index']}]) key index: [{key['index']}]. "
            f"Key [{key_used}] - OP Active: Stacking Limit: [{operator['stakingLimit']}]. "
            f"Key count used: [{operator['usedSigningKeys']}].",
            fg="red",
        )


if __name__ == "__main__":
    cli(obj={})
