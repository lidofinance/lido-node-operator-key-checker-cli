# Node Operator Key Checker Cli

## Installation

Run `./init.sh` install Python dependencies

## Running

### RPC Provider environment variable

This is the only thing required, the rest will be handled automatically unless overridden.

```
WEB3_PROVIDER_URI=https://mainnet.provider.io/v3/XXX python3 lido_validate_keys.py validate_network_keys
```

### Optional Parameters

By default CLI will use embedded strings and ABIs, but you can specify your own arguments if needed. Make sure to use them on CLI itself and not on the command eg:

```
WEB3_PROVIDER_URI=XXX python lido_validate_keys.py --max_multicall 300 --lido_address 0x123 --lido_abi_path /Users/x/xx.json --registry_address 0x123 --registry_abi_path /Users/x/xx.json validate_network_keys
```

```
--max_multicall				Batch amount of function calls to fit into one RPC call.
--lido_address				Address of the main contract.
--lido_abi_path				ABI file path for the main contract.
--registry_address			Address of the operator contract.
--registry_abi_path			ABI file path for operators contract.
```

### Checking Network Keys

Command: `validate_network_keys`

Example:

```
WEB3_PROVIDER_URI=XXX python lido_validate_keys.py validate_network_keys
```

### Checking Keys from File

Command: `validate_file_keys`
Specify the input file via `--file` or copy it as `input.json` to the cli folder

Example with default file location:

```
WEB3_PROVIDER_URI=XXX python lido_validate_keys.py validate_file_keys
```

Example with custom file path:

```
WEB3_PROVIDER_URI=XXX python lido_validate_keys.py validate_file_keys --file input.json
```

You can also get all commands and options via `python lido_validate_keys.py --help`
