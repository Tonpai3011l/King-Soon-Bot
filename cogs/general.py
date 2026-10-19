import discord
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        assert self.bot.user is not None
        print(f"Logged in as {self.bot.user} (ID: {self.bot.user.id})")

    @commands.command()
    async def ping(self, ctx: commands.Context[commands.Bot]) -> None:
        await ctx.send(f"`{round(self.bot.latency * 1000)} ms`")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))