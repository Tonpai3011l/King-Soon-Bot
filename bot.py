import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from keep_alive import keep_alive

load_dotenv()

TOKEN = os.getenv("TOKEN")

class Client(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="ks!", intents=intents)

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.tickets")
        await self.tree.sync()


Bot = Client()

if __name__ == "__main__":
    if not TOKEN:
        print("ข้อผิดพลาด: ไม่พบ TOKEN ในไฟล์ .env")
    else: 
        Bot.run(TOKEN, log_handler=None)
        keep_alive()