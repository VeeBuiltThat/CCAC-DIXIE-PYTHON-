import discord
from discord.ext import commands, tasks
from discord import Embed, ui
from datetime import datetime, timedelta
import random
import string
import os
from dotenv import load_dotenv
from os import REQUIRED_ROLE_ID, UNVERIFIED_ROLE_ID, WELCOME_CHANNEL_ID, NOTICE_CHANNEL_ID, GUILD_ID, NOTICE_MESSAGE, STAFF_CONTACT_CHANNEL


load_dotenv()

REQUIRED_ROLE_ID = int(os.getenv("REQUIRED_ROLE_ID"))
UNVERIFIED_ROLE_ID = int(os.getenv("UNVERIFIED_ROLE_ID"))
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))
NOTICE_CHANNEL_ID = int(os.getenv("NOTICE_CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))
NOTICE_MESSAGE = os.getenv("NOTICE_MESSAGE", "You must get the 'Verified' role within 48 hours...")
STAFF_CONTACT_CHANNEL = int(os.getenv("STAFF_CONTACT_CHANNEL", 1243567293750050887))

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

from dbconn import (
    add_user,
    get_user_by_id,
    get_password_by_user_id,
    get_join_time_by_user_id,
    check_user_exists,
    delete_user_by_id
)

GUILD_ID = 1240448660266029126


class ResendPasswordView(ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @ui.button(label="📩 Resend Password", style=discord.ButtonStyle.blurple)
    async def resend_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.member_id:
            await interaction.response.send_message(
                "⚠️ This button isn’t for you.", ephemeral=True
            )
            return

        if not check_user_exists(self.member_id):
            await interaction.response.send_message(
                "❌ I couldn’t find your verification details. Please contact staff.",
                ephemeral=True,
            )
            return

        password = get_password_by_user_id(self.member_id)
        try:
            embed = Embed(
                title="Your Verification Password",
                description=f"Here’s your one-time password:\n```{password}```\n\nUse it with `!verify <password>` in the verification channel.",
                color=discord.Color.green(),
            )
            await interaction.user.send(embed=embed)
            await interaction.response.send_message(
                "I sent your password again! Please check your DMs.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I still can’t DM you. Please enable DMs and try again.",
                ephemeral=True,
            )


class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_roles.start() 

    def generate_password(self, length=8):
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))

    async def log_event(self, message, member=None):
        print(f"[LOG] {message}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return
        password = self.generate_password()
        unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)

        if unverified_role:
            await member.add_roles(unverified_role, reason="New member - assigned Unverified role")
            await self.log_event(f"{member.name} was given the Unverified role.", member)

        add_user(member.id, datetime.now(), password)

        
        try:
            embed = Embed(
                title="Verification Required",
                description=(
                    f"Welcome to **{member.guild.name}**, {member.mention}!\n\n"
                    "To verify your account, copy the password below and send it in the verification channel "
                    "or use the command `!verify <password>`.\n\n"
                    "⚠️ You must verify within **48 hours** or you will be removed."
                ),
                color=discord.Color.green()
            )
            embed.add_field(name="Your Password", value=f"```{password}```", inline=False)
            embed.set_footer(text="Thank you for joining 🚀")
            await member.send(embed=embed, view=ResendPasswordView(member.id))

        except discord.Forbidden:
            # DM failed
            notice_channel = self.bot.get_channel(NOTICE_CHANNEL_ID)
            if notice_channel:
                embed = Embed(
                    title="⚠️ Couldn't Send You a DM",
                    description=(
                        "It looks like your DMs are disabled.\n\n"
                        "**Steps to fix this:**\n"
                        "1️. Enable DMs in **Settings > Privacy & Safety**\n"
                        "2️. Click the button below or run `!dmme`\n\n"
                        "If you still need help, contact staff in <#1243567293750050887>."
                    ),
                    color=discord.Color.red()
                )
                await notice_channel.send(content=f"{member.mention}", embed=embed, view=ResendPasswordView(member.id))

        welcome_channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            welcome_embed = Embed(
                title="Welcome!",
                description=(
                    f"Welcome {member.mention}!\n\n"
                    "Check your DMs for a verification password.\n"
                    "If you didn’t get it, click the button below or use `!dmme`.\n\n"
                    f"⚠️ {NOTICE_MESSAGE}"
                ),
                color=discord.Color.blurple()
            )
            await welcome_channel.send(embed=welcome_embed, view=ResendPasswordView(member.id))

        await self.log_event(f"{member.name} has joined and was sent a verification password.", member)


    @commands.command(name="verify", help="Verify yourself with your password.")
    async def verify(self, ctx, *, password: str = None):
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            return

        if not password:
            await ctx.send("Please provide a password. Example: `!verify MyPass123`")
            return

        member_id = ctx.author.id
        if not check_user_exists(member_id):
            await ctx.send("I couldn’t find your verification details. Please make sure you joined recently.")
            return

        stored_password = get_password_by_user_id(member_id)
        if stored_password == password:
            verified_role = ctx.guild.get_role(REQUIRED_ROLE_ID)
            unverified_role = ctx.guild.get_role(UNVERIFIED_ROLE_ID)
            if verified_role:
                await ctx.author.add_roles(verified_role, reason="Correct verification password provided.")
            if unverified_role:
                await ctx.author.remove_roles(unverified_role, reason="Verified - removed Unverified role")
            delete_user_by_id(member_id)

            success_embed = Embed(
                title="✅ Verified!",
                description=f"Congrats {ctx.author.mention}, you are now verified!",
                color=discord.Color.green()
            )
            await ctx.send(embed=success_embed)
            await self.log_event(f"{ctx.author.name} has been successfully verified.", ctx.author)
        else:
            fail_embed = Embed(
                title="❌ Wrong Password",
                description="That password doesn’t match. Please check your DMs and try again.",
                color=discord.Color.red()
            )
            await ctx.send(embed=fail_embed)


    @commands.command(name="dmme", help="Resends your verification password if you updated DM settings.")
    async def dm_me(self, ctx):
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            return
        member = ctx.author
        member_id = member.id

        if not check_user_exists(member_id):
            await ctx.send("I couldn’t find your verification details. Please make sure you joined recently.")
            return

        password = get_password_by_user_id(member_id)
        if not password:
            await ctx.send("Something went wrong. Please contact staff through <@1310970252447711343>.")
            return

        try:
            embed = Embed(
                title="Your Verification Password",
                description=f"Here’s your password:\n```{password}```\nUse it with `!verify <password>`.",
                color=discord.Color.green()
            )
            await member.send(embed=embed)
            await ctx.send(f"✅ {member.mention}, I sent your password again! Please check your DMs.")
        except discord.Forbidden:
            await ctx.send("I still couldn’t DM you. Please enable DMs and try again.")

        await self.log_event(f"{member.name} requested to resend their password.")

    @commands.command(name="DMuser", help="(Staff) DMs the verification password again to a specific user.")
    async def dm_user(self, ctx, user: discord.Member):
        if ctx.guild is None or ctx.guild.id != GUILD_ID:
            return
        member_id = user.id

        password = get_password_by_user_id(member_id)
        if not password:
            await ctx.send(
                f"Couldn’t find details for {user.mention}. Ask them to contact staff in <#{STAFF_CONTACT_CHANNEL}>."
            )
            return

        try:
            embed = Embed(
                title="Your Verification Password",
                description=f"Hello {user.mention}, here is your password:\n```{password}```\nUse it with `!verify <password>`.",
                color=discord.Color.green()
            )
            await user.send(embed=embed)
            staff_embed = Embed(
                title="Password Sent",
                description=f"I resent the password to {user.mention}.",
                color=discord.Color.blurple()
            )
            await ctx.send(embed=staff_embed)
        except discord.Forbidden:
            await ctx.send(f"❌ Couldn’t DM {user.mention}. Please ensure their DMs are enabled.")

        await self.log_event(f"Password resent to {user.name} by {ctx.author.name}.")


    @tasks.loop(minutes=60)
    async def check_roles(self):
        try:
            for guild in self.bot.guilds:
                if guild.id != GUILD_ID:
                    continue
                for member in guild.members:
                    if check_user_exists(member.id):
                        join_time = get_join_time_by_user_id(member.id)
                        if not join_time:
                            continue
                        if isinstance(join_time, str):
                            join_time = datetime.strptime(join_time, '%Y-%m-%d %H:%M:%S')

                        if datetime.now() - join_time >= timedelta(hours=48):
                            required_role = guild.get_role(REQUIRED_ROLE_ID)
                            if required_role and required_role not in member.roles:
                                await member.kick(reason="Failed to verify within 48 hours.")
                                delete_user_by_id(member.id)
                                await self.log_event(f"{member.name} was kicked for failing to verify in time.")
        except Exception as e:
            print(f"Error in check_roles task: {e}")

async def setup(bot):
    await bot.add_cog(Security(bot))
