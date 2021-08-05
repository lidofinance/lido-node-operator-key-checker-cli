# Node Operator Key Checker CLI

## Installation

You can get this tool using `pip`:

```
pip install lido-cli
```

Or if you cloned this repository, install Python dependencies via:

```
./init.sh
```

Depending on how it's installed use:

`lido-cli ...opts command ...opts` or `python lido_validate_keys.py ...opts command ...opts`

## Running

### RPC Provider

This is the only thing required, the rest will be handled automatically unless overridden.

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX validate_network_keys
```

### Optional Parameters

By default CLI will use embedded strings and ABIs, but you can specify your own arguments if needed. Make sure to use them on CLI itself and not on the command eg:

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX --max_multicall 300 --lido_address 0x123 --lido_abi_path /Users/x/xx.json --registry_address 0x123 --registry_abi_path /Users/x/xx.json validate_network_keys
```

```
--rpc                   RPC provider for network calls.
--max_multicall         Batch amount of function calls to fit into one RPC call.
--lido_address          Address of the main contract.
--lido_abi_path         ABI file path for the main contract.
--registry_address      Address of the operator contract.
--registry_abi_path     ABI file path for operators contract.
```

### Checking Network Keys

Slow version, but it does a full check.  
Command: `validate_network_keys`

Example:

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX validate_network_keys
```

### Fast Checking Network Keys

A faster version of the previous command. It uses cache and excludes used keys from validating (the duplication check still runs for all loaded keys).  
Command: `validate_network_keys_fast`

Example:

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX validate_network_keys_fast
```

Clear cache:

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX validate_network_keys_fast --clear_cache
```

### Checking Keys from File

Command: `validate_file_keys`
Specify the input file via `--file` or copy it as `input.json` to the cli folder

Example with default file location:

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX validate_file_keys
```

Example with custom file path:

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX validate_file_keys --file input.json
```

You can also get all commands and options via `python lido_validate_keys.py --help`
