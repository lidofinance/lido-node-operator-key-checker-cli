# Node Operator Key Checker Cli

## Installation

Run `./init.sh` to set up git submodules and install Python dependencies

## Running

### Required Parameters for All Commands

```
--rpc_url                       Local node / Infura / Alchemy API RPC url
--network                       Network to use, Mainnet / Pyrmont
--lido_address              Address of the main contract
--nos_registry_address              Address of the operator contract
```

### Optional Parameters for All Commands

By default CLI will load Lido.json and NodeOperatorsRegistry.json from `abi` folder, but you can specify your own paths if needed via:

```
--lido_abi			        JSON Main Contract ABI file path
--nos_registry_abi			        JSON Operator Contract ABI file path
```

### Checking Network Keys

Command: `validate_network_keys`

Example:

```
python lido_validate_keys.py --rpc_url https://eth-goerli.alchemyapi.io/v2/XXX --network pyrmont --lido_address 0x123 --nos_registry_address 0x123 validate_network_keys
```

### Checking Keys from File

Command: `validate_file_keys`
Specify the input file via `--file` or copy it as `input.json` to the cli folder

Example with default file location:

```
python lido_validate_keys.py --rpc_url https://eth-goerli.alchemyapi.io/v2/XXX --network pyrmont --lido_address 0x123 --nos_registry_address 0x123 validate_file_keys
```

Example with custom file path:

```
python lido_validate_keys.py --rpc_url https://eth-goerli.alchemyapi.io/v2/XXX --network pyrmont --lido_address 0x123 --nos_registry_address 0x123 validate_file_keys --file input.json
```

You can also get all commands and options via `python cli.py --help`
