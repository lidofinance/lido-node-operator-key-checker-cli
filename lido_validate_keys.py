import json

import click
from py_ecc.bls import G2ProofOfPossession as bls
from web3 import Web3
from web3.middleware import geth_poa_middleware

from eth2deposit.settings import get_chain_setting
from eth2deposit.utils.ssz import (
    compute_deposit_domain,
    compute_signing_root,
    DepositMessage,
)


@click.group()
@click.option(
    "--rpc_url",
    help="Local node / Infura / Alchemy API url",
)
@click.option("--network", help="Network to use eg Mainnet / Pyrmont.")
@click.option(
    "--lido_address",
    help="Address of the main contract.",
)
@click.option(
    "--nos_registry_address",
    help="Address of the operator contract.",
)
@click.option(
    "--lido_abi",
    default="abi/Lido.json",
    help="ABI file path for contract.",
)
@click.option(
    "--nos_registry_abi",
    default="abi/NodeOperatorsRegistry.json",
    help="ABI file path for operators contract.",
)
@click.pass_context
def cli(ctx, rpc_url, network, lido_address, nos_registry_address, lido_abi, nos_registry_abi):
    """CLI utility to load Node Operators keys from file or network and check for duplicates and invalid signatures."""

    # Connect to network

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # Pyrmont needs a middleware
    if network.lower() == "pyrmont":
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    click.secho("Connected to the network", fg="green")

    # Load contracts from network

    lido_abi = json.load(open(lido_abi))
    lido_contract = w3.eth.contract(address=lido_address, abi=lido_abi)

    operators_abi = json.load(open(nos_registry_abi))
    operators_contract = w3.eth.contract(address=nos_registry_address, abi=operators_abi)

    # Setting up required items for validation

    withdrawal_credentials = bytes(lido_contract.functions.getWithdrawalCredentials().call())
    click.secho("Loaded withdrawal credentials", fg="green")

    # Appropriate domain for needed network
    fork_version = get_chain_setting(network.lower()).GENESIS_FORK_VERSION
    domain = compute_deposit_domain(fork_version=fork_version)

    # Fetching network data for operator contract
    operators = load_network_data(operators_contract)

    # Passing computed items as context to command functions
    ctx.ensure_object(dict)
    ctx.obj["operators"] = operators
    ctx.obj["withdrawal_credentials"] = withdrawal_credentials
    ctx.obj["domain"] = domain


@cli.command("validate_network_keys")
@click.pass_context
def validate_network_keys(ctx):
    """Checking node operator keys from network."""

    # Loading variables from context
    operators = ctx.obj["operators"]
    withdrawal_credentials = ctx.obj["withdrawal_credentials"]
    domain = ctx.obj["domain"]

    # Check for invalid signatures and finding duplicates

    for op_i, op in enumerate(operators):

        if not op["keys"]:
            click.echo("#%s %s has no keys" % (op["id"], op["name"]))
            continue

        with click.progressbar(
            op["keys"], label="Checking #%s %s" % (op["id"], op["name"]), show_eta=False
        ) as keys:
            for key_i, key in enumerate(keys):

                # Checking if each key has a correct signature
                operators[op_i]["keys"][key_i]["valid_signature"] = validate_key(
                    key, withdrawal_credentials, domain
                )

                # Checking if each key is a duplicate
                # TODO: this can be done in O(N) instead of O(N^2) if len(operators) > 100

                duplicates = find_duplicates(operators=operators, original_op=op, key=key)
                operators[op_i]["keys"][key_i]["duplicate"] = bool(duplicates)

                op["keys"][key_i]["duplicates"] = []
                for duplicate_i, duplicate in enumerate(duplicates):
                    operators[op_i]["keys"][key_i]["duplicates"].append(
                        dict(
                            op_id=duplicate["op"]["id"],
                            op_name=duplicate["op"]["name"],
                            index=duplicate["key"]["index"],
                            approved=bool(duplicate["op"]["stakingLimit"]),
                            used=duplicate["key"]["used"],
                        )
                    )

    # Outputting every wrong data occurrence
    invalid = 0
    for op in operators:
        for key in op["keys"]:
            if key["duplicate"]:
                for duplicate in key["duplicates"]:
                    click.secho(
                        "%s's key %s (OP Approved: %s, Key Used: %s) is a duplicate of %s's key (OP Approved: %s, Key Used: %s)"
                        % (
                            op["name"],
                            key["key"].hex(),
                            op["stakingLimit"] > 0,
                            key["used"],
                            duplicate["op_name"],
                            duplicate["approved"],
                            duplicate["used"],
                        ),
                        fg="red",
                    )
                    invalid += 1
            if not key["valid_signature"]:
                click.secho(
                    "%s's key %s has an invalid signature" % (op["name"], key["key"].hex()),
                    fg="red",
                )
                invalid += 1

    click.secho(
        "%s occurrences of invalid data found" % invalid, fg="green" if not invalid else "red"
    )


