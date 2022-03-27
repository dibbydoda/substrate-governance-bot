import chains_library
import disnake as discord


async def generate_emojis_for_options(emoji_server: discord.Guild):
    print("Starting to process emojis")
    for emoji in emoji_server.emojis:
        await emoji.delete()

    for chain in chains_library.chains:
        with open(f".//chain_logos//{chain.logo_file}", "rb") as fp:
            image = fp.read()
        chain.emoji = await emoji_server.create_custom_emoji(name=chain.name, image=image)

    print("Finished processing emojis")
