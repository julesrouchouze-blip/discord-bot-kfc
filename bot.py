import discord
from discord.ext import commands
import asyncio
import os
from utils.database import init_db
from cogs.views import MainShopView

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
      await init_db()
      print(f"Bot connecte : {bot.user}")
      bot.add_view(MainShopView())
      try:
                synced = await bot.tree.sync()
                print(f"{len(synced)} commande(s) slash synchronisee(s)")
except Exception as e:
        print(f"Erreur sync : {e}")

async def main():
      async with bot:
                await bot.load_extension("cogs.economy")
                await bot.load_extension("cogs.admin")
                token = os.environ.get("BOT_TOKEN", "")
                await bot.start(token)

  asyncio.run(main())
