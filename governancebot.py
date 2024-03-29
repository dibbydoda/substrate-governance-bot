import logging
import os
import sqlite3
from collections import namedtuple, defaultdict as dd
from dataclasses import dataclass, field

import disnake as discord
from disnake.ext import commands
from dotenv import load_dotenv

import chain_watchers
import json

import generate_emojis
from generate_emojis import generate_emojis_for_options

logging.basicConfig(level=logging.WARNING)
load_dotenv(verbose=True)

intents = discord.Intents.none()
intents.guilds = True

client = commands.Bot(intents=intents, test_guilds=[int(os.getenv('test_server_id'))])
bot_token = os.getenv('TOKEN')


@dataclass
class InterfaceMessage:
    chain_selection_option: str = None
    channel_option: str = None
    ping_options: list = field(default_factory=list)


Chain = namedtuple('Chain', 'name, properties')
interface_messages_to_be_processed = dd(InterfaceMessage)


class WebhookInteractionView(discord.ui.View):
    async def on_timeout(self) -> None:
        message = self.message
        view = discord.ui.View.from_message(message)
        for item in view.children:
            item.disabled = True
        await message.edit(content="**THIS MENU TIMED OUT. PLEASE START AGAIN**", view=view)


@client.event
async def on_ready():
    emoji_server = client.get_guild(int(os.getenv('emoji_server_id')))
    with open("chains_library.json", "rb") as chains_file:
        global chains
        chains = json.load(chains_file)
    await generate_emojis_for_options(emoji_server, chains)
    await chain_watchers.create_chain_watchers(chains, client)


@client.event
async def on_guild_join(server: discord.Guild):
    try:
        await server.system_channel.send("Thanks for inviting me to your server. To get started, "
                                         "have an administrator use /help")
    except TypeError:
        pass


@client.slash_command(name="help",
                      description="Get help and learn how to setup a notification.",
                      default_permission=True)
@commands.has_guild_permissions(administrator=True)
async def bot_help(inter: discord.ApplicationCommandInteraction):
    await inter.send("This bot works by creating webhooks for each chain that a notification is required for. "
                     "\nTo create a notification use **/create_notification** and follow the prompts."
                     "\n To delete previously made notifications, use **/delete_notifications**.", ephemeral=True)


@client.slash_command(name="create_notification",
                      description="Create a notification for a chain's referendums.",
                      default_permission=True)
@commands.has_guild_permissions(administrator=True)
async def create_notification_interface(inter: discord.ApplicationCommandInteraction):
    chains_selection = discord.ui.Select(placeholder='Chain', options=await get_chain_options())
    channel_options = discord.ui.Select(placeholder='Channel to notify', options=await get_channel_options(inter.guild))

    ping_options = await get_role_options(inter.guild,)
    max_pings = 5 if len(ping_options) > 5 else len(ping_options)
    ping_option = discord.ui.Select(placeholder='OPTIONAL: Select a role to ping in notifications',
                                    options=ping_options,
                                    min_values=0,
                                    max_values=max_pings)

    chains_selection.callback = chain_selection_callback
    channel_options.callback = channel_selection_callback
    ping_option.callback = ping_selection_callback

    accept_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Create Notification")
    cancel_button = discord.ui.Button(style=discord.ButtonStyle.gray, label="Cancel Creation")

    accept_button.callback = create_webhook
    cancel_button.callback = cancel_creation

    control_view = WebhookInteractionView(timeout=300)
    for item in [chains_selection, channel_options, ping_option, accept_button, cancel_button]:
        control_view.add_item(item)

    message = "Select which chain you would like this notification to be for, then select a channel you " \
              "would like the notification to be posted into. Finally, you may optionally select up to 5 roles to be " \
              "mentioned when the notifications are posted."

    await inter.send(content=message, view=control_view)
    control_view.message = await inter.original_message()


@client.slash_command(name="delete_notifications",
                      description="Delete a previously made notification.",
                      default_permission=True)
@commands.has_guild_permissions(administrator=True)
async def delete_notification(inter: discord.ApplicationCommandInteraction):
    webhook_options = await get_webhook_options(inter.guild)
    if len(webhook_options) == 0:
        await inter.send(content="There are no webhooks to delete.")
        return
    max_options = 25 if len(webhook_options) > 25 else len(webhook_options)
    webhook_selection = discord.ui.Select(placeholder='Notification', options=webhook_options, max_values=max_options)
    webhook_selection.callback = delete_webhooks
    view = WebhookInteractionView(timeout=300)
    view.add_item(webhook_selection)
    await inter.send(content="Select the webhooks to delete. You may select multiple", view=view)
    view.message = await inter.original_message()


