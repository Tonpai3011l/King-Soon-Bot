import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")

CONTACT_TOPICS = [
    {
        "label": "ติดต่อซื้อสินค้า",
        "value": "1",
        # "emoji": "🛍️",
    },
    {
        "label": "ติดต่อสอบถาม",
        "value": "2",
        # "emoji": "💬",
    },
    {
        "label": "ติดต่อเคลมสินค้า",
        "value": "3",
        # "emoji": "🛠️",
    },
]

TICKET_CHANNEL_PREFIXES = {
    "1": "ติดต่อซื้อสินค้า",
    "2": "ติดต่อสอบถาม",
    "3": "ติดต่อเคลมสินค้า",
}

SETTINGS_FILE = Path(__file__).with_name("ticket_settings.json")
CONTACT_PANEL_DEFAULTS = {
    "title": "ติดต่อแอดมิน",
    "description": "ใส่คำอธิบายสำหรับผู้ใช้ได้ที่นี่",
    "image_url": "",
}


def load_settings() -> dict[str, object]:
    """Load all saved bot settings."""
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return settings if isinstance(settings, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_settings() -> None:
    """Persist all settings so they remain after a bot restart."""
    SETTINGS_FILE.write_text(
        json.dumps(
            {
                "ticket_category_ids": TICKET_CATEGORY_IDS,
                "contact_panels": CONTACT_PANELS,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_contact_panel_settings(guild_id: int | None) -> dict[str, object]:
    """Return the configured contact panel values for a server."""
    panel_settings = CONTACT_PANEL_DEFAULTS.copy()
    if guild_id is not None:
        panel_settings.update(CONTACT_PANELS.get(guild_id, {}))
    return panel_settings


SAVED_SETTINGS = load_settings()
RAW_CATEGORY_IDS = SAVED_SETTINGS.get("ticket_category_ids", {})
RAW_CONTACT_PANELS = SAVED_SETTINGS.get("contact_panels", {})

TICKET_CATEGORY_IDS = {
    int(guild_id): int(category_id)
    for guild_id, category_id in RAW_CATEGORY_IDS.items()
} if isinstance(RAW_CATEGORY_IDS, dict) else {}
CONTACT_PANELS = {
    int(guild_id): panel_settings
    for guild_id, panel_settings in RAW_CONTACT_PANELS.items()
    if isinstance(panel_settings, dict)
} if isinstance(RAW_CONTACT_PANELS, dict) else {}

class Client(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="ks!", intents=intents)

    async def setup_hook(self) -> None:
        self.add_view(CloseTicketView())
        self.add_view(ContactPanel())
        await self.tree.sync()

Bot = Client()

class CloseTicketView(discord.ui.View):
    """Persistent close button shown inside each ticket."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="ปิดตั๋ว",
        emoji="🔒",
        style=discord.ButtonStyle.primary,
        custom_id="kingsoon:close-ticket",
    )
    async def close_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "ไม่พบห้อง ticket ที่ต้องการปิด", ephemeral=True
            )
            return

        await interaction.response.send_message("กำลังปิดตั๋ว...", ephemeral=True)
        await interaction.channel.delete(reason=f"ปิด ticket โดย {interaction.user}")

class ContactSelect(discord.ui.Select):
    """Drop-down menu used in the admin contact panel."""

    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label=topic["label"],
                value=topic["value"],
                emoji=topic.get("emoji"),
            )
            for topic in CONTACT_TOPICS
        ]
        super().__init__(
            custom_id="kingsoon:contact-topic",
            placeholder="เลือกหัวข้อที่ต้องการติดต่อ",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "คำสั่งนี้ใช้งานได้ภายในเซิร์ฟเวอร์เท่านั้น", ephemeral=True
            )
            return

        ticket_prefix = TICKET_CHANNEL_PREFIXES[self.values[0]]
        ticket_name = f"{ticket_prefix}-{interaction.user.name}"[:100]
        guild = interaction.guild
        category_id = TICKET_CATEGORY_IDS.get(guild.id)
        ticket_category = guild.get_channel(category_id) if category_id else None
        if not isinstance(ticket_category, discord.CategoryChannel):
            await interaction.response.send_message(
                "ยังไม่ได้ตั้งค่าหมวดหมู่ ticket กรุณาให้แอดมินใช้คำสั่ง "
                "`/ตั้งค่า-หมวดหมู่ติดต่อ` ก่อน",
                ephemeral=True,
            )
            return

        bot_member = guild.me
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
        }

        if bot_member is not None:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
            )

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            ticket_channel = await guild.create_text_channel(
                ticket_name,
                category=ticket_category,
                overwrites=overwrites,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "บอทยังไม่มีสิทธิ์ **Manage Channels** สำหรับสร้าง ticket", ephemeral=True
            )
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "ไม่สามารถสร้าง ticket ได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง", ephemeral=True
            )
            return

        ticket_embed = discord.Embed(
            description=(
                f"## {TICKET_CHANNEL_PREFIXES[self.values[0]]}\n"
                "<a:anouncements_animated:1550806007255404554> ทีมงานจะตอบกลับภายใน 12 ชั่วโมง\n"
                "<a:warning:1546006798572724244> โปรดแจ้งรายละเอียดให้ชัดเจนเพื่อให้ทีมงานสามารถช่วยเหลือคุณได้อย่างรวดเร็ว"
            ),
            color=discord.Color.blue(),
        )
        await ticket_channel.send(
            content=f"{interaction.user.mention} {interaction.user.get_role(1531709726172254219).mention}",
            embed=ticket_embed,
            view=CloseTicketView(),
            allowed_mentions=discord.AllowedMentions(
                everyone=False, roles=True, users=True
            ),
        )

        if interaction.message is not None:
            await interaction.message.edit(view=ContactPanel(interaction.guild.id))

        await interaction.followup.send(
            f"สร้าง ticket เรียบร้อยแล้ว: {ticket_channel.mention}", ephemeral=True
        )

class ContactPanel(discord.ui.LayoutView):
    """Components v2 panel for selecting an admin contact topic."""

    def __init__(self, guild_id: int | None = None) -> None:
        super().__init__(timeout=None)

        panel_settings = get_contact_panel_settings(guild_id)
        contact_menu = ContactSelect()
        menu_row = discord.ui.ActionRow(contact_menu)
        panel_items = [
            discord.ui.TextDisplay(f"## {panel_settings['title']}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(str(panel_settings["description"])),
        ]
        image_url = str(panel_settings.get("image_url", "")).strip()
        if image_url:
            panel_items.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(image_url))
            )
        panel_items.extend(
            [
                menu_row,
                discord.ui.Separator(),
                discord.ui.TextDisplay("-# King Soon Bot • ทีมงานจะตอบภายใน 12 ชั่วโมง"),
            ]
        )
        panel = discord.ui.Container(*panel_items)
        panel.accent_color = discord.Color.blue()
        self.add_item(panel)

@Bot.event
async def on_ready():
    assert Bot.user is not None
    print(f"Logged in as {Bot.user} (ID: {Bot.user.id})")

@Bot.command()
async def ping(ctx: commands.Context[commands.Bot]):
    await ctx.send(f"`{round(Bot.latency * 1000)} ms`")

@Bot.tree.command(
    name="ตั้งค่า-ติดต่อแอดมิน",
    description="ตั้งค่าแผงติดต่อทีมงาน",
)
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def create_contact_panel(interaction: discord.Interaction) -> None:
    """Create a new saved contact panel in the current channel."""
    assert interaction.guild is not None
    guild = interaction.guild
    panel_settings = get_contact_panel_settings(guild.id)

    try:
        panel_channel_id = int(panel_settings.get("channel_id", 0))
        panel_message_id = int(panel_settings.get("message_id", 0))
        panel_channel = guild.get_channel(panel_channel_id)
        if isinstance(panel_channel, (discord.TextChannel, discord.Thread)):
            panel_message = await panel_channel.fetch_message(panel_message_id)
            await interaction.response.send_message(
                f"มีแผงติดต่ออยู่แล้ว: {panel_message.jump_url}\n"
                "หากต้องการเปลี่ยนข้อมูล ให้ใช้ `/แก้ไข-แผงติดต่อ`",
                ephemeral=True,
            )
            return
    except (ValueError, TypeError, discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass

    await interaction.response.send_message(view=ContactPanel(guild.id))
    panel_message = await interaction.original_response()
    panel_settings["channel_id"] = panel_message.channel.id
    panel_settings["message_id"] = panel_message.id
    CONTACT_PANELS[guild.id] = panel_settings
    save_settings()
    await interaction.followup.send(
        "สร้างแผงติดต่อเรียบร้อยแล้ว ใช้ `/แก้ไข-ติดต่อแอดมิน` เพื่อเปลี่ยนข้อมูล",
        ephemeral=True,
    )


@Bot.tree.command(
    name="แก้ไข-ติดต่อแอดมิน",
    description="แก้ไขข้อมูลของแผงติดต่อที่ตั้งไว้",
)
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def edit_contact_panel(
    interaction: discord.Interaction,
    title: str,
    description: str,
    image_url: str | None = None,
) -> None:
    """Edit the existing contact panel without creating a new one."""
    assert interaction.guild is not None
    if image_url and not image_url.startswith(("https://", "http://")):
        await interaction.response.send_message(
            "image_url ต้องเป็นลิงก์ที่ขึ้นต้นด้วย `https://` หรือ `http://`",
            ephemeral=True,
        )
        return

    guild = interaction.guild
    panel_settings = get_contact_panel_settings(guild.id)
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        panel_channel_id = int(panel_settings.get("channel_id", 0))
        panel_message_id = int(panel_settings.get("message_id", 0))
        panel_channel = guild.get_channel(panel_channel_id)
        if isinstance(panel_channel, (discord.TextChannel, discord.Thread)):
            panel_message = await panel_channel.fetch_message(panel_message_id)
        else:
            panel_message = None
    except (ValueError, TypeError, discord.NotFound, discord.Forbidden, discord.HTTPException):
        panel_message = None

    if panel_message is None:
        await interaction.followup.send(
            "ยังไม่พบแผงติดต่อเดิม กรุณาใช้ `/ตั้งค่า-ติดต่อแอดมิน` ก่อน",
            ephemeral=True,
        )
        return

    panel_settings.update(
        {
            "title": title,
            "description": description,
            "image_url": image_url or "",
        }
    )
    CONTACT_PANELS[guild.id] = panel_settings
    await panel_message.edit(view=ContactPanel(guild.id))
    save_settings()
    await interaction.followup.send(
        f"แก้ไขแผงติดต่อเรียบร้อยแล้ว: {panel_message.jump_url}",
        ephemeral=True,
    )


@create_contact_panel.error
async def create_contact_panel_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "คำสั่งนี้ใช้ได้เฉพาะผู้ดูแลเซิร์ฟเวอร์เท่านั้น", ephemeral=True
        )
        return
    raise error


@edit_contact_panel.error
async def edit_contact_panel_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "คำสั่งนี้ใช้ได้เฉพาะผู้ดูแลเซิร์ฟเวอร์เท่านั้น", ephemeral=True
        )
        return
    raise error

@Bot.tree.command(name="ตั้งค่า-หมวดหมู่ติดต่อ", description="กำหนดหมวดหมู่สำหรับสร้าง ticket")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def set_contact_category(
    interaction: discord.Interaction, category: discord.CategoryChannel
) -> None:
    """Save the selected ticket category for this server."""
    assert interaction.guild is not None
    TICKET_CATEGORY_IDS[interaction.guild.id] = category.id
    save_settings()
    await interaction.response.send_message(
        f"ตั้งค่าหมวดหมู่ ticket เป็น `{category.mention}` เรียบร้อยแล้ว",
        ephemeral=True,
    )

@set_contact_category.error
async def set_contact_category_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "คำสั่งนี้ใช้ได้เฉพาะผู้ดูแลเซิร์ฟเวอร์เท่านั้น", ephemeral=True
        )
        return
    raise error

if __name__ == "__main__":
    if TOKEN:
        Bot.run(TOKEN, log_handler=None)
    else:
        raise RuntimeError(
            "DISCORD_TOKEN is missing. Copy .env.example to .env and add your Bot token."
        )
