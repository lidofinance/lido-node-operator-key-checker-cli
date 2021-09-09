# <img src="https://docs.lido.fi/img/logo.svg" alt="Lido" width="46"/> Node Operator Key Checker CLI

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
lido-cli --rpc https://mainnet.provider.io/v3/XXX --multicall_max_bunch 100 --multicall_max_workers 3 --multicall_max_retries 5 validate_network_keys
```

```
--rpc                               RPC provider for network calls.
--multicall_max_bunch               Max bunch amount of Calls in one Multicall (max recommended 300).
--multicall_max_workers             Max parallel calls for multicalls.
--multicall_max_retries             Max call retries.
```

### Checking Network Keys

Command: `validate_network_keys`

Example:

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX validate_network_keys
```

### Checking Keys from File

Command: `validate_file_keys`
Specify the input file via `--file`

Example:

```
lido-cli --rpc https://mainnet.provider.io/v3/XXX validate_file_keys --file input.json
```

### ---

You can also get all commands and options via `python lido_validate_keys.py --help`
