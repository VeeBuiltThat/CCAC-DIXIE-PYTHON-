import sys
import os
import asyncio
import discord
from discord.ext import commands
from discord.utils import utcnow
import mysql.connector
import datetime  # unified import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from dbconnMOD import add_mod_log, get_warnings, remove_warning, get_notes, add_note_to_db

# Load role IDs from environment
JRMOD_ROLE_ID = int(os.getenv('JRMOD_ROLE_ID', 0))
MODS_ROLE_ID = int(os.getenv('MODS_ROLE_ID', 0))
ADMINS_ROLE_ID = int(os.getenv('ADMINS_ROLE_ID', 0))
CO_OWNERS_ROLE_ID = int(os.getenv('CO_OWNERS_ROLE_ID', 0))
OWNERS_ROLE_ID = int(os.getenv('OWNERS_ROLE_ID', 0))
BOT_MANAGER_ID = int(os.getenv('BOT_MANAGER_ID', 0))

print(f"Loaded Role IDs: {JRMOD_ROLE_ID}, {MODS_ROLE_ID}, {ADMINS_ROLE_ID}, {CO_OWNERS_ROLE_ID}, {OWNERS_ROLE_ID}, {BOT_MANAGER_ID}")
MODLOG_CHANNEL_ID = 1429427574085517353

todo_lists = {}

def has_role_ids(*role_ids):
    """Custom check for role IDs instead of names"""
    async def predicate(ctx):
        return any(r.id in role_ids for r in ctx.author.roles)
    return commands.check(predicate)



MOD_HOST = 'gameswaw1.bisecthosting.com'
MOD_PORT = 3306
MOD_DATABASE = 's404394_DixieModerator'
MOD_USER = 'u404394_zpDXmPyRMs'
MOD_PASSWORD = 's8HvVfGoqUpl9LRGVShnqzOk'


def get_db_connection():
    return mysql.connector.connect(
        host=MOD_HOST,
        port=MOD_PORT,
        database=MOD_DATABASE,
        user=MOD_USER,
        password=MOD_PASSWORD,
        autocommit=True
    )

