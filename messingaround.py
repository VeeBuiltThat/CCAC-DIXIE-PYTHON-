import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
from random import uniform

CREATOR_ID = 766005564190359552
SERVER_ID = 1240448660266029126

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if DISCORD_TOKEN is None:
    raise ValueError('Bot token not found. Please ensure the token variable is set correctly.')

@bot.event
async def on_ready():
    print(f'Yo, It\'s me, {bot.user}')

@bot.command()
async def send(ctx, channel_id: int, *, message: str):
    """Send a message to a specific channel"""
    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)  
        await channel.send(message)
        await ctx.send(f"Message sent to channel {channel.name} successfully!")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

PRETEND_THREAD_ID = 1379772245374664807
CC_THREAD_ID = 1379772874990157925
active_pretend_channels = {}
active_cc_conversations = {}

@bot.command()
async def pretend(ctx, channel_id: int):
    """Set up message forwarding from DMs to specified channel (Creator only)"""
    if not isinstance(ctx.channel, discord.DMChannel) or ctx.author.id != CREATOR_ID:
        return

    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)
        active_pretend_channels[ctx.channel.id] = channel_id
        await ctx.message.add_reaction('✅')
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command()
async def cc(ctx, user_id: int, *, message: str):
    """Send a message to a user and track their response"""
    if ctx.channel.id != CC_THREAD_ID:
        return

    try:
        user = await bot.fetch_user(user_id)
        if user is None:
            await ctx.send("Could not find the specified user.")
            return

        embed = discord.Embed(description=message, color=discord.Color.blue())
        embed.set_author(name="Message from Staff")
        await user.send(embed=embed)

        active_cc_conversations[user.id] = ctx.channel.id
        await ctx.send(f"Message sent to {user.name}#{user.discriminator}")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if isinstance(message.channel, discord.DMChannel) and message.author.id == CREATOR_ID and not message.content.startswith('!'):
        channel_id = active_pretend_channels.get(message.channel.id)
        if channel_id:
            try:
                channel = bot.get_channel(channel_id)
                if channel is None:
                    channel = await bot.fetch_channel(channel_id)

                delay = min(2 + len(message.content) * 0.02, 10)
                async with channel.typing():
                    await asyncio.sleep(delay)
                    await channel.send(f"{message.content}")
            except Exception as e:
                print(f"Failed to forward pretend message: {e}")

    elif isinstance(message.channel, discord.DMChannel):
        thread_id = active_cc_conversations.get(message.author.id)
        if thread_id:
            try:
                thread = bot.get_channel(thread_id)
                if thread is None:
                    thread = await bot.fetch_channel(thread_id)

                delay = min(2 + len(message.content) * 0.02, 10)
                async with thread.typing():
                    await asyncio.sleep(delay)
                    if len(message.content) <= 4000:
                        embed = discord.Embed(
                            description=message.content,
                            color=discord.Color.green()
                        )
                        embed.set_author(name=f"Response from {message.author.name}#{message.author.discriminator}")
                        await thread.send(embed=embed)
                    else:
                        await thread.send(f"**Response from {message.author.name}#{message.author.discriminator}:**\n{message.content}")
            except Exception as e:
                print(f"Failed to forward CC response: {e}")

try:
    bot.run(DISCORD_TOKEN)
except discord.errors.LoginFailure as e:
    print(f"Failed to log in: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