async def get_chain_options():
    options = []
    for chain in chains:
        options.append(discord.SelectOption(label=chain, value=chain, emoji=generate_emojis.emojis[chain]))
    return options


async def get_channel_options(server: discord.Guild):
    options = []
    for channel in server.text_channels:
        options.append(discord.SelectOption(label=channel.name, value=str(channel.id)))
    return options


async def get_role_options(server: discord.Guild):
    options = []
    for role in server.roles[::-1]:
        options.append(discord.SelectOption(label=role.name, value=str(role.id)))
    return options


async def get_webhook_options(server: discord.Guild):
    bot_webhooks = [webhook for webhook in await server.webhooks() if webhook.user == client.user]
    options = []
    db = sqlite3.connect("webhooks.db")
    c = db.cursor()
    for webhook in bot_webhooks:
        c.execute('''SELECT chain FROM webhooks WHERE id = ?''', (webhook.id,))
        row = c.fetchone()
        chain = row[0]
        options.append(discord.SelectOption(label=f"{webhook.name} in #{webhook.channel.name}.",
                                            value=str(webhook.id),
                                            emoji=generate_emojis.emojis[chain]))
    db.close()
    return options


async def create_webhook(inter: discord.MessageInteraction):
    server = inter.guild
    entered_values = interface_messages_to_be_processed[inter.message.id]
    if entered_values.channel_option is None or entered_values.chain_selection_option is None:
        await inter.send("Both a chain and channel must be selected. Please try again.")
        return
    chain_name = entered_values.chain_selection_option
    chain = chains[chain_name]
    channel = server.get_channel(int(entered_values.channel_option))
    pings = ','.join(entered_values.ping_options)

    with open(f".//chain_logos//{chain['logo_file']}", "rb") as fp:
        image = fp.read()

    try:
        webhook = await channel.create_webhook(name=f"{chain_name} Governance Notify", avatar=image)
    except discord.Forbidden:
        await inter.send("The webhook could not be created due to invalid bot permissions.")
        return

    db = sqlite3.connect("webhooks.db")

    try:
        c = db.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS webhooks
            (chain STRING, id INTEGER PRIMARY KEY, guild_id INTEGER, token STRING, url STRING, pings STRING)''')

        c.execute('''INSERT INTO webhooks (chain, id, guild_id, token, url, pings)
             VALUES (?, ?, ?, ?, ?, ?)''', (chain_name, webhook.id,
                                            webhook.guild_id, webhook.token,
                                            webhook.url, pings))

        db.commit()
        await inter.send("Webhook has been successfully created.")
    except sqlite3.DatabaseError:
        await inter.send("The webhook creation failed.")
        raise
    finally:
        db.close()
    interface_messages_to_be_processed.pop(inter.message.id)
    await webhook.send("test")


async def delete_webhooks(inter: discord.MessageInteraction):
    selected_webhooks = [int(webhook_id) for webhook_id in inter.values]
    for webhook in await inter.guild.webhooks():
        if webhook.id in selected_webhooks:
            try:
                db = sqlite3.connect("webhooks.db")
                c = db.cursor()
                c.execute('''DELETE FROM webhooks WHERE id = ?''', (webhook.id,))
                db.commit()
                webhook_name = webhook.name
                await webhook.delete()
                await inter.send(f"Webhook {webhook_name} deleted successfully")
            except sqlite3.DatabaseError:
                await inter.send(f"Webhook {webhook_name} could not delete successfully")
            finally:
                db.close()


async def cancel_creation(inter: discord.MessageInteraction):
    await inter.message.delete()


async def chain_selection_callback(inter: discord.MessageInteraction):
    interface_messages_to_be_processed[inter.message.id].chain_selection_option = inter.values[0]
    await inter.response.defer()


async def channel_selection_callback(inter: discord.MessageInteraction):
    interface_messages_to_be_processed[inter.message.id].channel_option = inter.values[0]
    await inter.response.defer()


async def ping_selection_callback(inter: discord.MessageInteraction):
    interface_messages_to_be_processed[inter.message.id].ping_options = inter.values
    await inter.response.defer()


def start():
    client.run(bot_token)


if __name__ == '__main__':
    start()