@click.option(
    "--file",
    default="input.json",
    help="JSON input file with proposed keys",
)
@cli.command("validate_file_keys")
@click.pass_context
def validate_file_keys(ctx, file):
    """Checking node operator keys from input file."""

    # Loading variables from context
    withdrawal_credentials = ctx.obj["withdrawal_credentials"]
    domain = ctx.obj["domain"]
    operators = ctx.obj["operators"]

    # Load and format JSON file
    proposed_keys_raw = json.load(open(file))
    proposed_keys = format_proposed_keys_file(proposed_keys_raw)

    # Search for duplicates
    click.secho("Searching for duplicates")
    duplicates = []
    for proposed_keys_item in proposed_keys:
        duplicate = find_duplicates(operators=operators, key=proposed_keys_item)
        if duplicate:
            duplicates.append(duplicate)
    if not duplicates:
        click.secho("No duplicate keys found", fg="green")
    else:
        click.secho("Duplicate keys found:", fg="red")
        for duplicate_occurrences in duplicates:
            for duplicate_occurrence in duplicate_occurrences:
                click.secho(
                    "Key %s is a duplicate of %s's key (OP Approved: %s, Key Used: %s)"
                    % (
                        duplicate_occurrence["key"]["key"].hex(),
                        duplicate_occurrence["op"]["name"],
                        duplicate_occurrence["op"]["stakingLimit"] > 0,
                        duplicate_occurrence["key"]["used"],
                    ),
                    fg="red",
                )

    # Check signatures
    invalid_signatures = []
    with click.progressbar(proposed_keys, label="Checking signatures", show_eta=False) as keys:
        for proposed_keys_item in keys:
            valid = validate_key(proposed_keys_item, withdrawal_credentials, domain)

            if not valid:
                invalid_signatures.append(proposed_keys_item["pubkey"])

    if not invalid_signatures:
        click.secho("No invalid signatures found", fg="green")
    else:
        click.secho("Invalid signatures found for keys:", fg="red")
        for item in invalid_signatures:
            click.secho(item, fg="red")


# Common helpers


def format_proposed_keys_file(items):
    """Format input to the same data keys on the network"""
    for item in items:
        item["key"] = bytes.fromhex(item["pubkey"]) if item.get("pubkey", False) else item["key"]
        item["depositSignature"] = (
            bytes.fromhex(item["signature"])
            if item.get("signature", False)
            else item["depositSignature"]
        )
    return items


def load_network_data(operators_contract):
    """Load all node operators and their data from the network"""

    # Getting total operators count
    opcount = operators_contract.functions.getNodeOperatorsCount().call()
    click.echo("There are %s operators on the network" % opcount)

    # Get each operator's data, add id
    operators_raw = [
        [i] + operators_contract.functions.getNodeOperator(_id=i, _fullInfo=True).call()
        for i in range(opcount)
    ]

    # Assign keys for the data

    # Getting function data from contract ABI
    function_data = next(
        (x for x in operators_contract.abi if x["name"] == "getNodeOperator"), None
    )

    # Adding "id" and all output name keys
    op_keys = ["id"] + [x["name"] for x in function_data["outputs"]]
    operators_data = [dict(zip(op_keys, op)) for op in operators_raw]

    # Get and add signing keys to node operators
    with click.progressbar(operators_data, label="Getting all signing keys", show_eta=False) as ops:
        for op in ops:
            op["keys"] = list_signing_keys(operators_contract, op["id"], op["totalSigningKeys"])

    return operators_data


def list_signing_keys(operators_contract, op_id, key_count):
    """Load signing keys for a particular operator"""

    # Getting function data from contract ABI
    function_data = next((x for x in operators_contract.abi if x["name"] == "getSigningKey"), None)

    # Adding "index" and all output name keys
    signing_keys_keys = ["index"] + [x["name"] for x in function_data["outputs"]]

    signing_keys_list = [
        dict(
            zip(
                signing_keys_keys,
                [i]
                + operators_contract.functions.getSigningKey(_operator_id=op_id, _index=i).call(),
            )
        )
        for i in range(0, key_count)
    ]

    return signing_keys_list


def find_duplicates(operators, key, original_op=None):
    """Compare every available key with each other to spot duplicates"""
    duplicates_found = []
    for operator in operators:
        for second_key in operator["keys"]:
            if key["key"] == second_key["key"]:
                if not original_op:
                    duplicates_found.append({"op": operator, "key": second_key})
                elif (original_op["id"], key["index"]) != (operator["id"], second_key["index"]):
                    duplicates_found.append({"op": operator, "key": second_key})
    return duplicates_found


def validate_key(key, withdrawal_credentials, domain):
    """Run signature validation on a key"""
    # TODO: Detailed info how it's being validated

    pubkey = key["key"]
    signature = key["depositSignature"]

    # Minimum staking requirement of 32 ETH per validator
    REQUIRED_DEPOSIT_ETH = 32
    ETH2GWEI = 10 ** 9
    amount = REQUIRED_DEPOSIT_ETH * ETH2GWEI

    deposit_message = DepositMessage(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )

    signing_root = compute_signing_root(deposit_message, domain)

    return bls.Verify(pubkey, signing_root, signature)


if __name__ == "__main__":
    cli(obj={})
