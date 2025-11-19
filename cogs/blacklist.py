import discord
from discord.ext import commands
import mysql.connector
from mysql.connector import Error
import datetime
from typing import Union

from config import MOD_HOST, MOD_PORT, MOD_DATABASE, MOD_USER, MOD_PASSWORD
from config import BLACKLIST_LOG_CHANNEL_ID, ALLOWED_ROLES, NOTIFY_ROLE_ID


def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=MOD_HOST,
            port=MOD_PORT,
            database=MOD_DATABASE,
            user=MOD_USER,
            password=MOD_PASSWORD
        )
        return conn
    except Error as e:
        print(f"❌ Database connection error: {e}")
        return None


def add_blacklist(user_id, username, reason):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO blacklist (user_id, username, reason, blacklist_date) VALUES (%s, %s, %s, %s)",
            (user_id, username, reason, datetime.datetime.utcnow())
        )
        conn.commit()
        cursor.close()
        conn.close()


def get_blacklist(user_id):
    conn = get_db_connection()
    results = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM blacklist WHERE user_id = %s", (user_id,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
    return results


class Blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="blacklist")
    @commands.has_any_role(*ALLOWED_ROLES)  
    async def blacklist(self, ctx, user: Union[discord.Member, discord.User] = None, *, reason: str = None):
        if user is None or reason is None:
            return await ctx.send("❌ Usage: `!blacklist <user @mention/user_id> <reason>`")

        add_blacklist(user.id, str(user), reason)
        try:
            dm_embed = discord.Embed(
                title="You have been blacklisted",
                description=f"Reason: **{reason}**\n\nYou are no longer allowed in **{ctx.guild.name}**.",
                color=discord.Color.red()
            )
            await user.send(embed=dm_embed)
        except Exception:
            pass

        try:
            await ctx.guild.ban(user, reason=f"Blacklisted: {reason}")
        except discord.Forbidden:
            return await ctx.send("I don't have permission to ban this user.")
        except discord.HTTPException:
            return await ctx.send("Failed to ban the user due to a Discord error.")

        embed = discord.Embed(
            title="User Blacklisted & Banned",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Username", value=f"{user}", inline=False)
        embed.add_field(name="User ID", value=f"{user.id}", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url if hasattr(user, "display_avatar") else discord.Embed.Empty)

        log_channel = ctx.guild.get_channel(BLACKLIST_LOG_CHANNEL_ID)
        if log_channel:
            role_ping = f"<@&{NOTIFY_ROLE_ID}>" 
            await log_channel.send(role_ping, embed=embed)

        await ctx.send(f"{user} has been blacklisted **and banned** for: {reason}")


    @commands.command(name="blacklistcheck")
    async def blacklistcheck(self, ctx, user_id: int):
        """Check blacklist records for a user"""
        records = get_blacklist(user_id)
        if not records:
            await ctx.send("No blacklist records found for this user.")
            return

        for record in records:
            embed = discord.Embed(
                title="Blacklist Record",
                color=discord.Color.orange()
            )
            embed.add_field(name="Username", value=record["username"], inline=True)
            embed.add_field(name="User ID", value=record["user_id"], inline=True)
            embed.add_field(name="Reason", value=record["reason"], inline=False)
            embed.add_field(name="Date", value=record["date"], inline=True)
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Blacklist(bot))