def init_todo_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            task TEXT NOT NULL,
            reminder_time DATETIME NULL,
            created_at DATETIME NOT NULL
        )
    """)
    cursor.close()
    conn.close()

init_todo_db()

def add_todo_to_db(user_id: int, task: str, reminder_time: datetime.datetime = None) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO todos (user_id, task, reminder_time, created_at) VALUES (%s, %s, %s, %s)",
            (
                user_id,
                task,
                reminder_time.strftime("%Y-%m-%d %H:%M:%S") if reminder_time else None,
                datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding todo: {e}")
        return False

def get_user_todos(user_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, task, reminder_time, created_at FROM todos WHERE user_id = %s ORDER BY created_at ASC",
            (user_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        todos = []
        for row in rows:
            reminder_dt = row['reminder_time']
            todos.append({
                "id": row['id'],
                "task": row['task'],
                "reminder_time": reminder_dt, 
                "created_at": row['created_at']
            })
        return todos
    except Exception as e:
        print(f"Error fetching todos: {e}")
        return []



class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_modlog_embed(self, action: str, target_user: discord.User, moderator: discord.Member,
                            reason: str = None, extra_info: str = None, channel: discord.TextChannel = None):
        """Sends all moderation action logs to the mod-log channel."""

        modlog_channel = self.bot.get_channel(MODLOG_CHANNEL_ID)
        if not modlog_channel:
            print(f"[ERROR] Modlog channel {MODLOG_CHANNEL_ID} not found.")
            return

        color = {
            "ban": discord.Color.red(),
            "kick": discord.Color.red(),
            "timeout": discord.Color.orange(),
            "timeout removed": discord.Color.green(),
            "wmajor": discord.Color.red(),
            "wminor": discord.Color.orange(),
            "note": discord.Color.blue(),
            "purge": discord.Color.purple(),
            "slowmode set": discord.Color.orange(),
            "slowmode removed": discord.Color.green(),
            "unban": discord.Color.green(),
        }.get(action.lower(), discord.Color.blurple())

        embed = discord.Embed(
            title=f"Moderation Action: {action.capitalize()}",
            color=color,
            timestamp=datetime.datetime.utcnow()
        )

        if hasattr(target_user, "avatar") and target_user.avatar:
            embed.set_thumbnail(url=target_user.avatar.url)

        embed.add_field(name="User", value=f"{target_user} ({target_user.id})", inline=True)
        embed.add_field(name="Moderator", value=f"{moderator} ({moderator.id})", inline=True)

        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if channel:
            embed.add_field(name="Channel", value=channel.mention, inline=False)
        if extra_info:
            embed.add_field(name="Extra Info", value=extra_info, inline=False)

        embed.set_footer(text=f"IDs: User {target_user.id} | Mod {moderator.id} | UTC")

        try:
            await modlog_channel.send(embed=embed)
        except Exception as e:
            print(f"[ERROR] Failed to send mod log: {e}")


    @commands.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, count: int):
        if not (1 <= count <= 100):
            return await ctx.send(embed=discord.Embed(description="Please provide a number between 1 and 100.", color=discord.Color.red()))
        deleted = await ctx.channel.purge(limit=count)
        await ctx.send(embed=discord.Embed(description=f"🧹 Purged {len(deleted)} messages.", color=discord.Color.green()), delete_after=5)
        await self.send_modlog_embed("Purge", ctx.author, ctx.author, extra_info=f"Deleted {len(deleted)} messages", channel=ctx.channel)

    @commands.command(name="slow")
    @commands.has_permissions(manage_channels=True)
    async def slow(self, ctx, duration: int, unit: str):
        unit = unit.lower()
        multipliers = {"second": 1, "seconds": 1, "minute": 60, "minutes": 60,
                       "hour": 3600, "hours": 3600, "day": 86400, "days": 86400}
        if unit not in multipliers:
            return await ctx.send(embed=discord.Embed(description="Invalid unit. Use seconds, minutes, hours, or days.", color=discord.Color.red()))
        seconds = duration * multipliers[unit]
        if seconds > 21600:
            return await ctx.send(embed=discord.Embed(description="Slowmode cannot exceed 6 hours (21600 seconds).", color=discord.Color.red()))
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(embed=discord.Embed(description=f"🐢 Slowmode set to {duration} {unit}.", color=discord.Color.orange()))
        await self.send_modlog_embed("Slowmode Set", ctx.author, ctx.author, extra_info=f"Set to {duration} {unit}", channel=ctx.channel)

    @commands.command(name="slowremove")
    @commands.has_permissions(manage_channels=True)
    async def slowremove(self, ctx):
        await ctx.channel.edit(slowmode_delay=0)
        await ctx.send(embed=discord.Embed(description="✅ Slowmode removed from this channel.", color=discord.Color.green()))
        await self.send_modlog_embed("Slowmode Removed", ctx.author, ctx.author, channel=ctx.channel)

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int, *, reason: str):
        user = await self.bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        embed = discord.Embed(title="User Unbanned", color=discord.Color.green())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
        embed.add_field(name="Unbanned by", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
        add_mod_log(user.id, reason, ctx.author.id, "unban")
        await self.send_modlog_embed("Unban", user, ctx.author, reason=reason)

    @commands.command(name="timeremove")
    @commands.has_permissions(moderate_members=True)
    async def timeremove(self, ctx, user_id: int):
        member = ctx.guild.get_member(user_id)
        if not member:
            return await ctx.send(embed=discord.Embed(description="User not found in this server.", color=discord.Color.red()))
        await member.edit(timed_out_until=None)
        await ctx.send(embed=discord.Embed(description=f"⏱️ Timeout removed for {member.mention}.", color=discord.Color.green()))
        add_mod_log(member.id, "Timeout removed", ctx.author.id, "timeremove")
        await self.send_modlog_embed("Timeout Removed", member, ctx.author)

    @commands.command(name="todo")
    async def todo(self, ctx, task: str, reminder: str = None):
        reminder_dt = None
        if reminder:
            try:
                h, m = map(int, reminder.split(":"))
                now = datetime.datetime.now()
                reminder_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if reminder_dt < now:
                    reminder_dt += datetime.timedelta(days=1)
            except:
                return await ctx.send(embed=discord.Embed(description="Invalid reminder format. Use HH:MM.", color=discord.Color.red()))
        add_todo_to_db(ctx.author.id, task, reminder_dt)
        await ctx.send(embed=discord.Embed(description=f"📝 Added to your to-do list: `{task}`", color=discord.Color.blue()))
        if reminder_dt:
            delay = (reminder_dt - datetime.datetime.now()).total_seconds()
            asyncio.create_task(self.send_reminder(ctx.author, task, delay))

    async def send_reminder(self, user: discord.User, task: str, delay: float):
        await asyncio.sleep(delay)
        try:
            await user.send(f"⏰ Reminder: `{task}`")
        except discord.Forbidden:
            pass

    @commands.command(name="todoshow")
    async def todoshow(self, ctx):
        todos = get_user_todos(ctx.author.id)
        if not todos:
            return await ctx.send(embed=discord.Embed(description="You have no todos.", color=discord.Color.blue()))
        description = ""
        for i, t in enumerate(todos, 1):
            desc = f"{i}. {t['task']}"
            if t.get("reminder_time"):
                desc += f" {t['reminder_time'].strftime('%H:%M')}"
            description += desc + "\n"
        await ctx.send(embed=discord.Embed(title="Your Todo List", description=description, color=discord.Color.blue()))


    # !whois <userID>
    @commands.command(name="whois")
    async def whois(self, ctx, user_id: int = None):
        """Shows user information, warnings, roles, and mod notes with a button to view notes."""
        member = None
        user = None

        # Fetch member or user
        if user_id:
            member = ctx.guild.get_member(user_id)
            if not member:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    return await ctx.send(embed=discord.Embed(
                        description="User not found.", color=discord.Color.red()
                    ))
        else:
            member = ctx.author

        if member:
            username = member.name
            user_id = member.id
            created_at = member.created_at.replace(tzinfo=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            joined_at = member.joined_at.replace(tzinfo=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            roles = ", ".join([role.mention for role in member.roles if role.name != "@everyone"]) or "None"
            avatar_url = member.avatar.url if member.avatar else None
        else:
            username = user.name
            user_id = user.id
            created_at = user.created_at.replace(tzinfo=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            joined_at = "Not in server"
            roles = "Not in server"
            avatar_url = user.avatar.url if user.avatar else None

        minor_warnings, major_warnings = get_warnings(user_id)
        notes = get_notes(user_id)

        embed = discord.Embed(title=f"User Info - {username}", color=discord.Color.blue())
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="Username", value=username, inline=True)
        embed.add_field(name="User ID", value=user_id, inline=True)
        embed.add_field(name="Account Created", value=created_at, inline=False)
        embed.add_field(name="Joined Server", value=joined_at, inline=False)
        embed.add_field(name="Roles", value=roles, inline=False)
        embed.add_field(name="Minor Warnings", value=str(len(minor_warnings)), inline=True)
        embed.add_field(name="Major Warnings", value=str(len(major_warnings)), inline=True)

        if notes:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="View Notes",
                style=discord.ButtonStyle.secondary,
                custom_id=f"view_notes_{user_id}"
            ))
            embed.add_field(name="Mod Notes", value="Click the button below to view notes.", inline=False)
            await ctx.send(embed=embed, view=view)
        else:
            embed.add_field(name="Mod Notes", value="None", inline=False)
            await ctx.send(embed=embed)

    @commands.command(name="wlist")
    async def wlist(self, ctx, user_id: int):
        minor_warnings, major_warnings = get_warnings(user_id)
        embed = discord.Embed(title=f"Warnings for <@{user_id}>", color=discord.Color.orange())

        if minor_warnings:
            value = "\n".join(
                f"{i+1}. [{w['log_id']}] {w['reason']} - by <@{w['mod_id']}> - {w['date'].strftime('%d/%m/%Y')}"
                for i, w in enumerate(minor_warnings)
            )
            embed.add_field(name="Minor Warnings", value=value, inline=False)
        else:
            embed.add_field(name="Minor Warnings", value="None", inline=False)

        if major_warnings:
            value = "\n".join(
                f"{i+1}. [{w['log_id']}] {w['reason']} - by <@{w['mod_id']}> - {w['date'].strftime('%d/%m/%Y')}"
                for i, w in enumerate(major_warnings)
            )
            embed.add_field(name="Major Warnings", value=value, inline=False)
        else:
            embed.add_field(name="Major Warnings", value="None", inline=False)

        await ctx.send(embed=embed)


    # !note <user_ID> <message>
    @commands.command(name="note")
    @commands.has_any_role(MODS_ROLE_ID, ADMINS_ROLE_ID, CO_OWNERS_ROLE_ID, OWNERS_ROLE_ID, BOT_MANAGER_ID)
    async def note(self, ctx, user_id: int, *, message: str):
        if add_note_to_db(user_id, message):
            await ctx.send(embed=discord.Embed(description=f"✅ Added note for <@{user_id}>.", color=discord.Color.green()))
        else:
            await ctx.send(embed=discord.Embed(description=f"❌ Failed to add note.", color=discord.Color.red()))

    # !timeout <userID> <duration> <unit> <reason>
    @commands.command(name="timeout")
    @commands.has_any_role(JRMOD_ROLE_ID, MODS_ROLE_ID, ADMINS_ROLE_ID, CO_OWNERS_ROLE_ID, OWNERS_ROLE_ID, BOT_MANAGER_ID)
    async def timeout(self, ctx, user_id: int, duration: int, unit: str, *, reason="No reason provided"):
        member = ctx.guild.get_member(user_id)
        if not member:
            return await ctx.send(embed=discord.Embed(
                description="User not found in this server.",
                color=discord.Color.red()
            ))

        if unit not in ["minutes", "hours", "days"]:
            return await ctx.send(embed=discord.Embed(
                description='Invalid time unit. Please use "minutes", "hours", or "days".',
                color=discord.Color.red()
            ))

        if unit == "minutes":
            delta = datetime.timedelta(minutes=duration)
        elif unit == "hours":
            delta = datetime.timedelta(hours=duration)
        elif unit == "days":
            delta = datetime.timedelta(days=duration)

        if delta.total_seconds() > 2592000:  # 30 days
            return await ctx.send(embed=discord.Embed(
                description='Timeout duration cannot exceed 30 days. Please adjust the duration.',
                color=discord.Color.red()
            ))

        await member.edit(timed_out_until=utcnow() + delta)

        embed_channel = discord.Embed(
            title="User Timed Out",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_channel.add_field(name="User", value=member.mention, inline=True)
        embed_channel.add_field(name="Timed out by", value=ctx.author.mention, inline=True)
        embed_channel.add_field(name="Duration", value=f"{duration} {unit}", inline=True)
        embed_channel.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed_channel)

        add_mod_log(member.id, f"timeout: {duration} {unit}", ctx.author.id, "timeout")

        embed_dm = discord.Embed(
            title="You have been timed out",
            description=f"You have received a timeout in **{ctx.guild.name}**.",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_dm.add_field(name="Duration", value=f"{duration} {unit}", inline=True)
        embed_dm.add_field(name="Reason", value=reason, inline=False)
        embed_dm.set_footer(text="If you think that your timeout has been issued wrongly, please contact <@1420311570172346408>")

        try:
            await member.send(embed=embed_dm)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description=f'Could not send DM to {member.mention}, they might have DMs disabled.',
                color=discord.Color.red()
            ))


    # !wminor <userID> <reason>
    @commands.command(name="wminor")
    async def warn_minor(self, ctx, user_id: int, *, reason=None):
        member = ctx.guild.get_member(user_id)
        if not member:
            await ctx.send(embed=discord.Embed(description="User not found in this server.", color=discord.Color.red()))
            return
        await self.issue_warning(ctx, member, "minor", reason)

    # !wmajor <userID> <reason>
    @commands.command(name="wmajor")
    @commands.has_any_role(JRMOD_ROLE_ID, MODS_ROLE_ID, ADMINS_ROLE_ID, CO_OWNERS_ROLE_ID, OWNERS_ROLE_ID, BOT_MANAGER_ID)
    async def warn_major(self, ctx, user_id: int, *, reason=None):
        member = ctx.guild.get_member(user_id)
        if not member:
            await ctx.send(embed=discord.Embed(description="User not found in this server.", color=discord.Color.red()))
            return
        await self.issue_warning(ctx, member, "major", reason)

    # !wremoveminor <userID> <logID>
    @commands.command(name="wremoveminor")
    @commands.has_any_role(JRMOD_ROLE_ID, MODS_ROLE_ID, ADMINS_ROLE_ID, CO_OWNERS_ROLE_ID, OWNERS_ROLE_ID, BOT_MANAGER_ID)
    async def wremoveminor(self, ctx, user_id: int, log_id: int):
        if remove_warning(user_id, "minor", log_id):
            await ctx.send(embed=discord.Embed(description=f"✅ Successfully removed **minor** warning for user <@{user_id}> (LogID: {log_id})", color=discord.Color.green()))
        else:
            await ctx.send(embed=discord.Embed(description=f"❌ Failed to remove **minor** warning for user <@{user_id}>. Either the warning doesn't exist or there was an error.", color=discord.Color.red()))

    # !wremovemajor <userID> <logID>
    @commands.command(name="wremovemajor")
    @commands.has_any_role(JRMOD_ROLE_ID, MODS_ROLE_ID, ADMINS_ROLE_ID, CO_OWNERS_ROLE_ID, OWNERS_ROLE_ID, BOT_MANAGER_ID)
    async def wremovemajor(self, ctx, user_id: int, log_id: int):
        if remove_warning(user_id, "major", log_id):
            await ctx.send(embed=discord.Embed(description=f"✅ Successfully removed **major** warning for user <@{user_id}> (LogID: {log_id})", color=discord.Color.green()))
        else:
            await ctx.send(embed=discord.Embed(description=f"❌ Failed to remove **major** warning for user <@{user_id}>. Either the warning doesn't exist or there was an error.", color=discord.Color.red()))

    # !kick <userID> <reason>
    @commands.command(name="kick")
    @commands.has_any_role(JRMOD_ROLE_ID, MODS_ROLE_ID, ADMINS_ROLE_ID, CO_OWNERS_ROLE_ID, OWNERS_ROLE_ID, BOT_MANAGER_ID)
    async def kick(self, ctx, user_id: int, *, reason="No reason provided"):
        member = ctx.guild.get_member(user_id)
        if not member:
            return await ctx.send(embed=discord.Embed(
                description="User not found in this server.",
                color=discord.Color.red()
            ))

        await member.kick(reason=reason)
        add_mod_log(member.id, reason, ctx.author.id, "kick")

        embed_channel = discord.Embed(
            title="User Kicked",
            color=discord.Color.yellow(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_channel.add_field(name="User", value=member.mention, inline=True)
        embed_channel.add_field(name="Kicked by", value=ctx.author.mention, inline=True)
        embed_channel.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed_channel)

        embed_dm = discord.Embed(
            title="You have been kicked",
            description=f"You have been kicked from **{ctx.guild.name}**.",
            color=discord.Color.yellow(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_dm.add_field(name="Reason", value=reason, inline=False)
        embed_dm.set_footer(text="You may rejoin if allowed by the server staff.")

        try:
            await member.send(embed=embed_dm)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description=f'Could not send DM to {member.mention}, they might have DMs disabled.',
                color=discord.Color.red()
            ))


    # !ban <userID> <reason>
    @commands.command(name="ban")
    @commands.has_any_role(MODS_ROLE_ID, ADMINS_ROLE_ID, CO_OWNERS_ROLE_ID, OWNERS_ROLE_ID, BOT_MANAGER_ID)
    async def ban(self, ctx, user_id: int, *, reason="No reason provided"):
        try:
            member = ctx.guild.get_member(user_id)
            if member:

                await ctx.guild.ban(member, reason=reason)
                user_display = member.mention
                add_mod_log(member.id, reason, ctx.author.id, "ban")


                embed_dm = discord.Embed(
                    title="You have been banned",
                    description=f"You have been banned from **{ctx.guild.name}**.",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed_dm.add_field(name="Reason", value=reason, inline=False)
                embed_dm.set_footer(text="This action is permanent unless appealed.")

                try:
                    await member.send(embed=embed_dm)
                except discord.Forbidden:
                    await ctx.send(embed=discord.Embed(
                        description=f'Could not send DM to {member.mention}, they might have DMs disabled.',
                        color=discord.Color.red()
                    ))
            else:

                user = discord.Object(id=user_id)
                await ctx.guild.ban(user, reason=reason)
                user_display = f"User ID: {user_id}"
                add_mod_log(user_id, reason, ctx.author.id, "ban")

            embed_channel = discord.Embed(
                title="User Banned",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            embed_channel.add_field(name="User", value=user_display, inline=True)
            embed_channel.add_field(name="Banned by", value=ctx.author.mention, inline=True)
            embed_channel.add_field(name="Reason", value=reason, inline=False)
            await ctx.send(embed=embed_channel)

        except discord.NotFound:
            await ctx.send(embed=discord.Embed(
                description=f"User with ID `{user_id}` not found.",
                color=discord.Color.red()
            ))
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description="I don’t have permission to ban that user.",
                color=discord.Color.red()
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"An error occurred: {e}",
                color=discord.Color.red()
            ))


    async def issue_warning(self, ctx, member: discord.Member, warning_type: str, reason: str):
        if not reason:
            await ctx.send(embed=discord.Embed(
                description=f'Please provide a reason for the warning, {ctx.author.mention}.',
                color=discord.Color.red()
            ))
            return

        add_mod_log(member.id, reason, ctx.author.id, f"{warning_type}_warning")

        minor_warnings, major_warnings = get_warnings(member.id)
        total_warnings = len(minor_warnings) if warning_type == "minor" else len(major_warnings)

        embed_channel = discord.Embed(
            title=f"{warning_type.capitalize()} Warning Issued",
            color=discord.Color.orange()
        )
        embed_channel.add_field(name="User", value=member.mention, inline=True)
        embed_channel.add_field(name="Warned by", value=ctx.author.mention, inline=True)
        embed_channel.add_field(name="Reason", value=reason, inline=False)
        embed_channel.add_field(name=f"Total {warning_type.capitalize()} Warnings", value=total_warnings, inline=False)
        await ctx.send(embed=embed_channel)

        embed_dm = discord.Embed(
            title=f"You have received a {warning_type} warning",
            description=f"You have been issued a **{warning_type} warning** in **{ctx.guild.name}**.",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_dm.add_field(name="Reason", value=reason, inline=False)
        embed_dm.set_footer(text="If you believe this warning was issued in error, please contact <@1420311570172346408>")

        try:
            await member.send(embed=embed_dm)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description=f'Could not send DM to {member.mention}, they might have DMs disabled.',
                color=discord.Color.red()
            ))

async def setup(bot):
    await bot.add_cog(Mod(bot))
