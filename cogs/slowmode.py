import discord
from discord.ext import commands
import aiomysql
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv


# Try a package-relative import; fall back to environment variables if unavailable
try:
    from .config import DB_HOST as CFG_DB_HOST, DB_PORT as CFG_DB_PORT, DB_NAME as CFG_DB_NAME, DB_USER as CFG_DB_USER, DB_PASSWORD as CFG_DB_PASSWORD
except Exception:
    CFG_DB_HOST = CFG_DB_PORT = CFG_DB_NAME = CFG_DB_USER = CFG_DB_PASSWORD = None

load_dotenv()

DB_HOST = os.getenv("DB_HOST") or CFG_DB_HOST
DB_PORT = int(os.getenv("DB_PORT", CFG_DB_PORT if CFG_DB_PORT is not None else 3306))
DB_NAME = os.getenv("DB_NAME") or CFG_DB_NAME
DB_USER = os.getenv("DB_USER") or CFG_DB_USER
DB_PASSWORD = os.getenv("DB_PASSWORD") or CFG_DB_PASSWORD


class CustomSlowmode(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_pool = None
        self.channel_durations = {}  

    async def setup_db(self):
        """Create the connection pool and ensure tables exist."""
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
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS slowmode_channels (
                        guild_id BIGINT,
                        channel_id BIGINT,
                        duration_seconds INT,
                        PRIMARY KEY (guild_id, channel_id)
                    );
                """)
        print("MySQL slowmode tables ready.")

    async def load_channel_durations(self):
        """Load persisted channel slowmode settings into memory."""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT guild_id, channel_id, duration_seconds
                    FROM slowmode_channels
                """)
                rows = await cur.fetchall()
                for guild_id, channel_id, duration_seconds in rows:
                    # store as timedelta in memory
                    self.channel_durations[int(channel_id)] = timedelta(seconds=duration_seconds)
        print(f"Loaded {len(self.channel_durations)} channel slowmode settings from DB.")

    async def cog_load(self):
        await self.setup_db()
        await self.load_channel_durations()

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

    async def set_channel_duration_db(self, guild_id, channel_id, duration: timedelta):
        """Persist channel slowmode setting."""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    REPLACE INTO slowmode_channels (guild_id, channel_id, duration_seconds)
                    VALUES (%s, %s, %s)
                """, (guild_id, channel_id, int(duration.total_seconds())))

    async def delete_channel_duration_db(self, guild_id, channel_id):
        """Delete persisted channel slowmode setting."""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    DELETE FROM slowmode_channels
                    WHERE guild_id=%s AND channel_id=%s
                """, (guild_id, channel_id))

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
        """Set custom slowmode for this channel and persist it."""
        if hours == 0 and minutes == 0:
            # disable
            self.channel_durations.pop(ctx.channel.id, None)
            await self.delete_channel_duration_db(ctx.guild.id, ctx.channel.id)
            await ctx.send("Custom slowmode disabled for this channel.")
            return

        duration = timedelta(hours=hours, minutes=minutes)
        self.channel_durations[ctx.channel.id] = duration
        await self.set_channel_duration_db(ctx.guild.id, ctx.channel.id, duration)
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
            await ctx.send(f"Custom slowmode: `{self.format_timedelta(duration)}` (persisted).")


async def setup(bot):
    await bot.add_cog(CustomSlowmode(bot))
