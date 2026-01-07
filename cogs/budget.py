import discord
import re
import datetime
import emoji
import asyncio
from discord.ext import commands
from discord.ui import Button, View, Select
from currency_converter import CurrencyConverter
import google.generativeai as genai
import os
from dotenv import load_dotenv           
import mysql.connector                  
from mysql.connector import Error        
from dbconnMOD import add_mod_log, get_warnings
from dbconnMOD import create_mod_log_table
from config import API_KEY, MOD_LOG_CHANNEL_ID, TARGET_CHANNEL_ID


load_dotenv()
API_KEY = os.getenv("API_KEY")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")
c = CurrencyConverter()

MOD_LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID", 1338401271119347743))
TARGET_CHANNEL_ID = [
    int(x) for x in os.getenv(
        "TARGET_CHANNEL_ID_LIST",
        "1338422604897456129,1248315045000253530,1244399296279740558,1240456287473369170,1246266893925482641,1243567009564721243,1244400051879546930"
    ).split(",")
]

budget_connection = None


def get_budget_connection():
    global budget_connection
    if budget_connection and budget_connection.is_connected():
        return budget_connection
    try:
        budget_connection = mysql.connector.connect(
            host=os.getenv('MOD_HOST'),
            port=int(os.getenv('MOD_PORT', 3306)),
            user=os.getenv('MOD_USER'),
            password=os.getenv('MOD_PASSWORD'),
            database=os.getenv('MOD_DATABASE')
        )
        create_budget_logs_table()
        return budget_connection
    except Error as e:
        print("❌ Error connecting to budget database:", e)
        return None


def create_budget_logs_table():
    conn = get_budget_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget_logs (
            log_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            content TEXT NOT NULL,
            detected_price FLOAT,
            currency VARCHAR(10),
            ai_check VARCHAR(20),
            staff_action VARCHAR(50),
            false_positive BOOLEAN DEFAULT FALSE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
        cursor.close()
        print("✅ budget_logs table ready.")
    except Error as e:
        print("❌ Error creating budget_logs table:", e)


def insert_budget_log(user_id, channel_id, message_id, content, detected_price=None, currency=None, ai_check="VALID"):
    conn = get_budget_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO budget_logs (user_id, channel_id, message_id, content, detected_price, currency, staff_action, false_positive)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (user_id, channel_id, message_id, content, detected_price, currency, "PENDING", False))

        conn.commit()
        cursor.close()
        print(f"✅ Logged budget violation for user {user_id}")
    except Error as e:
        print("❌ Error inserting budget log:", e)


