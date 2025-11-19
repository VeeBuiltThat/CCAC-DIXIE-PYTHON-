import discord
from discord.ext import commands
import re

ALLOWED_CATEGORY_IDS = [
    1240456571541258341,
    1240455945331675217,
    1243563029207973989,
    1244399454166057042,
    1400369669000400937,
    1346882435400466495,
    1419606799438319660,
    1419606732971180104,
    1419606665891811469,
    1346881386510024745,
    1402348823598203061,
    1402347868756643900,
    1402347829409874032,
    1402347709976936591,
    1402347454438838443,
    1346882153279000648,
    1346881466881146910,
    1346839676790771772,
    1422566042630230116,
    1412722642321932298
]

ALLOWED_CHANNEL_IDS = [
    1242925169681502322,
    1242925123422523462,
    1420468983336931328,
    1243565009523445800,
    1416125543828426915,
    1247314373693673582,
]

BYPASS_ROLE_IDS = [
    1334950965408956527,
    1429420833671086171,
]


LINK_REGEX = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)

class LinkSnatcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return  

 
        if not LINK_REGEX.search(message.content):
            return


        if message.channel.id in ALLOWED_CHANNEL_IDS:
            return

        if getattr(message.channel, "category", None) and message.channel.category and message.channel.category.id in ALLOWED_CATEGORY_IDS:
            return

        if isinstance(message.author, discord.Member):
            author_role_ids = {role.id for role in message.author.roles}
            if any(role_id in author_role_ids for role_id in BYPASS_ROLE_IDS):
                return

        try:
            await message.delete()
        except discord.Forbidden:
            pass 

        try:
            warning = await message.channel.send(
                f"{message.author.mention}, links are not allowed in this channel!"
            )
            await warning.delete(delay=60)  # auto-delete after 1 minute
        except discord.Forbidden:
            pass

async def setup(bot):
    await bot.add_cog(LinkSnatcher(bot))
