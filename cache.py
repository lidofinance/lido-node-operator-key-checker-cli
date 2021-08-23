import click
import dbm
import json

from typing import List, Dict
from os.path import expanduser, join

home_user_dir = expanduser("~")
cache_dir = home_user_dir
cache_file_prefix = "lido-keys-cache-"


def open_cache_file(chainId: int):
    file_name = cache_file_prefix + str(chainId)
    file_path = join(cache_dir, file_name)

    return dbm.open(file_path, "c")


def clear_keys_cache(chainId: int):
    with open_cache_file(chainId) as cache:
        for key in cache.keys():
            del cache[key]


def check_wc(cache, wc: bytes):
    cached_wc = cache.get("wc")

    is_empty_cache = len(cache.keys()) == 0
    is_same_wc = cached_wc is not None and cache.get("wc") == wc.hex().encode()

    if not is_empty_cache and not is_same_wc:
        click.secho("Withdrawal credentials do not match a cached credentials, clear cache to continue", fg="red")
        exit()


def get_keys_from_cache(chainId: int, wc: bytes, operators: List[Dict]):
    operators_cached_keys = []
    operators_new_keys = []

    with open_cache_file(chainId) as cache:
        check_wc(cache, wc)

        for operator in operators:
            cached_keys = []
            new_keys = []

            for key in operator["keys"]:
                public_key = key["key"].hex()
                cached_key = parse_key(cache.get(public_key))
                is_valid_cache = cached_key is not None and cached_key["depositSignature"] == key["depositSignature"]

                if cached_key and not is_valid_cache:
                    click.secho("Invalid cache for key: %s" % (public_key), fg="red")
                    click.secho("Operator: %s (%s)" % (operator["name"], operator["id"]))

                if is_valid_cache:
                    cached_keys.append({**key, "valid_signature": cached_key["valid_signature"]})
                else:
                    new_keys.append(key)

            operators_cached_keys.append({**operator, "keys": cached_keys})
            operators_new_keys.append({**operator, "keys": new_keys})

    return operators_cached_keys, operators_new_keys


def save_keys_to_cache(chainId: int, wc: bytes, operators: List[Dict]):
    with open_cache_file(chainId) as cache:
        check_wc(cache, wc)
        cache["wc"] = wc.hex()

        for operator in operators:
            for key in operator["keys"]:
                public_key = key["key"].hex()
                cache[public_key] = serialize_key(key)


def parse_key(string: str):
    if string is None:
        return None

    parsed = json.loads(string)

    return {
        **parsed,
        "key": bytes.fromhex(parsed["key"]),
        "depositSignature": bytes.fromhex(parsed["depositSignature"]),
    }


def serialize_key(key: dict) -> str:
    return json.dumps({
        **key,
        "key": bytes.hex(key["key"]),
        "depositSignature": bytes.hex(key["depositSignature"]),
    })
