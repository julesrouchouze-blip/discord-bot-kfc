import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiosqlite
import os
import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHANNEL_ID = int(os.environ.get("ADMIN_CHANNEL_ID", "0"))
ADMIN_ROLE_NAME = os.environ.get("ADMIN_ROLE_NAME", "Admin")
DB_PATH = "economy.db"

PRODUCTS = [
      {"id": "kfc_300", "nom": "KFC 300-499 points", "prix": 3},
      {"id": "kfc_500", "nom": "KFC 500-799 points", "prix": 4},
      {"id": "kfc_800", "nom": "KFC 800-999 points", "prix": 5},
      {"id": "kfc_1000", "nom": "KFC 1000-1299 points", "prix": 6},
      {"id": "kfc_1300", "nom": "KFC 1300-1599 points", "prix": 7},
      {"id": "kfc_1600", "nom": "KFC 1600-1799 points", "prix": 8},
      {"id": "kfc_1800", "nom": "KFC 1800-1999 points", "prix": 9},
      {"id": "kfc_2000", "nom": "KFC 2000-2399 points", "prix": 10},
      {"id": "kfc_2400", "nom": "KFC 2400-2500 points", "prix": 11},
]

async def init_db():
      async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("CREATE TABLE IF NOT EXISTS wallets (user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0)")
                await db.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, montant INTEGER, description TEXT, created_at TEXT)")
                await db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id TEXT, product_nom TEXT, prix INTEGER, created_at TEXT)")
                await db.execute("CREATE TABLE IF NOT EXISTS recharge_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, montant INTEGER, status TEXT DEFAULT 'pending', message_id INTEGER, created_at TEXT)")
                await db.commit()

  async def ensure_wallet(user_id, username):
        async with aiosqlite.connect(DB_PATH) as db:
                  await db.execute("INSERT OR IGNORE INTO wallets (user_id, username, balance) VALUES (?, ?, 0)", (user_id, username))
                  await db.execute("UPDATE wallets SET username = ? WHERE user_id = ?", (username, user_id))
                  await db.commit()

    async def get_balance(user_id):
          async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)) as c:
                                  row = await c.fetchone()
                                  return row[0] if row else 0

            async def update_balance(user_id, delta):
                  async with aiosqlite.connect(DB_PATH) as db:
                            async with db.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)) as c:
                                          row = await c.fetchone()
                                          if not row: raise ValueError("Introuvable.")
                                                        new_bal = row[0] + delta
                                          if new_bal < 0: raise ValueError("Solde insuffisant.")
                                                    await db.execute("UPDATE wallets SET balance = ? WHERE user_id = ?", (new_bal, user_id))
                                      await db.commit()
                            return new_bal

              async def add_transaction(user_id, type_, montant, desc=""):
                    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                    async with aiosqlite.connect(DB_PATH) as db:
                              await db.execute("INSERT INTO transactions (user_id, type, montant, description, created_at) VALUES (?,?,?,?,?)", (user_id, type_, montant, desc, now))
                              await db.commit()

                async def get_last_transactions(user_id, limit=10):
                      async with aiosqlite.connect(DB_PATH) as db:
                                async with db.execute("SELECT type, montant, description, created_at FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)) as c:
                                              return await c.fetchall()

                        async def add_order(user_id, product_id, product_nom, prix):
                              now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                              async with aiosqlite.connect(DB_PATH) as db:
                                        await db.execute("INSERT INTO orders (user_id, product_id, product_nom, prix, created_at) VALUES (?,?,?,?,?)", (user_id, product_id, product_nom, prix, now))
                                        await db.commit()

                          async def create_recharge_request(user_id, username, montant):
                                now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                                async with aiosqlite.connect(DB_PATH) as db:
                                          c = await db.execute("INSERT INTO recharge_requests (user_id, username, montant, status, created_at) VALUES (?,?,?,'pending',?)", (user_id, username, montant, now))
                                          await db.commit()
                                          return c.lastrowid

                            async def get_recharge_request(req_id):
                                  async with aiosqlite.connect(DB_PATH) as db:
                                            async with db.execute("SELECT * FROM recharge_requests WHERE id = ?", (req_id,)) as c:
                                                          row = await c.fetchone()
                                                          if not row: return None
                                                                        cols = [d[0] for d in c.description]
                                                          return dict(zip(cols, row))

                                    async def update_recharge_status(req_id, status, msg_id=None):
                                          async with aiosqlite.connect(DB_PATH) as db:
                                          if msg_id:
                                                        await db.execute("UPDATE recharge_requests SET status=?, message_id=? WHERE id=?", (status, msg_id, req_id))
else:
            await db.execute("UPDATE recharge_requests SET status=? WHERE id=?", (status, req_id))
        await db.commit()

class ProductSelect(discord.ui.Select):
      def __init__(self):
                options = [discord.SelectOption(label=p["nom"], description=f"{p['prix']} credits", value=p["id"], emoji="??") for p in PRODUCTS]
        super().__init__(placeholder="??  Choisir un produit...", min_values=1, max_values=1, options=options, custom_id="shop_select", row=0)

    async def callback(self, interaction: discord.Interaction):
              product = next((p for p in PRODUCTS if p["id"] == self.values[0]), None)
        user = interaction.user
        await ensure_wallet(user.id, str(user))
        balance = await get_balance(user.id)
        if balance < product["prix"]:
                      embed = discord.Embed(title="Solde insuffisant", color=discord.Color.red(), description=f"Prix : {product['prix']} credits\nSolde : {balance} credits\nManque : {product['prix']-balance} credits")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        new_bal = await update_balance(user.id, -product["prix"])
        await add_transaction(user.id, "achat", -product["prix"], f"Achat : {product['nom']}")
        await add_order(user.id, product["id"], product["nom"], product["prix"])
        embed = discord.Embed(title="Commande confirmee !", color=discord.Color.green())
        embed.add_field(name="Produit", value=product["nom"])
        embed.add_field(name="Prix", value=f"{product['prix']} credits")
        embed.add_field(name="Nouveau solde", value=f"{new_bal} credits")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class MainShopView(discord.ui.View):
      def __init__(self):
                super().__init__(timeout=None)
                self.add_item(ProductSelect())

      @discord.ui.button(label="Recharger mon wallet", emoji="??", style=discord.ButtonStyle.success, custom_id="shop_recharger", row=1)
      async def btn_recharger(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_modal(RechargeModal())

      @discord.ui.button(label="Mon solde", emoji="??", style=discord.ButtonStyle.secondary, custom_id="shop_solde", row=1)
      async def btn_solde(self, interaction: discord.Interaction, button: discord.ui.Button):
                user = interaction.user
                await ensure_wallet(user.id, str(user))
                balance = await get_balance(user.id)
                  transactions = await get_last_transactions(user.id)
                embed = discord.Embed(title="Mon Wallet", color=discord.Color.gold())
                embed.add_field(name="Solde", value=f"{balance} credits", inline=False)
                if transactions:
                              lines = [f"{'[+]' if m>=0 else '[-]'} {dt} - {m} ({t})" for t,m,d,dt in transactions]
                              embed.add_field(name="Historique", value="\n".join(lines), inline=False)
                          await interaction.response.send_message(embed=embed, ephemeral=True)

  class RechargeModal(discord.ui.Modal, title="Recharger mon Wallet"):
        montant = discord.ui.TextInput(label="Montant (credits)", placeholder="Ex: 100")

    async def on_submit(self, interaction: discord.Interaction):
              try:
                            m = int(self.montant.value)
                            if m <= 0: raise ValueError
                                      except:
                            await interaction.response.send_message("Montant invalide.", ephemeral=True); return
              user = interaction.user
        await ensure_wallet(user.id, str(user))
        ch = interaction.client.get_channel(ADMIN_CHANNEL_ID)
        if not ch:
                      await interaction.response.send_message("Salon admin introuvable.", ephemeral=True); return
                  req_id = await create_recharge_request(user.id, str(user), m)
        embed = discord.Embed(title="Demande de rechargement", color=discord.Color.orange())
        embed.add_field(name="Utilisateur", value=str(user))
        embed.add_field(name="Montant", value=f"{m} credits")
        view = AdminView(req_id, user.id, m)
        msg = await ch.send(embed=embed, view=view)
        await update_recharge_status(req_id, "pending", msg.id)
        await interaction.response.send_message(f"Demande de {m} credits envoyee !", ephemeral=True)

class AdminView(discord.ui.View):
      def __init__(self, req_id, target_id, montant):
                super().__init__(timeout=None)
                self.req_id = req_id
                self.target_id = target_id
                self.montant = montant

    def is_admin(self, i): return discord.utils.get(i.user.roles, name=ADMIN_ROLE_NAME) is not None

    @discord.ui.button(label="Valider", style=discord.ButtonStyle.success)
    async def valider(self, interaction: discord.Interaction, button: discord.ui.Button):
              if not self.is_admin(interaction):
                            await interaction.response.send_message("Permission refusee.", ephemeral=True); return
                        req = await get_recharge_request(self.req_id)
        if not req or req["status"] != "pending":
                      await interaction.response.send_message("Deja traite.", ephemeral=True); return
                  await ensure_wallet(self.target_id, f"User{self.target_id}")
        bal = await update_balance(self.target_id, self.montant)
        await add_transaction(self.target_id, "recharge", self.montant, f"Valide par {interaction.user}")
        await update_recharge_status(self.req_id, "approved")
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Valide par", value=str(interaction.user))
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        u = interaction.client.get_user(self.target_id)
        if u:
                      try: await u.send(f"Rechargement {self.montant} credits valide ! Solde : {bal}")
                                    except: pass

              @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger)
    async def refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
              if not self.is_admin(interaction):
                            await interaction.response.send_message("Permission refusee.", ephemeral=True); return
                        req = await get_recharge_request(self.req_id)
        if not req or req["status"] != "pending":
                      await interaction.response.send_message("Deja traite.", ephemeral=True); return
                  await update_recharge_status(self.req_id, "refused")
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="Refuse par", value=str(interaction.user))
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        u = interaction.client.get_user(self.target_id)
        if u:
                      try: await u.send(f"Rechargement {self.montant} credits refuse.")
                                    except: pass

          intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
      await init_db()
    bot.add_view(MainShopView())
    print(f"Bot connecte : {bot.user}")
    synced = await bot.tree.sync()
    print(f"{len(synced)} commandes synchronisees")

