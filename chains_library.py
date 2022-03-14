# This module contains information for each chain as dataclass.

from dataclasses import dataclass

@dataclass
class SubstrateChain:
    """Class representing a substrate blockchain."""
    name: str
    is_relay: bool
    endpoints: tuple
    logo_file: str

Polkadot = SubstrateChain(name="Polkadot",
                          is_relay=True,
                          endpoints=(),
                          logo_file="polkadot-circle.png")

Kusama = SubstrateChain(name="Kusama",
                        is_relay=True,
                        endpoints=(),
                        logo_file="")

chains= (Polkadot, Kusama)

def get_chain(search_name):
    for chain in chains:
        if chain.name == search_name:
            return chain