def update_budget_log_action(message_id, action, false_positive=False):
    conn = get_budget_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE budget_logs
            SET staff_action=%s, false_positive=%s
            WHERE message_id=%s;
        """, (action, int(bool(false_positive)), message_id))
        conn.commit()
        cursor.close()
        print(f"✅ Updated budget log {message_id} -> action={action} false_positive={false_positive}")
    except Error as e:
        print("❌ Error updating budget log:", e)

class Budget(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        create_mod_log_table()

class WarningView(View):
    def __init__(self, bot, user, message, warning_type):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.message = message
        self.warning_type = warning_type
        self.minor_warnings, self.major_warnings = get_warnings(user.id)
        self.count = len(self.minor_warnings) + len(self.major_warnings) + 1
        self.add_item(WarningSelect(self))

    async def disable_buttons(self, interaction, warned_type=None):
        for item in self.children:
            item.disabled = True
        try:
            if warned_type:
                embed = interaction.message.embeds[0]
                embed.title = f"{embed.title} - WARNED ({warned_type})"
                await interaction.message.edit(view=self, embed=embed)
            else:
                await interaction.message.edit(view=self)
        except discord.NotFound:
            pass

    async def delete_log(self, interaction):
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass

    @discord.ui.button(label="Custom Message", style=discord.ButtonStyle.primary)
    async def custom_message(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Please type your custom warning message:", ephemeral=True)

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120)
            warned_label = "MINOR" if self.warning_type == "Minor Warning" else "MAJOR"
            prefix = f"You have received a {warned_label} warning in **Cheesecake Art Cafe** server.\n\n"
            content_with_prefix = prefix + msg.content

            embed = discord.Embed(
                title=f"⚠️ {self.warning_type} Issued",
                description=content_with_prefix,
                color=discord.Color.orange() if self.warning_type == "Major Warning" else discord.Color.red()
            )
            embed.set_footer(text="Please follow the server rules.")
            try:
                await self.user.send(embed=embed)
                await interaction.followup.send("Custom warning sent.", ephemeral=True)
                action_type = "major_warning" if self.warning_type == "Major Warning" else "minor_warning"
                add_mod_log(self.user.id, content_with_prefix, interaction.user.id, action_type)

                await self.message.delete()
                warned_type = "MINOR" if self.warning_type == "Minor Warning" else "MAJOR"
                await self.disable_buttons(interaction, warned_type)
            except discord.Forbidden:
                await interaction.followup.send("Could not DM user.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Custom message timed out.", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: Button):

        await self.delete_log(interaction)
        await interaction.response.send_message("Action canceled. The log has been deleted, the original post remains.", ephemeral=True)


class WarningSelect(Select):
    def __init__(self, parent):
        self.parent = parent
        if self.parent.warning_type == "Minor Warning":
            options = [
                discord.SelectOption(label="Minor - Price Below Minimum", value="minor_price_below"),
                discord.SelectOption(label="Minor - Buying Offer Below Minimum", value="minor_buying_below"),
                discord.SelectOption(label="Minor - Missing Price", value="minor_missing_price"),
                discord.SelectOption(label="Minor - Wrong Channel", value="minor_wrong_channel"),
                discord.SelectOption(label="Minor - Work Before Payment", value="minor_work_before_payment"),
            ]
        else:
            options = [
                discord.SelectOption(label="Major - NSFW / Suggestive art", value="major_nsfw"),
                discord.SelectOption(label="Major - Minor offering NSFW work", value="major_minor_nsfw"),
            ]
        super().__init__(placeholder="Choose an automated message...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        value_to_message = {
            "minor_price_below": f"Hello! Your selling price is currently below the server’s required minimum **__(15$ / 1.2k robux)__**. Please update your listing to meet the pricing guidelines before reposting. Thank you beforehand! This is your  {self.parent.count} Minor Warning.\n-# If you think that your warning has been issued wrongly, please contact the staff through <@1420311570172346408>  ",
            "minor_buying_below": f"Hi! Your buying offer doesn’t meet the server’s minimum price threshold **__(15$ / 1.2k robux)__**. Kindly adjust your offer to comply with the rules. Let us know if you need help finding the correct pricing! This is your {self.parent.count} Minor Warning. \n-# If you think that your warning has been issued wrongly, please contact the staff through <@1420311570172346408> ",
            "minor_missing_price": f"Hey there! All listings must include clear, visible pricing. Please edit your post to add the price so others can engage properly. This is your {self.parent.count} Minor Warning.\n-# If you think that your warning has been issued wrongly, please contact the staff through <@1420311570172346408> ",
            "minor_wrong_channel": f"Heads-up! It looks like your post was submitted in the wrong channel. Please repost it in the appropriate section to help keep things organized. We appreciate your cooperation! This is your {self.parent.count} Minor Warning.\n-# If you think that your warning has been issued wrongly, please contact the staff through <@1420311570172346408> ",
            "minor_work_before_payment": f"Sending a sketch before receiving payment is strictly against server policy. Please wait until payment is confirmed before sending any work. Repeated violations may result in further action. This is your {self.parent.count} Minor Warning.\n-# If you think that your warning has been issued wrongly, please contact the staff through <@1420311570172346408> ",
            "major_nsfw": f"Your post contained NSFW or suggestive content. This is your {self.parent.count} Major Warning.\n-#If you think that your warning has been issues wrongly, please contact the staff through <@1310970252447711343> \n-# If you think that your warning has been issued wrongly, please contact the staff through <@1420311570172346408> ",
            "major_minor_nsfw": f"You are a minor offering NSFW work. This is your {self.parent.count} Major Warning.\n-#If you think that your warning has been issues wrongly, please contact the staff through <@1310970252447711343> \n-# If you think that your warning has been issued wrongly, please contact the staff through <@1420311570172346408> ",
        }

        chosen = value_to_message.get(self.values[0])
        if not chosen:
            await interaction.response.send_message("Selected template not found.", ephemeral=True)
            return

        warned_label = "MINOR" if self.parent.warning_type == "Minor Warning" else "MAJOR"
        prefix = f"You have received a {warned_label} warning in **Cheesecake Art Cafe** server.\n\n"
        chosen = prefix + chosen

        embed = discord.Embed(
            title=f"⚠️ {self.parent.warning_type}",
            description=chosen,
            color=discord.Color.red() if self.parent.warning_type == "Minor Warning" else discord.Color.orange()
        )
        embed.add_field(name="Message Content", value=self.parent.message.content or "*No text*", inline=False)
        embed.set_footer(text="Please comply with server rules.")

        try:
            await self.parent.user.send(embed=embed)
            await interaction.response.send_message(f"✅ Automated warning sent: {self.values[0]}", ephemeral=True)
            action_type = "major_warning" if self.parent.warning_type == "Major Warning" else "minor_warning"
            add_mod_log(self.parent.user.id, chosen, interaction.user.id, action_type)

            # Delete the original message
            await self.parent.message.delete()

            warned_type = "MINOR" if self.parent.warning_type == "Minor Warning" else "MAJOR"
            await self.parent.disable_buttons(interaction, warned_type)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Could not DM user.", ephemeral=True)


class Budget(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"(?i)(TAT|TURN AROUND TIME|SLOTS)", "", text)
        text = emoji.replace_emoji(text, replace="")
        text = re.sub(r"<a?:\w+:\d+>", "", text)
        return text

    def extract_prices(self, text):
        price_patterns = re.finditer(
            r"(?P<currency>[$€£¥₹]|USD|EUR|GBP|JPY|INR)?\s*(?P<amount>\d+(?:\.\d+)?)\s*(?P<post_currency>[$€£¥₹]|USD|EUR|GBP|JPY|INR)?",
            text, re.IGNORECASE
        )
        prices = []
        currency_map = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}
        for match in price_patterns:
            pre_currency = match.group("currency")
            amount = match.group("amount")
            post_currency = match.group("post_currency")
            currency_code = None
            if pre_currency:
                currency_code = currency_map.get(pre_currency, pre_currency)
            elif post_currency:
                currency_code = currency_map.get(post_currency, post_currency)
            else:
                currency_code = "USD"
            if amount:
                try:
                    prices.append((float(amount), str(currency_code).upper()))
                except ValueError:
                    continue
        return prices

    def check_price(self, text):
        text = self.clean_text(text)
        if re.search(r"\b(free|0\s?\$|0\$|cheap\b|below\s?min)\b", text, re.IGNORECASE):
            return True
        prices = self.extract_prices(text)
        if not prices and text.strip() != "":
            return "MISSING_PRICE"
        for price, currency in prices:
            try:
                price_in_usd = c.convert(price, currency.upper(), 'USD') if currency.upper() != "USD" else price
                if price_in_usd < 15:
                    return True
            except Exception:
                continue
        return False

    async def analyze_with_gemini(self, text):
        try:
            prompt = f"""
            You are a moderator assistant reviewing marketplace messages.
            Only flag messages as INVALID if they contain a price below $15 USD.
            Ignore add-ons, fees, or commercial use fees.
            Bulk deals (minimum, bundle, bulk) are valid.
            TAT mentions make message valid.
            User Message: {text}
            """
            response = model.generate_content(prompt)
            return "INVALID" if "INVALID" in response.text.upper() else "VALID"
        except Exception as e:
            print("Gemini check error:", e)
            return "VALID"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.channel or message.channel.id not in TARGET_CHANNEL_ID:
            return

        text = self.clean_text(message.content)
        regex_flag = self.check_price(text)
        ai_flag = await self.analyze_with_gemini(text)

        flagged = False
        warning_type = "Minor Warning"
        reason = None

        if regex_flag == "MISSING_PRICE":
            flagged = True
            reason = "MISSING_PRICE"
        elif regex_flag is True:
            flagged = True
            reason = "PRICE_TOO_LOW_OR_KEYWORD"
        elif ai_flag == "INVALID":
            flagged = True
            reason = "AI_INVALID"
            warning_type = "Major Warning"

        if flagged:
            mod_log_channel = self.bot.get_channel(MOD_LOG_CHANNEL_ID)
            if not mod_log_channel:
                print("❌ Mod log channel not found!")
                return

            embed = discord.Embed(
                title="🚨 Possible Rule Violation",
                color=discord.Color.red()
            )
            embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
            embed.add_field(name="User ID", value=message.author.id, inline=True)
            embed.add_field(name="Message Link", value=f"[Click Here]({message.jump_url})", inline=True)
            embed.add_field(name="Flag Reason", value=reason, inline=True)
            if message.content:
                embed.add_field(name="Message Content", value=message.content[:1024], inline=False)
            embed.set_footer(text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            try:
                await mod_log_channel.send(
                    embed=embed,
                    view=WarningView(self.bot, message.author, message, warning_type)
                )
            except Exception as e:
                print("❌ Error sending mod log:", e)


async def setup(bot):
    await bot.add_cog(Budget(bot))
