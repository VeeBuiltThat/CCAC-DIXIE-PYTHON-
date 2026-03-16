import discord
from discord.ext import commands
from datetime import datetime, timezone

def format_duration(start, end):
    delta = end - start
    days, seconds = delta.days, delta.seconds
    years, days = divmod(days, 365)
    months, days = divmod(days, 30)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if years: parts.append(f"{years}y")
    if months: parts.append(f"{months}m")
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds: parts.append(f"{seconds}s")
    return " ".join(parts) or "0s"

class AuditLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = 1243662236699070545 

    def log_channel(self, guild: discord.Guild):
        return guild.get_channel(self.log_channel_id)

    def create_embed(self, title: str, description: str = None, color: discord.Color = discord.Color.blurple(), footer: str = None):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        if footer:
            embed.set_footer(text=footer)
        return embed

    async def fetch_audit_user(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int):
        try:
            async for entry in guild.audit_logs(limit=5, action=action):
                if getattr(entry.target, "id", None) == target_id:
                    return entry.user
        except discord.Forbidden:
            return None
        return None

    # ---------------- MEMBER EVENTS ----------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        log = self.log_channel(member.guild)
        if log:
            embed = self.create_embed(
                "Member Joined",
                f"**User:** {member} (`{member.id}`)\n"
                f"**Account Created:** {member.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"**Current Members:** {len(member.guild.members)}",
                discord.Color.green(),
                f"Server: {member.guild.name}"
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log = self.log_channel(member.guild)
        if log:
            join_time = member.joined_at or member.created_at
            duration = format_duration(join_time, datetime.now(timezone.utc))
            roles = ", ".join(r.mention for r in member.roles if r != member.guild.default_role) or "None"
            embed = self.create_embed(
                "Member Left",
                f"**User:** {member} (`{member.id}`)\n"
                f"**Roles:** {roles}\n"
                f"**Duration in Server:** {duration}",
                discord.Color.red(),
                f"Server: {member.guild.name}"
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        log = self.log_channel(guild)
        if log:
            embed = self.create_embed(
                "Member Banned",
                f"**User:** {user} (`{user.id}`) was banned from the server.",
                discord.Color.red(),
                f"Server: {guild.name}"
            )
            await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        log = self.log_channel(guild)
        if log:
            embed = self.create_embed(
                "Member Unbanned",
                f"**User:** {user} (`{user.id}`) was unbanned from the server.",
                discord.Color.green(),
                f"Server: {guild.name}"
            )
            await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        log = self.log_channel(after.guild)
        if not log:
            return

        # Timeout changes
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                embed = self.create_embed(
                    "Member Timed Out",
                    f"{after.mention} was timed out until {after.timed_out_until.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    discord.Color.orange()
                )
            else:
                embed = self.create_embed(
                    "Timeout Removed",
                    f"Timeout removed for {after.mention}",
                    discord.Color.green()
                )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            await log.send(embed=embed)


        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]
        if added_roles:
            embed = self.create_embed(
                "Role Added",
                "\n".join(r.mention for r in added_roles),
                discord.Color.green()
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            await log.send(embed=embed)
        if removed_roles:
            embed = self.create_embed(
                "Role Removed",
                "\n".join(r.mention for r in removed_roles),
                discord.Color.red()
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            await log.send(embed=embed)

        # Nickname change
        if before.nick != after.nick:
            embed = self.create_embed(
                "Nickname Changed",
                f"**Before:** {before.nick or 'None'}\n**After:** {after.nick or 'None'}",
                discord.Color.orange()
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            await log.send(embed=embed)

        # Avatar change
        if before.display_avatar.url != after.display_avatar.url:
            embed = self.create_embed(
                "Avatar Changed",
                f"{after.mention} updated their avatar.",
                discord.Color.orange()
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            await log.send(embed=embed)

    # ---------------- MESSAGE EVENTS ----------------
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.guild and not before.author.bot and before.content != after.content:
            log = self.log_channel(before.guild)
            if log:
                embed = self.create_embed(
                    "Message Edited",
                    f"**Author:** {before.author} (`{before.author.id}`)\n"
                    f"**Channel:** {before.channel.mention}\n"
                    f"**Before:** {before.content}\n"
                    f"**After:** {after.content}\n"
                    f"[Jump to Message]({after.jump_url})",
                    discord.Color.orange()
                )
                embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
                await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild and not message.author.bot:
            log = self.log_channel(message.guild)
            if log:
                content = message.content or "[Embed/Attachment]"
                embed = self.create_embed(
                    "Message Deleted",
                    f"**Author:** {message.author} (`{message.author.id}`)\n"
                    f"**Channel:** {message.channel.mention}\n"
                    f"**Content:** {content}",
                    discord.Color.red()
                )
                embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        if not messages:
            return
        guild = messages[0].guild
        log = self.log_channel(guild)
        if log:
            embed = self.create_embed(
                "Messages Purged",
                f"{len(messages)} messages deleted in {messages[0].channel.mention}",
                discord.Color.red()
            )
            await log.send(embed=embed)

    # ---------------- CHANNEL EVENTS ----------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log = self.log_channel(channel.guild)
        if log:
            category = channel.category.name if channel.category else "No category"
            embed = self.create_embed(
                "Channel Created",
                f"**Name:** {channel.name}\n**Category:** {category}",
                discord.Color.green()
            )
            await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        log = self.log_channel(after.guild)
        if not log:
            return
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if hasattr(before, "topic") and before.topic != after.topic:
            changes.append(f"**Topic:** {before.topic} → {after.topic}")
        if changes:
            embed = self.create_embed(
                "Channel Updated",
                "\n".join(changes),
                discord.Color.orange()
            )
            await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log = self.log_channel(channel.guild)
        if log:
            embed = self.create_embed(
                "❌ Channel Deleted",
                f"**Name:** {channel.name}",
                discord.Color.red()
            )
            await log.send(embed=embed)

    # ---------------- ROLE EVENTS ----------------
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log = self.log_channel(role.guild)
        if log:
            embed = self.create_embed(
                "🟢 Role Created",
                f"**Name:** {role.name}\n**Color:** {role.color}",
                discord.Color.green()
            )
            await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        log = self.log_channel(after.guild)
        if not log:
            return
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.color != after.color:
            changes.append(f"**Color:** {before.color} → {after.color}")
        if before.hoist != after.hoist:
            changes.append(f"**Hoisted:** {before.hoist} → {after.hoist}")
        if before.permissions != after.permissions:
            before_perms = [n for n, v in before.permissions if v]
            after_perms = [n for n, v in after.permissions if v]
            added = [p for p in after_perms if p not in before_perms]
            removed = [p for p in before_perms if p not in after_perms]
            if added:
                changes.append(f"Permissions Added: {', '.join(added)}")
            if removed:
                changes.append(f"Permissions Removed: {', '.join(removed)}")
        if changes:
            embed = self.create_embed(
                "📝 Role Updated",
                "\n".join(changes),
                discord.Color.orange()
            )
            await log.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log = self.log_channel(role.guild)
        if log:
            embed = self.create_embed(
                "🔴 Role Deleted",
                f"**Name:** {role.name}",
                discord.Color.red()
            )
            await log.send(embed=embed)

    # ---------------- EMOJI EVENTS ----------------
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before, after):
        log = self.log_channel(guild)
        if not log:
            return
        before_set = set(e.name for e in before)
        after_set = set(e.name for e in after)
        added = after_set - before_set
        removed = before_set - after_set
        desc = []
        if added:
            desc.append(f"**Added:** {', '.join(added)}")
        if removed:
            desc.append(f"**Removed:** {', '.join(removed)}")
        if desc:
            embed = self.create_embed(
                "🎨 Emoji Changes",
                "\n".join(desc),
                discord.Color.orange()
            )
            await log.send(embed=embed)

    # ---------------- SERVER UPDATES ----------------
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        log = self.log_channel(after)
        if not log:
            return
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.icon != after.icon:
            changes.append("**Icon:** Changed")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification Level:** {before.verification_level} → {after.verification_level}")
        if before.afk_channel != after.afk_channel:
            before_name = before.afk_channel.name if before.afk_channel else "None"
            after_name = after.afk_channel.name if after.afk_channel else "None"
            changes.append(f"**AFK Channel:** {before_name} → {after_name}")
        if before.afk_timeout != after.afk_timeout:
            changes.append(f"**AFK Timeout:** {before.afk_timeout}s → {after.afk_timeout}s")
        if before.explicit_content_filter != after.explicit_content_filter:
            changes.append(f"**Explicit Content Filter:** {before.explicit_content_filter} → {after.explicit_content_filter}")
        if before.premium_tier != after.premium_tier:
            changes.append(f"**Boost Tier:** {before.premium_tier} → {after.premium_tier}")
        if hasattr(before, 'vanity_url_code') and before.vanity_url_code != after.vanity_url_code:
            changes.append(f"**Vanity URL:** {before.vanity_url_code} → {after.vanity_url_code}")
        if changes:
            embed = self.create_embed(
                "🏛️ Server Updated",
                "\n".join(changes),
                discord.Color.orange()
            )
            embed.set_author(name=after.name, icon_url=after.icon.url if after.icon else discord.Embed.Empty)
            await log.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AuditLogs(bot))
