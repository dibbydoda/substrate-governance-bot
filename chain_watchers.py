import asyncio
import sqlite3
import threading

import aiohttp
import disnake as discord
from substrateinterface import SubstrateInterface
from collections import namedtuple

import governancebot

interfaces = {}
failed_connections = []


def connect_to_chain(chain: namedtuple):
    for url in chain.properties["endpoints"]:
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


def chain_watcher(chain, bot):
    # Make connection to interface
    interface = None
    while interface is None:
        interface = connect_to_chain(chain)

    while True:
        # Create Subscription for Interface
        new_referendum_index = interface.query(module='System',
                                               storage_function='Events',
                                               subscription_handler=referendum_watcher_subscription)
        asyncio.run(notify_webhooks(chain, new_referendum_index, bot))


async def create_chain_watchers(chains, bot):
    for chain_tuple in chains.items():
        chain = governancebot.Chain._make(chain_tuple)
        watcher_thread = threading.Thread(target=chain_watcher, args=(chain, bot), daemon=True)
        watcher_thread.start()


async def notify_webhooks(chain, referendum_index, bot):
    db = sqlite3.connect('webhooks.db')
    db.row_factory = sqlite3.Row
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
            partial_webhook = discord.Webhook.from_url(url=webhook_data['url'],
                                                       session=session,
                                                       bot_token=governancebot.bot_token)
            try:
                await partial_webhook.fetch()
            except discord.NotFound:
                # The webhook has been manually deleted.
                await remove_deleted_webhook(webhook_data['id'])
                continue
            ping_string: str = str(webhook_data['pings'])
            message = ''
            if not ping_string == '':
                print(bot.get_guild(webhook_data['guild_id']))
                print(bot.guilds)
                mentions = [(bot.get_guild(webhook_data['guild_id'])).get_role(int(role_id)).mention for
                            role_id in ping_string.split(',')]
                message += ' ,'.join(mentions)
                message += "\n"
            message += (f"Referendum number {referendum_index} is now up for vote on {chain.name} "
                        f"\nFor more information visit the referendum page Subscan."
                        f"\nVote on polkadot.js")
            print(partial_webhook.is_partial(), partial_webhook.is_authenticated())
            await partial_webhook.send(content=message, embeds=[subscan_embed, js_embed])

        db.close()


async def remove_deleted_webhook(webhook_id):
    db = sqlite3.connect('webhooks.db')
    c = db.cursor()
    try:
        c.execute('''DELETE FROM webhooks WHERE id = ?''', (webhook_id,))
    except sqlite3.DatabaseError:
        pass
    db.commit()
