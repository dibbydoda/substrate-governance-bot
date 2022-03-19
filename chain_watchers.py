import asyncio
import sqlite3
import threading

import aiohttp
import disnake as discord
from substrateinterface import SubstrateInterface

import governancebot

interfaces= {}
failed_connections = []


def connect_to_chain(chain):
    for url in chain.endpoints:
        try:
            print(f"Trying {url}")
            interface = SubstrateInterface(url=url)
            # Check connection by getting current block number
            current_block = interface.get_block(finalized_only=True)
            print(current_block['header']['number'])
            assert type(current_block['header']['number']) == int
        except:
            continue
        else:
            return interface

    # If all endpoints are tried and a connection to the chain cannot be made
    print(f"Connecting to chain {chain.name} failed.")


def referendum_watcher_subscription(events, _update_number, _subscription_id):
    for event in events:
        try:
            if event['event'][0] == 'Democracy' and event['event'][1][0] == 'Started':
                return event['event'][1][1]
        except IndexError:
            pass


def chain_watcher(chain):
    # Make connection to interface
    interface = None
    while interface is None:
        interface = connect_to_chain(chain)

    while True:
        # Create Subscription for Interface
        new_referendum_index = interface.query(module='System',
                                               storage_function='Events',
                                               subscription_handler=referendum_watcher_subscription)
        asyncio.run(notify_webhooks(chain, new_referendum_index))


async def create_chain_watchers(chains):
    for chain in chains:
        watcher_thread = threading.Thread(target=chain_watcher, args=(chain,), daemon=True)
        watcher_thread.start()


async def notify_webhooks(chain, referendum_index):
    bot = governancebot.client
    db = sqlite3.connect('webhooks.db')
    c = db.cursor()
    c.execute('''SELECT id, guild_id, token, url, pings FROM webhooks WHERE chain = ?''', (chain.name,))
    rows = c.fetchall()
    async with aiohttp.ClientSession() as session:
        subscan_embed = discord.Embed(title="Subscan Referendum Info",
                                      type="link",
                                      url=f"https://{chain.name}.subscan.io/referenda/{referendum_index}",
                                      description="Click here to get more info on the voting on subscan.",
                                      colour=discord.Colour.purple())
        subscan_embed.set_image(url="https://miro.medium.com/max/1400/1*y-ihVke24XjJ4-sWS-5uyQ.png")

        js_embed = discord.Embed(title="Polkadot.JS",
                                 type="link",
                                 url=f"https://polkadot.js.org/apps/#/explorer",
                                 description=f"Click here to access polkadot.js for voting. "
                                             f"Navigate to the desired chain, then go to the governance-democracy tab.",
                                 colour=discord.Colour.orange())
        js_embed.set_image(url="https://polkadot.js.org/extension/logo.jpg")

        for webhook_data in rows:
            webhook = discord.Webhook.from_url(url=webhook_data[3], session=session)
            pings: str = webhook_data[4]
            if pings is not None:
                mentions = [bot.get_guild(webhook_data[1]).get_role(int(role_id)).mention for
                            role_id in pings.split(',')]
            message = ' ,'.join(mentions)
            if pings is not None:
                message += "\n"
            message += (f"A new referendum is up for vote on {chain.name} "
                       f"\nFor more information visit Subscan."
                       f"Vote on polkadot.js")

            await webhook.send(content=message, embeds=[subscan_embed, js_embed])

        db.close()







