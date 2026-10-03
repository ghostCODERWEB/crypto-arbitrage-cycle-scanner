"""Enumerate short currency cycles and calculate fee-adjusted theoretical returns with canonical deduplication."""

from .common import (
    number,
    integer,
    identity,
    records,
    chronology,
    allocate,
    result,
    validate_document,
)
from decimal import Decimal


def _analyze(d):
    quotes = records(d["quotes"], "id")
    graph = {}
    assets = set()
    for q in quotes:
        source = identity(q["from"])
        target = identity(q["to"])
        rate = number(q["rate"], minimum="0.000000000000000001")
        fee = number(q["fee"], maximum=1)
        if source == target:
            raise ValueError("self edge prohibited")
        graph.setdefault(source, []).append(
            {"target": target, "rate": rate * (1 - fee), "id": q["id"]}
        )
        assets.update((source, target))
    if len(assets) > 20 or len(quotes) > 100:
        raise ValueError("graph too large")
    maxhops = integer(d["max_hops"], 2, 6)
    cycles = {}
    explored = 0
    for origin in sorted(assets):

        def visit(current, path, edges, multiplier):
            nonlocal explored
            explored += 1
            if explored > 100000:
                raise ValueError("cycle search bound exceeded")
            for edge in graph.get(current, []):
                target = edge["target"]
                new = multiplier * edge["rate"]
                if target == origin and len(path) >= 2:
                    key = tuple(edges + [edge["id"]])
                    rotations = [key[i:] + key[:i] for i in range(len(key))]
                    canonical = min(rotations)
                    cycles[canonical] = {
                        "edges": list(canonical),
                        "multiplier": new,
                        "profit_ratio": new - 1,
                        "profitable": new > 1,
                    }
                elif target not in path and len(path) < maxhops:
                    visit(target, path + [target], edges + [edge["id"]], new)

        visit(origin, [origin], [], number(1))
    return result(
        {
            "cycles": sorted(
                cycles.values(), key=lambda c: (-c["multiplier"], c["edges"])
            ),
            "profitable_count": sum(c["profitable"] for c in cycles.values()),
        }
    )


def analyze(document):
    validate_document(document)
    try:
        return result(_analyze(document))
    except (KeyError, TypeError, ArithmeticError, RecursionError) as error:
        raise ValueError("invalid domain input: " + str(error)) from error
