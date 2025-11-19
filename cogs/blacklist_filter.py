
import discord
from discord.ext import commands
import re

STAFF_CHANNEL_ID = 1422481641846210621
STAFF_PING_ID = 1422222372471046154


SFW_CATEGORY_IDS = {
    1243563029207973989,
    1244063961305841755,
    1243564077985431612,
    1240448660978798653,
    1240455945331675217,
    1416001390483869738,
}
NSFW_CATEGORY_IDS = {1242890093983698966}


IGNORED_CATEGORY_IDS = {
    1412722642321932298,
    1240456571541258341,
}

# ✅ Word lists
SFW_BLACKLISTED_WORDS = [
    "nigger","nlgger","nlgg","n1gger","jizz","jiz","j1z","j1zz","cum","cumming","c00m","cuhm",
    "Masterbate","Masturbate","Masturbation","Masturbating","Masterbation","Masterbating","Mast3rbait",
    "nlgga","nlgger","molest","molesters","molester","mol3st","mol3esters","m0l3st",
    "Meth","Chink","Cocaine","Stripper","s3x","Niqqa","Niqqas","Fag","Ddy","Ddlg","Virgin","Virginity",
    "Dildo","Dild","Vibrator","Dild0","Kys","Nut3d","Nutt3d","Faggots","Fagg","Faggot","n1gger","n1g","n!gger",
    "Fags","yarichin","yachirin","yarchin","Lewd","fujoshi","fujo","Lewds","Harems","Ecchi","Harem","L3wd",
    "Lewding","Anal","ecchi","hentai","Hitler","Hitl3r","Raping","@nal","@n@l","Pussies","Rapeing","Pussy",
    "pornhub","pornhub.com","yarichinbitclub","bitclub","xvideos.com","coochie","Groomer","Gr00m","whorehouse",
    "wh0re","whore","wh0r3","whores","columbine","puteiro","Gr00m1ng","Ped0","Nuted","Nutted","femd0m","femdom",
    "f3md0m","f3mdom","nigga","Nig33r","Oppai","0ppai","penis","N1g","N1g33r","N1g3r","S3x","Sexual","Nig3r",
    "nig*","nig","S3xual","petafile","petafil3","S3xu@al","$ex","$3x","$exu@l","$exual","retard","onlyfans",
    "fansonly","fanzonly","onlyfanz","lolicon","pettanko","l0li","Lolic0n","$perm","Sperm","$p3rm","Sp3rm",
    "wank","xsex","Ejaculate","Ejaculation","Masterbait","Masterbation","cooch","sex","raped","Nudes","pedo",
    "pedophile","ped0","pedophilia","Horny","Bdsm","r@pe","r@ped","tard","Ni663r","niggas","Kink","Fetish",
    "rape","rap3","r@p3","sex","niggers","ddlg","nigg","Suicide","Nigg3r","kink","kinky","pervert","perv",
    "negro","Dicks","卐","nigg","nibba","whore","retard","retarded","fag","tranny","dyke","coon","douche",
    "faggot","gook","Rape","slut","incest","boner","Loli","hentai","cum","porn","pornhub","wanker","orgasm",
    "orgasmic","grabify","grabify.com","fujoshis","smut","bestiality","beastiality","anc","a&c"
]

NSFW_BLACKLISTED_WORDS = [
    "nigger","nlgger","nlgg","n1gger",
    "nlgga","nlgger","molest","molesters","molester","mol3st","mol3esters","m0l3st",
    "Meth","Chink","Cocaine","Niqqa","Niqqas","Fag","Ddy","Ddlg",
    "Kys","Nut3d","Nutt3d",
    "Fags","yarichin","yachirin","yarchin","Lewd","fujoshi","fujo","Lewds","Harems","Ecchi","Harem","L3wd",
    "Lewding","Hitler","Hitl3r","Raping",
    "Groomer","Gr00m","whorehouse","columbine","puteiro","Gr00m1ng","Ped0","femd0m","femdom",
    "f3md0m","f3mdom","nigga","Nig33r","Oppai","0ppai","penis","N1g","N1g33r","N1g3r","Nig3r",
    "nig*","nig","petafile","petafil3","retard",
    "lolicon","pettanko","l0li","Lolic0n",
    "wank","raped","pedo","pedophile","ped0","pedophilia",
    "r@pe","r@ped","tard","Ni663r","niggas",
    "rape","rap3","r@p3","niggers","ddlg","nigg","Suicide","Nigg3r",
    "negro","卐","nigg","nibba","retard","retarded","fag","tranny","dyke","coon","douche",
    "faggot","gook","Rape","slut","incest","Loli","grabify","grabify.com",
    "fujoshis","bestiality","beastiality","anc","a&c"
]

def compile_blacklist(words):
    pattern_parts = []
    for word in words:

        if re.match(r'^[a-zA-Z]+$', word):
            pattern_parts.append(rf"\b{word}\b")
        else:
            pattern_parts.append(rf"(?<!\w){word}(?!\w)")
    return re.compile(r"(" + "|".join(pattern_parts) + r")", re.IGNORECASE)

SFW_REGEX = compile_blacklist(SFW_BLACKLISTED_WORDS)
NSFW_REGEX = compile_blacklist(NSFW_BLACKLISTED_WORDS)


URL_REGEX = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)


class BlacklistFilter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.TextChannel):
            return

        category = message.channel.category
        if not category:
            return

        category_id = category.id

        if category_id in IGNORED_CATEGORY_IDS:
            return


        if category_id in SFW_CATEGORY_IDS:
            regex = SFW_REGEX
        elif category_id in NSFW_CATEGORY_IDS:
            regex = NSFW_REGEX
        else:
            return 


        clean_content = URL_REGEX.sub("", message.content)


        match = regex.search(clean_content)
        if match:
            blacklisted_word = match.group(0) 

            try:
                await message.delete()
            except discord.Forbidden:
                pass


            try:
                await message.channel.send(
                    f"{message.author.mention}, your message was removed because it contained a blacklisted word: "
                    f"`{blacklisted_word}`."
                )
            except discord.Forbidden:
                pass 

            staff_channel = self.bot.get_channel(STAFF_CHANNEL_ID)
            if staff_channel:
                embed = discord.Embed(
                    title="🚨 Blacklisted Word Detected",
                    color=discord.Color.red()
                )
                embed.add_field(name="User", value=f"{message.author} ({message.author.id})", inline=False)
                embed.add_field(name="Message", value=message.content, inline=False)
                embed.add_field(name="Blacklisted Word", value=f"`{blacklisted_word}`", inline=True)
                embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                embed.set_footer(
                    text=f"Message ID: {message.id} • Time: {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                await staff_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BlacklistFilter(bot))
