import json
from typing import List

import click

from web3 import Web3
from lido import Lido
from lido.contracts.w3_contracts import get_contract

from cache import get_keys_from_cache, save_keys_to_cache, clear_keys_cache
from helpers import filter_keys, keys_len, merge_keys, pick_by, count_by


@click.group()
@click.option(
    "--rpc",
    type=str,
    required=True,
    help="RPC provider for network calls.",
)
@click.option(
    "--max_multicall",
    type=int,
    required=False,
    help="Batch amount of function calls to fit into one RPC call.",
)
@click.option(
    "--lido_address",
    type=str,
    required=False,
    help="Address of the main contract.",
)
@click.option(
    "--lido_abi_path",
    type=str,
    required=False,
    help="ABI file path for the main contract.",
)
@click.option(
    "--registry_address",
    type=str,
    required=False,
    help="Address of the operator contract.",
)
@click.option(
    "--registry_abi_path",
    type=str,
    required=False,
    help="ABI file path for operators contract.",
)
@click.pass_context
def cli(ctx, rpc, max_multicall, lido_address, lido_abi_path, registry_address, registry_abi_path):
    """CLI utility to load Node Operators keys from file or network and check for duplicates and invalid signatures."""

    w3 = Web3(Web3.HTTPProvider(rpc))
    chainId = w3.eth.chainId

    if chainId == 5:
        from web3.middleware import geth_poa_middleware

        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    lido = Lido(
        w3,
        lido_address=lido_address,
        registry_address=registry_address,
        lido_abi_path=lido_abi_path,  # the file-path to the contract's ABI
        registry_abi_path=registry_abi_path,  # the file-path to the contract's ABI
        max_multicall=max_multicall,
    )

    operators_data = lido.get_operators_data()
    click.secho("Loaded {} operators".format(len(operators_data)), fg="green")

    data_with_keys = lido.get_operators_keys(
        operators_data,
    )

    click.secho("Loaded {} operator keys".format(keys_len(data_with_keys)), fg="green")
    click.secho("-")

    contract = get_contract(w3, address=lido.lido_address, path=lido.lido_abi_path)
    withdrawal_credentials = contract.functions.getWithdrawalCredentials().call()

    # Passing computed items as context to command functions
    ctx.ensure_object(dict)
    ctx.obj["lido"] = lido
    ctx.obj["operators"] = data_with_keys
    ctx.obj["chainId"] = chainId
    ctx.obj["withdrawal_credentials"] = withdrawal_credentials


