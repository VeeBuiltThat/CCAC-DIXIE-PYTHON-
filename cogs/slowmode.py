import discord
from discord.ext import commands
import aiomysql
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


load_dotenv()

# Database credentials
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")



class CustomSlowmode(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_pool = None
        self.channel_durations = {}  
        
        
    async def setup_db(self):
        """Create the connection pool and ensure table exists."""
        self.db_pool = await aiomysql.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            autocommit=True
        )

        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS custom_slowmode (
                        guild_id BIGINT,
                        channel_id BIGINT,
                        user_id BIGINT,
                        end_time DATETIME,
                        duration_seconds INT,
                        PRIMARY KEY (guild_id, channel_id, user_id)
                    );
                """)
        print("MySQL slowmode table ready.")

    async def cog_load(self):
        await self.setup_db()


    def format_timedelta(self, delta: timedelta):
        total = int(delta.total_seconds())
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        if seconds: parts.append(f"{seconds}s")
        return " ".join(parts) or "0s"

    async def get_cooldown(self, guild_id, channel_id, user_id):
        """Retrieve cooldown from database."""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT end_time, duration_seconds
                    FROM custom_slowmode
                    WHERE guild_id=%s AND channel_id=%s AND user_id=%s
                """, (guild_id, channel_id, user_id))
                row = await cur.fetchone()
                if row:
                    return row[0], timedelta(seconds=row[1])
        return None, None

    async def set_cooldown(self, guild_id, channel_id, user_id, duration: timedelta):
        """Insert or update user cooldown in DB."""
        end_time = datetime.utcnow() + duration
        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    REPLACE INTO custom_slowmode
                    (guild_id, channel_id, user_id, end_time, duration_seconds)
                    VALUES (%s, %s, %s, %s, %s)
                """, (guild_id, channel_id, user_id, end_time, int(duration.total_seconds())))

    async def delete_cooldown(self, guild_id, channel_id, user_id):
        """Remove user cooldown."""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    DELETE FROM custom_slowmode
                    WHERE guild_id=%s AND channel_id=%s AND user_id=%s
                """, (guild_id, channel_id, user_id))


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        channel_id = message.channel.id
        user_id = message.author.id

        if channel_id not in self.channel_durations:
            return

        duration = self.channel_durations[channel_id]


        end_time, _ = await self.get_cooldown(guild_id, channel_id, user_id)

        now = datetime.utcnow()

        if end_time and now < end_time:

            await message.delete()
            remaining = self.format_timedelta(end_time - now)
            try:
                await message.author.send(
                    f"⏳ You are still on slowmode in **#{message.channel.name}**.\n"
                    f"You can send another message in **{remaining}**."
                )
            except discord.Forbidden:
                pass
            return
        else:

            await self.set_cooldown(guild_id, channel_id, user_id, duration)

        await self.bot.process_commands(message)


    @commands.command(name="setslowmode")
    @commands.has_permissions(manage_channels=True)
    async def set_slowmode(self, ctx, hours: float = 0, minutes: float = 0):
        """Set custom slowmode for this channel."""
        if hours == 0 and minutes == 0:
            self.channel_durations.pop(ctx.channel.id, None)
            await ctx.send("Custom slowmode disabled for this channel.")
            return

        duration = timedelta(hours=hours, minutes=minutes)
        self.channel_durations[ctx.channel.id] = duration
        await ctx.send(f"Custom slowmode set to `{self.format_timedelta(duration)}`.")

    @commands.command(name="resetslow")
    @commands.has_permissions(manage_channels=True)
    async def reset_slow(self, ctx, member: discord.Member):
        """Reset a user's cooldown in this channel."""
        await self.delete_cooldown(ctx.guild.id, ctx.channel.id, member.id)
        await ctx.send(f"Cooldown reset for {member.mention}.")

    @commands.command(name="slowstatus")
    async def slow_status(self, ctx):
        """Show the current slowmode duration for this channel."""
        duration = self.channel_durations.get(ctx.channel.id)
        if not duration:
            await ctx.send("No custom slowmode is active here.")
        else:
            await ctx.send(f"Custom slowmode: `{self.format_timedelta(duration)}`.")


async def setup(bot):
    await bot.add_cog(CustomSlowmode(bot))
