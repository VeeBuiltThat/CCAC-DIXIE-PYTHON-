import discord
from discord.ext import commands
from discord import Embed
from datetime import datetime, timezone, timedelta
from config import ALERT_CHANNEL_ID, GUILD_ID

class BotDetection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_suspicious(self, member: discord.Member) -> list:
        """Returns a list of reasons why this member might be suspicious."""
        reasons = []
        now = datetime.now(timezone.utc)

        if (now - member.created_at) < timedelta(days=7):
            reasons.append(f"Account is very new (created {member.created_at.strftime('%Y-%m-%d')})")

        if member.display_avatar.is_default():
            reasons.append("User has a default Discord avatar")

        suspicious_patterns = ["bot", "test", "spam"]
        if any(pat in member.name.lower() for pat in suspicious_patterns):
            reasons.append("⚠️ Username contains suspicious keywords")

        return reasons

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != GUILD_ID:
            return

        now = datetime.now(timezone.utc)
        account_age = now - member.created_at

        if account_age < timedelta(days=14):
            try:
                await member.send(
                    "Your account is too young. Please make sure your account is at least 14 days old. "
                    "You may rejoin after your account reaches this age."
                )
            except discord.Forbidden:
                pass 

            try:
                await member.kick(reason="Account younger than 14 days")
            except discord.Forbidden:
                pass  
            return  

        reasons = self.is_suspicious(member)
        if reasons:
            channel = self.bot.get_channel(ALERT_CHANNEL_ID)
            if channel:
                embed = Embed(
                    title="🚨 Possible Bot Detected",
                    description="Please review this new member.",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
                embed.add_field(
                    name="Joined",
                    value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown",
                    inline=True
                )
                embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
                embed.add_field(name="Suspicious Signs", value="\n".join(reasons), inline=False)
                embed.set_thumbnail(url=member.display_avatar.url)

                await channel.send(embed=embed)  

async def setup(bot):
    await bot.add_cog(BotDetection(bot))
