
def keys_len(operators: list[dict]):
    return sum([len(operator["keys"]) for operator in operators])


def merge_keys(lists: list[list[dict]]):
    first_operators = lists[0]
    merged_operators = []

    for index, operator in enumerate(first_operators):
        merged_operator_keys = [key for operators in lists for key in operators[index]["keys"]]

        merged_operators.append({
            **operator,
            "keys": merged_operator_keys
        })

    return merged_operators


def filter_keys(operators: list[dict], callback):
    return [{**operator, "keys": [key for key in operator["keys"] if callback(key)]} for operator in operators]
