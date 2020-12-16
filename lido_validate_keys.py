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
    lido = w3.eth.contract(address=lido_address, abi=lido_abi)

    operators_abi = json.load(open(nos_registry_abi))
    operators = w3.eth.contract(address=nos_registry_address, abi=operators_abi)

    # Setting up required items for validation
    click.secho("Loaded withdrawal credentials", fg="green")
    withdrawal_credentials = bytes(lido.functions.getWithdrawalCredentials().call())

    # Appropriate domains for needed network
    fork_version = get_chain_setting(network.lower()).GENESIS_FORK_VERSION
    domain = compute_deposit_domain(fork_version=fork_version)

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

    ops = load_network_data(operators)

    # Check for invalid signatures and finding duplicates

    for op_n, op in enumerate(ops):
        with click.progressbar(
            op["keys"], label="Checking %s" % op["name"], show_eta=False
        ) as keys:
            for key_n, key in enumerate(keys):

                # Checking if each key has a correct signature
                ops[op_n]["keys"][key_n]["valid_signature"] = validate_key(
                    key, withdrawal_credentials, domain
                )

                # Checking if each key is a duplicate

                # fixme: this works for O(N^2), but it's possible to do in O(N),
                #  not a big deal if len(ops) < 100
                duplicates = find_duplicates(ops, op, key)
                ops[op_n]["keys"][key_n]["duplicate"] = bool(duplicates)

                op["keys"][key_n]["duplicates"] = []
                for duplicate_n, duplicate in enumerate(duplicates):
                    ops[op_n]["keys"][key_n]["duplicates"].append(
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
    for op in ops:
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
    help="JSON input file with a node description",
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
    node_description_raw = json.load(open(file))
    node_description = format_input_node_description_file(node_description_raw)

    # Load network data
    ops = load_network_data(operators)

    # Search for duplicates
    duplicates = []
    for node_description_item in node_description:
        duplicate = find_duplicates(ops, "all", node_description_item)
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
    with click.progressbar(node_description, label="Checking signatures", show_eta=False) as keys:
        for node_description_item in keys:
            valid = validate_key(node_description_item, withdrawal_credentials, domain)

            if not valid:
                invalid_signatures.append(node_description_item["pubkey"])

    if not invalid_signatures:
        click.secho("No invalid signatures found", fg="green")
    else:
        click.secho("Invalid signatures found for keys:", fg="red")
        for item in invalid_signatures:
            click.secho(item, fg="red")


# Common helpers


def format_input_node_description_file(items):
    """Format input to the same data keys on the network"""
    for item in items:
        item["key"] = bytes.fromhex(item["pubkey"]) if item.get("pubkey", False) else item["key"]
        item["deposit_signature"] = (
            bytes.fromhex(item["signature"]) if item.get("signature", False) else item["deposit_signature"]
        )
    return items


def load_network_data(operators):
    """Load all node operators and their data from the network"""

    # Getting total operators count
    opcount = operators.functions.getNodeOperatorsCount().call()
    click.echo("There are %s operators on the network" % opcount)

    # Get each operator's data, add id
    # fixme use named fields (specified contract's JSON)
    #  to decrease the probability of mistake due to positional misplacing
    ops_raw = [[i] + operators.functions.getNodeOperator(i, True).call() for i in range(0, opcount)]

    # Assign keys for the data

    op_keys = [
        "id",
        "active",
        "name",
        "rewardAddress",
        "stakingLimit",
        "stoppedValidators",
        "totalSigningKeys",
        "usedSigningKeys",
    ]

    ops = [dict(zip(op_keys, op)) for op in ops_raw]

    # Get and add signing keys to node operators
    with click.progressbar(ops, label="Getting all signing keys", show_eta=False) as opss:
        for op in opss:
            op["keys"] = list_signing_keys(operators, op["id"], op["totalSigningKeys"])

    return ops


def list_signing_keys(operators, op_id, key_count):
    """Load signing keys for a particular operator"""

    signing_keys_keys = [
        "index",
        "key",
        "deposit_signature",
        "used",
    ]

    signing_keys_list = [
        dict(
            zip(
                signing_keys_keys,
                [i] + operators.functions.getSigningKey(op_id, i).call(),
            )
        )
        for i in range(0, key_count)
    ]

    return signing_keys_list


def find_duplicates(operators, original_op, key):
    """Compare every available key with each other to spot duplicates"""
    duplicates_found = []
    for operator in operators:
        for second_key in operator["keys"]:
            if key["key"] == second_key["key"]:
                if original_op == "all":  # TODO: unclear logic here, I don't understand
                    duplicates_found.append({"op": operator, "key": second_key})
                elif (original_op["id"], key["index"]) != (operator["id"], second_key["index"]):
                    duplicates_found.append({"op": operator, "key": second_key})
    return duplicates_found


def validate_key(key, withdrawal_credentials, domain):
    """Run signature validation on a key"""
    # TODO: it's better to add how it's validated, because it's unclear for me

    pubkey = key["key"]
    signature = key["deposit_signature"]

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