@cli.command("validate_network_keys_fast")
@click.option(
    "--clear_cache",
    is_flag=True,
    help="Clear node operators keys cache",
)
@click.pass_context
def validate_network_keys_fast(ctx, clear_cache):
    """Checking node operator keys from network with cache."""

    # Loading variables from context
    lido = ctx.obj["lido"]
    operators = ctx.obj["operators"]
    chainId = ctx.obj["chainId"]
    wc = ctx.obj["withdrawal_credentials"]

    if clear_cache:
        clear_keys_cache(chainId)
        click.secho("Cache cleared for chain id: {}".format(chainId), fg="green")
        click.secho("-")

    operators_used_keys = filter_keys(operators, lambda key: key["used"] == True)
    operators_unused_keys = filter_keys(operators, lambda key: key["used"] != True)

    # Loading keys from cache
    operators_cached_keys, operators_uncached_keys = get_keys_from_cache(chainId, wc, operators_unused_keys)

    unused_keys = keys_len(operators_unused_keys)
    cached_keys = keys_len(operators_cached_keys)
    uncached_keys = keys_len(operators_uncached_keys)

    click.secho("Unused keys: {}, cached: {}, uncached: {}".format(unused_keys, cached_keys, uncached_keys), fg="green")
    click.secho("-")

    # Validation not cached keys
    operators_validated_keys = lido.validate_keys_multi(operators_uncached_keys)
    click.secho("Completed signature validation", fg="green")

    # Saving to cache
    save_keys_to_cache(chainId, wc, operators_validated_keys)
    click.secho("Completed saving to cache", fg="green")

    # Check for duplications
    merged_keys = merge_keys([operators_used_keys, operators_cached_keys, operators_validated_keys])
    data_found_duplicates = lido.find_duplicates(merged_keys)
    click.secho("Completed duplicate checks", fg="green")

    click.secho("-")

    # Handling invalid signatures
    invalid_signatures = []

    for op in data_found_duplicates:
        for key in op["keys"]:
            if not key["used"] and not key["valid_signature"]:
                invalid_signatures.append(
                    {
                        "key": key,
                        "op_id": op["id"],
                        "op_name": op["name"],
                        "op_staking_limit": bool(op["stakingLimit"]),
                    }
                )

    if not invalid_signatures:
        click.secho("No invalid signatures found", fg="green")
    else:
        click.secho(
            "{} Invalid signatures found for keys:".format(len(invalid_signatures)), fg="red"
        )
        for item in invalid_signatures:
            click.secho(
                "%s (#%s) key #%s - OP Active: %s, Key Used: %s:"
                % (
                    item["op_name"],
                    item["op_id"],
                    item["key"]["index"],
                    item["op_staking_limit"],
                    item["key"]["used"],
                )
            )
            click.secho(item["key"]["key"].hex(), fg="red")

    click.secho("-")

    # Handling duplicates
    with_duplicates = []

    for op in data_found_duplicates:
        for key in op["keys"]:
            if key["duplicate"]:
                with_duplicates.append(
                    {
                        "key": key,
                        "op_name": op["name"],
                        "op_id": op["id"],
                        "op_approved": bool(op["stakingLimit"]),
                    }
                )

    if not with_duplicates:
        click.secho("No duplicates found", fg="green")
    else:
        click.secho("{} Duplicates found:".format(len(with_duplicates)), fg="red")
        for item_with_duplicates in with_duplicates:
            click.secho(item_with_duplicates["key"]["key"].hex(), fg="red")

            click.secho(
                "%s (#%s) key #%s - OP Active: %s, Key Used: %s"
                % (
                    item_with_duplicates["op_name"],
                    item_with_duplicates["op_id"],
                    item_with_duplicates["key"]["index"],
                    item_with_duplicates["op_approved"],
                    item_with_duplicates["key"]["used"],
                )
            )

            click.secho("Duplicates of this key:")
            for dup in item_with_duplicates["key"]["duplicates"]:
                click.secho(
                    "- %s (#%s) key #%s - OP Active: %s, Key Used: %s"
                    % (
                        dup["op_name"],
                        dup["op_id"],
                        dup["index"],
                        dup["approved"],
                        dup["used"],
                    )
                )

    click.secho("Finished")


