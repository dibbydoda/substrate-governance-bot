import disnake as discord
import governancebot

emojis = {}


async def generate_emojis_for_options(emoji_server: discord.Guild, chains):
    print("Starting to process emojis")
    for emoji in emoji_server.emojis:
        await emoji.delete()

    for chain_tuple in chains.items():
        chain = governancebot.Chain._make(chain_tuple)
        with open(f".//chain_logos//{chain.properties['logo_file']}", "rb") as fp:
            image = fp.read()
        emoji = await emoji_server.create_custom_emoji(name=chain.name, image=image)
        emojis[chain.name] = emoji

    print("Finished processing emojis")
