"""stapel-classified capabilities.json emitter — a shim over stapel_tools.

New in 0.2.0, and for the same reason the contract triad is: this package
grew a surface. Until then ``docs/capabilities.json`` was hand-authored,
which was honest for a preset with nothing callable in it and is not honest
for one that serves three endpoints and three comm Functions.
"""
from pathlib import Path

from stapel_tools.capabilities import axis_group_rules, run_capabilities_cli


def main(argv=None):
    from stapel_classified._codegen import _configure

    _configure()
    from stapel_classified.conf import DEFAULTS
    from stapel_classified.urls_v1 import GATE_REGISTRY

    # The axes that change WHAT THE PRODUCT DOES to its users: whether a
    # block is enforced at all, and which providers answer the questions a
    # conversation header asks. Batch limits and timeouts are tuning — they
    # bound cost, they do not change the deal with anybody.
    axes = {
        "BLOCK_ENFORCEMENT",
        "BLOCK_FUNCTION",
        "PUBLIC_PROFILE_FUNCTION",
        "SELLER_RATING_TARGET_TYPE",
    }
    return run_capabilities_cli(
        argv,
        repo=Path(__file__).resolve().parent,
        canonical_prefix="/classified/api/v1",
        defaults=DEFAULTS,
        registry=GATE_REGISTRY,
        is_axis=lambda k: k in axes,
        axis_group=axis_group_rules(
            exact={
                "BLOCK_ENFORCEMENT": "classified.blocks",
                "BLOCK_FUNCTION": "classified.blocks",
                "PUBLIC_PROFILE_FUNCTION": "classified.cards",
                "SELLER_RATING_TARGET_TYPE": "classified.cards",
            }
        ),
        prog="stapel-classified-capabilities",
    )


if __name__ == "__main__":
    raise SystemExit(main())
