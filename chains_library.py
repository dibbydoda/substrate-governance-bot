# This module contains information for each chain as dataclass.
from dataclasses import dataclass
from disnake import Emoji


@dataclass
class SubstrateChain:
    """Class representing a substrate blockchain."""
    name: str
    endpoints: tuple
    logo_file: str
    is_relay: bool = False
    emoji: Emoji = None


Polkadot = SubstrateChain(name="Polkadot",
                          is_relay=True,
                          endpoints=("wss://rpc.polkadot.io",
                                     "wss://polkadot.api.onfinality.io/public-ws",
                                     "wss://polkadot-rpc.dwellir.com"),
                          logo_file="polkadot-circle.png")

Kusama = SubstrateChain(name="Kusama",
                        is_relay=True,
                        endpoints=("wss://kusama-rpc.polkadot.io",
                                   "wss://kusama.api.onfinality.io/public-ws",
                                   "wss://kusama-rpc.dwellir.com"),
                        logo_file="kusama-128.png")

Statemine = SubstrateChain(name="Statemine",
                           endpoints=('wss://statemine-rpc.polkadot.io',
                                      'wss://statemine.api.onfinality.io/public-ws',
                                      'wss://statemine-rpc.dwellir.com'),
                           logo_file="statemine.png")

# Encointer = SubstrateChain(name="Encointer")

chains = (Polkadot, Kusama, Statemine)


def get_chain(search_name):
    for chain in chains:
        if chain.name == search_name:
            return chain