@cli.command("validate_network_keys")
@click.pass_context
def validate_network_keys(ctx):
    """Checking node operator keys from network."""

    # Loading variables from context
    lido = ctx.obj["lido"]
    operators = ctx.obj["operators"]

    data_validated_keys = lido.validate_keys_multi(
        operators,
    )
    click.secho("Completed signature validation", fg="green")

    data_found_duplicates = lido.find_duplicates(data_validated_keys)
    click.secho("Completed duplicate checks", fg="green")

    click.secho("-")

    # Handling invalid signatures
    invalid_signatures = []

    for op in data_found_duplicates:
        for key in op["keys"]:
            if not key["valid_signature"]:
                invalid_signatures.append(
                    {
                        "key": key,
                        "op_id": op["id"],
                        "op_name": op["name"],
                        "op_staking_limit": bool(op["stakingLimit"]),
                    }
                )

    if not invalid_signatures:
        click.secho("No invalid signatures found", fg="green")
    else:
        click.secho(
            "{} Invalid signatures found for keys:".format(len(invalid_signatures)), fg="red"
        )
        for item in invalid_signatures:
            click.secho(
                "%s (#%s) key #%s - OP Active: %s, Key Used: %s:"
                % (
                    item["op_name"],
                    item["op_id"],
                    item["key"]["index"],
                    item["op_staking_limit"],
                    item["key"]["used"],
                )
            )
            click.secho(item["key"]["key"].hex(), fg="red")

    click.secho("-")

    # Handling duplicates
    with_duplicates = []

    for op in data_found_duplicates:
        for key in op["keys"]:
            if key["duplicate"]:
                with_duplicates.append(
                    {
                        "key": key,
                        "op_name": op["name"],
                        "op_id": op["id"],
                        "op_approved": bool(op["stakingLimit"]),
                    }
                )

    if not with_duplicates:
        click.secho("No duplicates found", fg="green")
    else:
        click.secho("{} Duplicates found:".format(len(with_duplicates)), fg="red")
        for item_with_duplicates in with_duplicates:
            click.secho(item_with_duplicates["key"]["key"].hex(), fg="red")

            click.secho(
                "%s (#%s) key #%s - OP Active: %s, Key Used: %s"
                % (
                    item_with_duplicates["op_name"],
                    item_with_duplicates["op_id"],
                    item_with_duplicates["key"]["index"],
                    item_with_duplicates["op_approved"],
                    item_with_duplicates["key"]["used"],
                )
            )

            click.secho("Duplicates of this key:")
            for dup in item_with_duplicates["key"]["duplicates"]:
                click.secho(
                    "- %s (#%s) key #%s - OP Active: %s, Key Used: %s"
                    % (
                        dup["op_name"],
                        dup["op_id"],
                        dup["index"],
                        dup["approved"],
                        dup["used"],
                    )
                )

    click.secho("Finished")


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
    operators = ctx.obj["operators"]

    # Load and format JSON file
    input_raw = json.load(open(file))

    # Formatting eth2deposit cli input fields
    input = []
    for item in input_raw:
        item["key"] = bytes.fromhex(item["pubkey"])
        item["depositSignature"] = bytes.fromhex(item["signature"])
        del item["pubkey"]
        del item["signature"]
        input.append(item)

    # Handling duplicates among input.json file
    click.secho("Checking '%s' file" % file)
    input_json_keys = [item['key'] for item in input]  # type: List[bytes]
    input_json_key_counts = count_by(input_json_keys, lambda i: i)
    input_json_duplicates = pick_by(input_json_key_counts, lambda qty, _: qty > 1)

    if len(input_json_duplicates) > 0:
        click.secho("Found duplicated entries in '%s' for keys:" % file, fg="red")
        for key, _ in input_json_duplicates.items():
            click.secho(key.hex(), fg="red")
    else:
        click.secho("No duplicates found in '%s'" % file, fg="green")

    click.secho("-")

    # Handling invalid signatures
    click.secho("Searching for invalid signatures")
    invalid_signatures = lido.validate_key_list_multi(input, strict=True)

    if not invalid_signatures:
        click.secho("No invalid signatures found", fg="green")
    else:
        click.secho("Invalid signatures found for keys:", fg="red")
        for key in invalid_signatures:
            click.secho(key["key"].hex(), fg="red")

    click.secho("-")

    # Handling duplicates
    with_duplicates = []
    with click.progressbar(input, label="Searching for duplicates", show_eta=False) as keys:
        for key in keys:
            duplicates_found = lido.spot_duplicates(operators, key)

            if duplicates_found:
                with_duplicates.append({"key": key["key"], "duplicates": duplicates_found})

    if not with_duplicates:
        click.secho("No duplicates found", fg="green")
    else:
        click.secho("Duplicates found for keys:", fg="red")
        for item_with_duplicates in with_duplicates:
            click.secho(item_with_duplicates["key"].hex(), fg="red")

            click.secho("Duplicate of:")
            for dup in item_with_duplicates["duplicates"]:
                click.secho(
                    "- %s (#%s) key #%s - OP Active: %s, Key Used: %s"
                    % (
                        dup["op"]["name"],
                        dup["op"]["id"],
                        dup["key"]["index"],
                        bool(dup["op"]["stakingLimit"]),
                        dup["key"]["used"],
                    )
                )

    click.secho("Finished")


if __name__ == "__main__":
    cli(obj={})
