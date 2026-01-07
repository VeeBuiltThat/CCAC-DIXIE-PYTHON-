import discord
from discord.ext import commands
import asyncio

class AntiForward(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.protected_channels = [
            1244399296279740558, 1240456287473369170, 1243567743538561064,
            1243567946605793353, 1243567701088145538, 1240456357149409361,
            1248017633907834970, 1246266893925482641, 1243567009564721243,
            1244400051879546930
        ]
        self.delete_after_seconds = 30
        self.notice_duration = 5
        self.ignored_bot_id = 1244337100770250802

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.author.id == self.ignored_bot_id:
            return

        if message.channel.id in self.protected_channels:
            if message.type == discord.MessageType.reply or message.reference:
                # Delete the forwarded message first
                try:
                    await message.delete()
                except discord.Forbidden:
                    print("Missing permission to delete messages.")
                except discord.NotFound:
                    pass  # already deleted

                # Send a short-lived in-channel notice that pings the user
                try:
                    notice = await message.channel.send(
                        f"{message.author.mention} Forwarded messages are not allowed in this channel."
                    )
                    await asyncio.sleep(self.notice_duration)
                    await notice.delete()
                except discord.Forbidden:
                    print("Missing permission to send/delete notices.")
                except Exception as e:
                    print(f"Failed to send/delete notice: {e}")


async def setup(bot):
    await bot.add_cog(AntiForward(bot))