@bot.tree.command(name="poster", description="Poster le menu boutique (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def poster(interaction: discord.Interaction):
      embed = discord.Embed(color=0x2B2D31)
    lines = [f"?? **{p['nom']}** - {p['prix']} credits" for p in PRODUCTS]
    embed.description = "\n".join(lines)
    embed.set_footer(text="Selectionnez un produit dans le menu ci-dessous")
    await interaction.response.send_message("Poste !", ephemeral=True)
    await interaction.channel.send(embed=embed, view=MainShopView())

@bot.tree.command(name="solde", description="Voir ton solde")
async def solde(interaction: discord.Interaction):
      await ensure_wallet(interaction.user.id, str(interaction.user))
    bal = await get_balance(interaction.user.id)
    embed = discord.Embed(title="Mon Wallet", color=discord.Color.gold())
    embed.add_field(name="Solde", value=f"{bal} credits")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="crediter", description="Crediter un membre (admin)")
@app_commands.describe(membre="Membre", montant="Montant")
@app_commands.checks.has_permissions(administrator=True)
async def crediter(interaction: discord.Interaction, membre: discord.Member, montant: int):
      await ensure_wallet(membre.id, str(membre))
    bal = await update_balance(membre.id, montant)
    await add_transaction(membre.id, "admin", montant, f"Par {interaction.user}")
    await interaction.response.send_message(f"{montant} credits ajoutes. Solde : {bal}", ephemeral=True)

bot.run(BOT_TOKEN)
