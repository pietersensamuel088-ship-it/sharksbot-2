import json
import os
import random
import re
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import discord
import aiohttp
from aiohttp import web
from discord import app_commands
from discord.ext import commands, tasks

def load_env_file(path=Path(".env")):
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env(name, default=""):
    return os.getenv(name, default)


def env_int(name, default):
    return int(env(name, str(default)))


def env_path(name, default):
    return Path(env(name, default))


load_env_file()

TOKEN = env("DISCORD_BOT_TOKEN")
STEAM_API_KEY = env("STEAM_API_KEY")
BASE_SAVE_FILE = env_path("BASE_SAVE_FILE", "base_message.json")
WARNINGS_FILE = env_path("WARNINGS_FILE", "warnings.json")
BINDINGS_FILE = env_path("BINDINGS_FILE", "bindings.json")
BLACKLIST_FILE = env_path("BLACKLIST_FILE", "blacklist.json")
GIVEAWAYS_FILE = env_path("GIVEAWAYS_FILE", "giveaways.json")
STATUS_MESSAGE_FILE = env_path("STATUS_MESSAGE_FILE", "status_message.json")
GMOD_WEBHOOK_SETTINGS_FILE = env_path("GMOD_WEBHOOK_SETTINGS_FILE", "gmod_webhook_settings.json")
WEB_DASHBOARD_HOST = env("WEB_DASHBOARD_HOST", "0.0.0.0")
WEB_DASHBOARD_PORT = env_int("WEB_DASHBOARD_PORT", 8080)
DISCORD_LOGO_URL = env("DISCORD_LOGO_URL", "https://i.imgur.com/XUAp7MU.png")
LOA_APPLICATIONS_CHANNEL_ID = env_int("LOA_APPLICATIONS_CHANNEL_ID", 1508499978253766866)
LOA_PEOPLE_CHANNEL_ID = env_int("LOA_PEOPLE_CHANNEL_ID", 1508501143100194948)
LOA_ROLE_ID = env_int("LOA_ROLE_ID", 1508499680252793075)
VERIFIED_ROLE_ID = env_int("VERIFIED_ROLE_ID", 1508503687411011755)
GANG_MEMBER_ROLE_ID = env_int("GANG_MEMBER_ROLE_ID", 1503498704278257775)
STARTER_ROLE_ID = env_int("STARTER_ROLE_ID", 1486165333336260755)
BOT_STATUS_CHANNEL_ID = env_int("BOT_STATUS_CHANNEL_ID", 1508529868277813398)
BLACKLIST_CHANNEL_ID = env_int("BLACKLIST_CHANNEL_ID", 1493910793295495258)
GMOD_WEBHOOK_URL = env("GMOD_WEBHOOK_URL")
GMOD_LOG_FILE = env_path("GMOD_LOG_FILE", r"C:\Program Files (x86)\Steam\steamapps\common\GarrysMod\garrysmod\console.log")
PRINTER_WEBHOOK_URL = env("PRINTER_WEBHOOK_URL")
PRINTER_COLLECTOR_NAME = env("PRINTER_COLLECTOR_NAME", "TTVRecod")
PRINTER_CUT_PERCENT = env_int("PRINTER_CUT_PERCENT", 20)
PAYOUT_WEBHOOK_URL = env("PAYOUT_WEBHOOK_URL")
PAYOUT_GIVER_NAME = env("PAYOUT_GIVER_NAME", "TTVRecod")

EMOJI_SHARK = "\U0001F988"
EMOJI_PARTY = "\U0001F389"
EMOJI_LOCK = "\U0001F510"
EMOJI_PIN = "\U0001F4CD"
EMOJI_WARNING = "\u26A0\uFE0F"
EMOJI_CHECK = "\u2705"
EMOJI_CROSS = "\u274C"
EMOJI_ID = "\U0001FAAA"
EMOJI_STAFF = "\U0001F6E1\uFE0F"
EMOJI_CLOCK = "\U0001F551"
EMOJI_CALENDAR = "\U0001F4C5"
EMOJI_NOTE = "\U0001F4DD"
EMOJI_GAME = "\U0001F3AE"
EMOJI_GIFT = "\U0001F381"
EMOJI_MONEY = "\U0001F4B0"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)
commands_synced = False
status_message_cache = None
gmod_log_position = None
dashboard_runner = None
steam_profile_cache = {}
giveaway_finish_tasks = {}
giveaway_finishes_in_progress = set()
GMOD_PARTY_CHAT_PATTERN = re.compile(
    r"\{[^}]*party chat\s*\|\}\s*(?P<name>[^:]+):\s*(?P<message>.+)",
    re.IGNORECASE,
)

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Sharks Bot Dashboard</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #101318;
        --panel: #181e26;
        --panel-2: #202833;
        --line: #303946;
        --text: #f4f7fb;
        --muted: #a9b4c1;
        --accent: #22c55e;
        --accent-2: #38bdf8;
        --warn: #f59e0b;
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        min-height: 100vh;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, Helvetica, sans-serif;
      }

      button, input, select { font: inherit; }

      .shell {
        width: min(1400px, calc(100% - 28px));
        margin: 0 auto;
        padding: 24px 0;
      }

      .top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 16px;
      }

      h1 {
        margin: 0;
        font-size: 28px;
        letter-spacing: 0;
      }

      .sub {
        margin: 6px 0 0;
        color: var(--muted);
      }

      .toolbar {
        display: grid;
        grid-template-columns: 220px minmax(180px, 1fr) 140px 140px;
        gap: 10px;
        margin-bottom: 16px;
      }

      select, input, button {
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 10px 12px;
        background: var(--panel);
        color: var(--text);
      }

      button {
        border: 0;
        background: var(--accent);
        color: #052411;
        font-weight: 800;
        cursor: pointer;
      }

      .stats {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
        margin-bottom: 16px;
      }

      .stat, .table-wrap {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel);
      }

      .stat {
        padding: 14px;
      }

      .stat strong {
        display: block;
        font-size: 24px;
      }

      .stat span {
        color: var(--muted);
      }

      .table-wrap {
        overflow: auto;
      }

      table {
        width: 100%;
        min-width: 1160px;
        border-collapse: collapse;
      }

      th, td {
        padding: 12px;
        border-bottom: 1px solid var(--line);
        text-align: left;
        vertical-align: top;
      }

      th {
        position: sticky;
        top: 0;
        background: #151b23;
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0;
      }

      .member {
        display: flex;
        gap: 10px;
        align-items: center;
        min-width: 220px;
      }

      .avatar {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: var(--panel-2);
        object-fit: cover;
      }

      .name strong,
      .steam strong {
        display: block;
      }

      .muted, small {
        color: var(--muted);
      }

      .pill {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 4px 8px;
        background: var(--panel-2);
        color: var(--muted);
        font-size: 12px;
      }

      .online { color: var(--accent); }
      .idle { color: var(--warn); }
      .dnd { color: #fb7185; }

      .roles {
        max-width: 320px;
        color: var(--muted);
      }

      .error {
        color: #fb7185;
        margin-bottom: 12px;
      }

      @media (max-width: 880px) {
        .top { align-items: stretch; flex-direction: column; }
        .toolbar { grid-template-columns: 1fr; }
        .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="top">
        <div>
          <h1>Sharks Bot Dashboard</h1>
          <p class="sub">Discord members, /bind records, and public Steam profile details.</p>
        </div>
      </section>

      <section class="toolbar">
        <select id="guildSelect"></select>
        <input id="searchInput" placeholder="Search name, Discord ID, Steam ID, country, role">
        <select id="statusFilter">
          <option value="all">All statuses</option>
          <option value="online">Online</option>
          <option value="idle">Idle</option>
          <option value="dnd">Do not disturb</option>
          <option value="offline">Offline</option>
        </select>
        <button id="refreshButton" type="button">Refresh</button>
      </section>

      <p class="error" id="errorText"></p>

      <section class="stats">
        <div class="stat"><strong id="loadedCount">0</strong><span>members loaded</span></div>
        <div class="stat"><strong id="boundCount">0</strong><span>bound accounts</span></div>
        <div class="stat"><strong id="onlineCount">0</strong><span>online or idle</span></div>
        <div class="stat"><strong id="shownCount">0</strong><span>shown after filters</span></div>
      </section>

      <section class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Discord member</th>
              <th>Status</th>
              <th>Discord details</th>
              <th>Steam profile</th>
              <th>Steam details</th>
              <th>Roles</th>
              <th>Dates</th>
            </tr>
          </thead>
          <tbody id="membersBody"></tbody>
        </table>
      </section>
    </main>

    <script>
      const guildSelect = document.querySelector("#guildSelect");
      const searchInput = document.querySelector("#searchInput");
      const statusFilter = document.querySelector("#statusFilter");
      const refreshButton = document.querySelector("#refreshButton");
      const membersBody = document.querySelector("#membersBody");
      const errorText = document.querySelector("#errorText");
      const loadedCount = document.querySelector("#loadedCount");
      const boundCount = document.querySelector("#boundCount");
      const onlineCount = document.querySelector("#onlineCount");
      const shownCount = document.querySelector("#shownCount");
      let allMembers = [];

      function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          "\"": "&quot;",
          "'": "&#039;"
        }[char]));
      }

      function formatDate(value) {
        if (!value) return "Unknown";
        return new Date(value).toLocaleString();
      }

      function statusClass(status) {
        if (status === "online") return "online";
        if (status === "idle") return "idle";
        if (status === "dnd") return "dnd";
        return "";
      }

      function memberSearchText(row) {
        return [
          row.discord.id,
          row.discord.username,
          row.discord.global_name,
          row.discord.display_name,
          row.discord.nickname,
          row.discord.status,
          row.discord.roles.join(" "),
          row.steam.steam_id_64,
          row.steam.ingame_name,
          row.steam.personaname,
          row.steam.country,
          row.steam.current_game
        ].join(" ").toLowerCase();
      }

      function renderMembers() {
        const query = searchInput.value.trim().toLowerCase();
        const wantedStatus = statusFilter.value;
        const filtered = allMembers.filter(row => {
          const matchesSearch = !query || memberSearchText(row).includes(query);
          const matchesStatus = wantedStatus === "all" || row.discord.status === wantedStatus;
          return matchesSearch && matchesStatus;
        });

        shownCount.textContent = filtered.length;

        membersBody.innerHTML = filtered.map(row => {
          const discord = row.discord;
          const steam = row.steam;
          const avatar = discord.avatar_url || steam.avatar_url || "";
          const steamProfile = steam.profile_url
            ? `<a href="${escapeHtml(steam.profile_url)}" target="_blank" rel="noreferrer">Open profile</a>`
            : `<span class="muted">Not public or not bound</span>`;
          const activities = discord.activities.length
            ? discord.activities.map(activity => `${activity.type}: ${activity.name}`).join("<br>")
            : "None";
          const roles = discord.roles.length ? discord.roles.join(", ") : "No roles";

          return `
            <tr>
              <td>
                <div class="member">
                  ${avatar ? `<img class="avatar" src="${escapeHtml(avatar)}" alt="">` : `<div class="avatar"></div>`}
                  <div class="name">
                    <strong>${escapeHtml(discord.display_name || discord.username)}</strong>
                    <small>@${escapeHtml(discord.username || "unknown")}</small>
                  </div>
                </div>
              </td>
              <td>
                <span class="pill ${statusClass(discord.status)}">${escapeHtml(discord.status)}</span>
                <br><small>${escapeHtml(activities)}</small>
              </td>
              <td>
                <strong>ID</strong><br><small>${escapeHtml(discord.id)}</small><br>
                <strong>Nickname</strong><br><small>${escapeHtml(discord.nickname || "None")}</small><br>
                <strong>Top role</strong><br><small>${escapeHtml(discord.top_role || "None")}</small>
              </td>
              <td class="steam">
                <strong>${escapeHtml(steam.personaname || steam.ingame_name || "Not bound")}</strong>
                <small>${steamProfile}</small>
              </td>
              <td>
                <strong>SteamID64</strong><br><small>${escapeHtml(steam.steam_id_64 || "None")}</small><br>
                <strong>Country</strong><br><small>${escapeHtml(steam.country || "Hidden/unknown")}</small><br>
                <strong>Game</strong><br><small>${escapeHtml(steam.current_game || "None")}</small>
              </td>
              <td class="roles">${escapeHtml(roles)}</td>
              <td>
                <strong>Joined</strong><br><small>${escapeHtml(formatDate(discord.joined_at))}</small><br>
                <strong>Created</strong><br><small>${escapeHtml(formatDate(discord.created_at))}</small><br>
                <strong>Bound</strong><br><small>${escapeHtml(formatDate(steam.bound_at))}</small>
              </td>
            </tr>
          `;
        }).join("");
      }

      async function loadGuilds() {
        const response = await fetch("/api/guilds");
        const data = await response.json();
        guildSelect.innerHTML = data.guilds.map(guild => (
          `<option value="${guild.id}">${escapeHtml(guild.name)} (${guild.member_count ?? "?"})</option>`
        )).join("");
      }

      async function loadMembers() {
        errorText.textContent = "";
        membersBody.innerHTML = "";

        const guildId = guildSelect.value;
        const response = await fetch(`/api/members?guild_id=${encodeURIComponent(guildId)}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "Could not load members.");
        }

        allMembers = data.members;
        loadedCount.textContent = data.total_members_loaded;
        boundCount.textContent = data.total_bound;
        onlineCount.textContent = allMembers.filter(row => (
          row.discord.status === "online" || row.discord.status === "idle" || row.discord.status === "dnd"
        )).length;
        renderMembers();
      }

      async function start() {
        try {
          await loadGuilds();
          await loadMembers();
        } catch (error) {
          errorText.textContent = error.message;
        }
      }

      refreshButton.addEventListener("click", () => loadMembers().catch(error => {
        errorText.textContent = error.message;
      }));
      guildSelect.addEventListener("change", () => loadMembers().catch(error => {
        errorText.textContent = error.message;
      }));
      searchInput.addEventListener("input", renderMembers);
      statusFilter.addEventListener("change", renderMembers);

      start();
    </script>
  </body>
</html>"""


def utc_now():
    return datetime.now(timezone.utc)


def format_discord_time(iso_time):
    timestamp = int(datetime.fromisoformat(iso_time).timestamp())
    return f"<t:{timestamp}:f>"


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        backup_path = path.with_suffix(f"{path.suffix}.broken")
        path.replace(backup_path)
        print(f"{path} was broken JSON. Moved it to {backup_path} and started fresh.")
        return default


def save_json(path, data):
    temp_path = path.with_suffix(f"{path.suffix}.tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    temp_path.replace(path)


def load_base_message():
    return load_json(BASE_SAVE_FILE, None)


def save_base_message(channel_id, message_id):
    save_json(BASE_SAVE_FILE, {"channel_id": channel_id, "message_id": message_id})


def load_status_message():
    return load_json(STATUS_MESSAGE_FILE, None)


def save_status_message(channel_id, message_id):
    save_json(STATUS_MESSAGE_FILE, {"channel_id": channel_id, "message_id": message_id})


def load_gmod_webhook_settings():
    return load_json(GMOD_WEBHOOK_SETTINGS_FILE, {"enabled": True})


def save_gmod_webhook_settings(enabled):
    save_json(GMOD_WEBHOOK_SETTINGS_FILE, {"enabled": enabled})


def is_gmod_webhook_enabled():
    settings = load_gmod_webhook_settings()
    return settings.get("enabled", True)


def load_warnings():
    return load_json(WARNINGS_FILE, {})


def save_warnings(warnings):
    save_json(WARNINGS_FILE, warnings)


def load_bindings():
    return load_json(BINDINGS_FILE, {})


def save_bindings(bindings):
    save_json(BINDINGS_FILE, bindings)


def load_blacklist():
    return load_json(BLACKLIST_FILE, {})


def save_blacklist(blacklist):
    save_json(BLACKLIST_FILE, blacklist)


def load_giveaways():
    return load_json(GIVEAWAYS_FILE, {})


def save_giveaways(giveaways):
    save_json(GIVEAWAYS_FILE, giveaways)

def is_valid_steam_id_64(steam_id):
    return steam_id.isdigit() and len(steam_id) == 17


def get_next_blacklist_id(blacklist):
    highest_id = 0

    for entry in blacklist.values():
        blacklist_id = entry.get("blacklist_id", "")

        if blacklist_id.startswith("BL-") and blacklist_id[3:].isdigit():
            highest_id = max(highest_id, int(blacklist_id[3:]))

    return f"BL-{highest_id + 1:04d}"


def get_next_giveaway_id(giveaways):
    highest_id = 0

    for giveaway in giveaways.values():
        giveaway_id = giveaway.get("giveaway_id", "")

        if giveaway_id.startswith("GW-") and giveaway_id[3:].isdigit():
            highest_id = max(highest_id, int(giveaway_id[3:]))

    return f"GW-{highest_id + 1:04d}"


def parse_duration_seconds(timer):
    match = re.fullmatch(r"\s*(\d+)\s*([smhd])\s*", timer.lower())

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    multipliers = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 60 * 60 * 24,
    }

    return amount * multipliers[unit]


def get_next_warn_id(warnings):
    highest_id = 0

    for user_warnings in warnings.values():
        for warning in user_warnings:
            warn_id = warning.get("warn_id", "")

            if warn_id.startswith("W-") and warn_id[2:].isdigit():
                highest_id = max(highest_id, int(warn_id[2:]))

    return f"W-{highest_id + 1:04d}"


def make_base_embed(party_name="Not set", party_password="Not set", base_location="Not set"):
    updated_at = utc_now()

    embed = discord.Embed(
        title=f"{EMOJI_SHARK} Sharks Base Information",
        color=discord.Color.teal(),
        timestamp=updated_at,
    )
    embed.set_thumbnail(url=DISCORD_LOGO_URL)
    embed.add_field(name=f"{EMOJI_PARTY} Party Name", value=party_name, inline=False)
    embed.add_field(name=f"{EMOJI_LOCK} Party Password", value=party_password, inline=False)
    embed.add_field(name=f"{EMOJI_PIN} Base Location", value=base_location, inline=False)
    embed.set_footer(text="Use /updatebase to change this information • Last updated")

    return embed


def make_warning_embed(member, warning):
    embed = discord.Embed(
        title=f"{EMOJI_WARNING} Sharks Warning Issued",
        description=f"{member.mention} has been warned.",
        color=discord.Color.orange(),
        timestamp=datetime.fromisoformat(warning["created_at"]),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name=f"{EMOJI_ID} Warning ID", value=warning["warn_id"], inline=True)
    embed.add_field(name=f"{EMOJI_STAFF} Staff Member", value=warning["moderator_name"], inline=True)
    embed.add_field(name=f"{EMOJI_CLOCK} Time", value=format_discord_time(warning["created_at"]), inline=False)
    embed.add_field(name="Reason", value=warning["reason"], inline=False)
    embed.set_footer(text="Sharks warning system")

    return embed


def make_warning_dm_embed(member, warning):
    embed = discord.Embed(
        title=f"{EMOJI_WARNING} You Have Been Warned",
        description="A staff member has issued you a warning in the Sharks Discord.",
        color=discord.Color.orange(),
        timestamp=datetime.fromisoformat(warning["created_at"]),
    )
    embed.set_thumbnail(url=DISCORD_LOGO_URL)
    embed.add_field(name="Server Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name=f"{EMOJI_ID} Warning ID", value=warning["warn_id"], inline=True)
    embed.add_field(name=f"{EMOJI_STAFF} Staff Member", value=warning["moderator_name"], inline=True)
    embed.add_field(name=f"{EMOJI_CLOCK} Time", value=format_discord_time(warning["created_at"]), inline=False)
    embed.add_field(name="Reason", value=warning["reason"], inline=False)
    embed.set_footer(text="Keep this warning ID if you need to ask staff about it.")

    return embed


def make_warning_list_embed(member, user_warnings):
    nickname = member.nick if member.nick else "No nickname set"

    embed = discord.Embed(
        title=f"{EMOJI_SHARK} Warning Information",
        color=discord.Color.teal(),
        timestamp=utc_now(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Name", value=str(member), inline=True)
    embed.add_field(name="User ID", value=str(member.id), inline=True)
    embed.add_field(name="Nickname", value=nickname, inline=False)
    embed.add_field(name="Total Warnings", value=str(len(user_warnings)), inline=False)

    if not user_warnings:
        embed.description = "This member has no warnings."
        return embed

    for warning in user_warnings[:10]:
        embed.add_field(
            name=f"{warning['warn_id']} • {format_discord_time(warning['created_at'])}",
            value=f"**Reason:** {warning['reason']}\n**Staff:** {warning['moderator_name']}",
            inline=False,
        )

    if len(user_warnings) > 10:
        embed.set_footer(text=f"Showing 10 of {len(user_warnings)} warnings")

    return embed


def make_loa_panel_embed():
    embed = discord.Embed(
        title=f"{EMOJI_CALENDAR} Sharks LOA Applications",
        description=(
            "Need time away? Click the button below to request LOA.\n\n"
            "Please include a clear reason, start date, end date, and any extra notes staff should know."
        ),
        color=discord.Color.blue(),
        timestamp=utc_now(),
    )
    embed.set_thumbnail(url=DISCORD_LOGO_URL)
    embed.set_footer(text="Use the button below to request LOA")

    return embed


def make_loa_request_embed(member, reason, start_date, end_date, notes):
    embed = discord.Embed(
        title=f"{EMOJI_CALENDAR} New LOA Request",
        description=f"{member.mention} has submitted an LOA request.",
        color=discord.Color.blue(),
        timestamp=utc_now(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Nickname", value=member.nick or "No nickname set", inline=False)
    embed.add_field(name=f"{EMOJI_CALENDAR} Start Date", value=start_date, inline=True)
    embed.add_field(name=f"{EMOJI_CALENDAR} End Date", value=end_date, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name=f"{EMOJI_NOTE} Notes", value=notes or "No extra notes.", inline=False)
    embed.set_footer(text="LOA role was applied if the bot had permission")

    return embed


def make_loa_people_embed(member, start_date, end_date, notes):
    embed = discord.Embed(
        title=f"{EMOJI_CALENDAR} Member On LOA",
        description=f"{member.mention} is now marked as on LOA.",
        color=discord.Color.green(),
        timestamp=utc_now(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Nickname", value=member.nick or "No nickname set", inline=False)
    embed.add_field(name=f"{EMOJI_CALENDAR} Start Date", value=start_date, inline=True)
    embed.add_field(name=f"{EMOJI_CALENDAR} End Date", value=end_date, inline=True)
    embed.add_field(name=f"{EMOJI_NOTE} Notes", value=notes or "No extra notes.", inline=False)
    embed.set_footer(text="LOA status posted by Sharks bot")

    return embed


def make_bind_embed(member, binding, nickname_status, role_status):
    embed = discord.Embed(
        title=f"{EMOJI_CHECK} Account Bound",
        description=f"{member.mention} has linked their SteamID64.",
        color=discord.Color.green(),
        timestamp=utc_now(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name=f"{EMOJI_GAME} In-game Name", value=binding["ingame_name"], inline=False)
    embed.add_field(name="SteamID64", value=f"`{binding['steam_id_64']}`", inline=False)
    embed.add_field(name="Nickname", value=nickname_status, inline=False)
    embed.add_field(name="Verified Role", value=role_status, inline=False)
    embed.set_footer(text="Sharks verification system")

    return embed


def make_steamid_embed(member, binding):
    embed = discord.Embed(
        title=f"{EMOJI_GAME} SteamID Lookup",
        color=discord.Color.teal(),
        timestamp=utc_now(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Discord Member", value=f"{member.mention} ({member.id})", inline=False)
    embed.add_field(name=f"{EMOJI_GAME} In-game Name", value=binding["ingame_name"], inline=False)
    embed.add_field(name="SteamID64", value=f"`{binding['steam_id_64']}`", inline=False)
    embed.add_field(name="Bound At", value=format_discord_time(binding["bound_at"]), inline=False)
    embed.set_footer(text="Sharks verification system")

    return embed


def make_status_embed():
    now = utc_now()

    embed = discord.Embed(
        title=f"{EMOJI_CHECK} Bot is Online",
        description="Sharks bot is currently running.",
        color=discord.Color.green(),
        timestamp=now,
    )
    embed.set_thumbnail(url=DISCORD_LOGO_URL)
    embed.add_field(name="Status", value="Online", inline=True)
    embed.add_field(name="Updated", value=format_discord_time(now.isoformat()), inline=True)
    embed.add_field(
        name="Heartbeat",
        value="Updates every 10 seconds while the bot is running.",
        inline=False,
    )
    embed.add_field(
        name="If This Stops Updating",
        value="If this embed has not updated in 10 seconds, please contact staff.",
        inline=False,
    )
    embed.set_footer(text="A stale update time means the bot may be offline or disconnected")

    return embed


def make_giveaway_embed(giveaway):
    ends_at_text = format_discord_time(giveaway["ends_at"])
    created_at_text = format_discord_time(giveaway["created_at"])
    entrants_count = len(giveaway.get("entrants", []))
    status = "Ended" if giveaway.get("ended") else "Open"

    embed = discord.Embed(
        title=f"{EMOJI_GIFT} Sharks Giveaway",
        description=giveaway["description"],
        color=discord.Color.blue(),
        timestamp=datetime.fromisoformat(giveaway["created_at"]),
    )
    embed.add_field(name="Prize / Name", value=giveaway["name"], inline=False)
    embed.add_field(name="Giveaway ID", value=giveaway["giveaway_id"], inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Winners", value=str(giveaway["winner_count"]), inline=True)
    embed.add_field(name="Entries", value=str(entrants_count), inline=True)
    embed.add_field(
        name="Offline Winners",
        value="Skipped when possible" if giveaway.get("online_only") else "Allowed",
        inline=True,
    )
    embed.add_field(name="Created", value=created_at_text, inline=True)
    embed.add_field(name="Ends", value=ends_at_text, inline=True)

    if giveaway.get("ended"):
        winners = giveaway.get("winners", [])
        winners_text = ", ".join(f"<@{winner_id}>" for winner_id in winners) if winners else "No valid entries."
        embed.add_field(name="Selected Winners", value=winners_text, inline=False)
    else:
        embed.add_field(name="How To Enter", value="Click the Enter button below.", inline=False)

    image_url = normalize_optional_url(giveaway.get("image_url"))
    if image_url:
        embed.set_image(url=image_url)

    embed.set_thumbnail(url=DISCORD_LOGO_URL)
    embed.set_footer(text="Sharks giveaway system")

    return embed


async def get_giveaway_channel(giveaway):
    channel = bot.get_channel(giveaway["channel_id"])
    if channel is None:
        channel = await bot.fetch_channel(giveaway["channel_id"])

    return channel


def get_cached_giveaway_member(guild, user_id):
    if guild is None:
        return None

    try:
        return guild.get_member(int(user_id))
    except (TypeError, ValueError):
        return None


def is_online_giveaway_member(member):
    return member is not None and member.status != discord.Status.offline


async def pick_giveaway_winners(giveaway, guild=None, excluded_user_ids=None, prefer_online=True):
    excluded_user_ids = {str(user_id) for user_id in (excluded_user_ids or [])}
    entrants = [
        str(user_id)
        for user_id in giveaway.get("entrants", [])
        if str(user_id) not in excluded_user_ids
    ]

    if not entrants:
        return [], False

    winner_count = min(giveaway["winner_count"], len(entrants))

    if prefer_online and guild is not None:
        online_entrants = [
            user_id
            for user_id in entrants
            if is_online_giveaway_member(get_cached_giveaway_member(guild, user_id))
        ]

        if online_entrants:
            winner_count = min(giveaway["winner_count"], len(online_entrants))
            return random.sample(online_entrants, winner_count), True

    return random.sample(entrants, winner_count), False


def mention_user_ids(user_ids):
    return ", ".join(f"<@{user_id}>" for user_id in user_ids) if user_ids else "No valid entries."


def normalize_optional_url(url):
    if not url:
        return None

    cleaned_url = str(url).strip()
    if not cleaned_url:
        return None

    if not cleaned_url.startswith(("http://", "https://")):
        return None

    return cleaned_url


def seconds_until(iso_time):
    ends_at = datetime.fromisoformat(iso_time)
    return max(0, (ends_at - utc_now()).total_seconds())


def schedule_giveaway_finish(giveaway):
    giveaway_id = giveaway.get("giveaway_id")

    if not giveaway_id or giveaway.get("ended"):
        return

    existing_task = giveaway_finish_tasks.get(giveaway_id)
    if existing_task and not existing_task.done():
        return

    giveaway_finish_tasks[giveaway_id] = asyncio.create_task(
        finish_giveaway_at_time(giveaway_id, giveaway["ends_at"])
    )


def schedule_all_open_giveaways():
    giveaways = load_giveaways()

    for giveaway in giveaways.values():
        schedule_giveaway_finish(giveaway)


async def finish_giveaway_at_time(giveaway_id, ends_at):
    delay = seconds_until(ends_at)

    if delay > 0:
        await discord.utils.sleep_until(datetime.fromisoformat(ends_at))

    await finish_giveaway_by_id(giveaway_id)


async def finish_giveaway_by_id(giveaway_id):
    if giveaway_id in giveaway_finishes_in_progress:
        return False

    giveaway_finishes_in_progress.add(giveaway_id)

    try:
        giveaways = load_giveaways()
        giveaway = giveaways.get(giveaway_id)

        if giveaway is None or giveaway.get("ended"):
            return False

        ends_at = datetime.fromisoformat(giveaway["ends_at"])
        if ends_at > utc_now():
            schedule_giveaway_finish(giveaway)
            return False

        ended_at = utc_now()
        channel = await get_giveaway_channel(giveaway)
        prefer_online = giveaway.get("online_only", False)
        winners, used_online_pool = await pick_giveaway_winners(
            giveaway,
            channel.guild,
            prefer_online=prefer_online,
        )

        giveaway["ended"] = True
        giveaway["ended_at"] = ended_at.isoformat()
        giveaway["winners"] = winners
        giveaway["online_winners_only"] = used_online_pool

        message = await channel.fetch_message(giveaway["message_id"])
        await message.edit(embed=make_giveaway_embed(giveaway), view=GiveawayEndedView())

        winners_text = mention_user_ids(winners)
        online_note = "\nOffline entrants were skipped." if used_online_pool else ""
        await channel.send(
            f"{EMOJI_GIFT} Giveaway `{giveaway['giveaway_id']}` ended for **{giveaway['name']}**.\n"
            f"Winner(s): {winners_text}{online_note}"
        )
        giveaways[giveaway_id] = giveaway
        save_giveaways(giveaways)
        return True
    except (discord.HTTPException, OSError, TimeoutError) as error:
        giveaway["ended"] = False
        giveaway["ended_at"] = None
        giveaway["winners"] = []
        giveaways[giveaway_id] = giveaway
        save_giveaways(giveaways)
        print(f"Could not finish giveaway {giveaway['giveaway_id']} cleanly: {error}")
        return False
    finally:
        giveaway_finishes_in_progress.discard(giveaway_id)
        task = giveaway_finish_tasks.get(giveaway_id)

        if task and task.done():
            giveaway_finish_tasks.pop(giveaway_id, None)


def should_forward_gmod_line(line):
    return "PARTY CHAT" in line.upper()


def clean_gmod_party_chat(line):
    match = GMOD_PARTY_CHAT_PATTERN.search(line)

    if not match:
        return None

    return {
        "name": match.group("name").strip(),
        "message": match.group("message").strip(),
    }


def message_contains_name(message_lower, name):
    clean_name = name.strip()

    if len(clean_name) < 3:
        return False

    name_pattern = rf"(?<!\w){re.escape(clean_name.lower())}(?!\w)"
    return re.search(name_pattern, message_lower) is not None


def find_party_chat_mentions(sender_name, message):
    bindings = load_bindings()
    mentioned_users = []
    mentioned_user_ids = set()
    message_lower = message.lower()
    sender_lower = sender_name.lower()

    for user_id, binding in bindings.items():
        ingame_name = binding.get("ingame_name", "").strip()

        if not ingame_name:
            continue

        if ingame_name.lower() == sender_lower:
            continue

        if message_contains_name(message_lower, ingame_name):
            mentioned_users.append(f"<@{user_id}>")
            mentioned_user_ids.add(int(user_id))

    if mentioned_users:
        return mentioned_users

    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue

            possible_names = {
                member.nick or "",
                member.display_name or "",
                member.name or "",
                str(member) or "",
            }

            possible_names = {name.strip() for name in possible_names if name.strip()}

            if any(name.lower() == sender_lower for name in possible_names):
                continue

            if member.id in mentioned_user_ids:
                continue

            if any(message_contains_name(message_lower, name) for name in possible_names):
                mentioned_users.append(member.mention)
                mentioned_user_ids.add(member.id)

    return mentioned_users


def make_gmod_party_chat_webhook_message(chat):
    timestamp = format_discord_time(utc_now().isoformat())
    mentioned_users = find_party_chat_mentions(chat["name"], chat["message"])
    mentioned_text = ", ".join(mentioned_users) if mentioned_users else "None"

    return (
        f"**Party Chat:** `{chat['name']}`: {chat['message']}\n"
        f"**Mentioned:** {mentioned_text}\n"
        f"**Date/Time:** {timestamp}"
    )
async def send_printer_webhook(amount):
    cut = round(amount * (PRINTER_CUT_PERCENT / 100))
    owner_amount = amount - cut

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "content": (
            f"{EMOJI_MONEY} **Printer Collection**\n\n"
            f"**{PRINTER_COLLECTOR_NAME} Collected:**\n"
            f"Total: ${amount:,}\n"
            f"{PRINTER_CUT_PERCENT}% Cut: ${cut:,}\n"
            f"Owner Receives: ${owner_amount:,}\n"
            f"Timestamp: {timestamp}"
        )
    }

    async with aiohttp.ClientSession() as session:
        await session.post(PRINTER_WEBHOOK_URL, json=payload)

async def send_gmod_webhook(message):
    if not GMOD_WEBHOOK_URL:
        return

    payload = {"content": message[:1900]}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GMOD_WEBHOOK_URL, json=payload, timeout=10) as response:
                if response.status >= 300:
                    print(f"GMod webhook failed with status {response.status}.")
    except (aiohttp.ClientError, OSError, TimeoutError) as error:
        print(f"GMod webhook skipped because Discord/network failed: {error}")


async def fetch_steam_profile(steam_id_64):
    if not STEAM_API_KEY or STEAM_API_KEY == "PUT_YOUR_STEAM_API_KEY_HERE":
        return None

    url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    params = {
        "key": STEAM_API_KEY,
        "steamids": steam_id_64,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status != 200:
                    return None

                data = await response.json()
    except (aiohttp.ClientError, TimeoutError, OSError, json.JSONDecodeError):
        return None

    players = data.get("response", {}).get("players", [])
    if not players:
        return None

    return players[0]


async def fetch_steam_profile_cached(steam_id_64):
    cached = steam_profile_cache.get(steam_id_64)
    now = utc_now()

    if cached:
        cached_at = cached.get("cached_at")
        if cached_at and (now - cached_at).total_seconds() < 300:
            return cached.get("profile")

    profile = await fetch_steam_profile(steam_id_64)
    steam_profile_cache[steam_id_64] = {
        "cached_at": now,
        "profile": profile,
    }
    return profile


def iso_or_none(value):
    if value is None:
        return None

    return value.isoformat()


def dashboard_json(data, status=200):
    response = web.json_response(data, status=status)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def member_activity_names(member):
    activities = []

    for activity in getattr(member, "activities", []):
        activity_name = getattr(activity, "name", None)
        activity_type = getattr(activity, "type", None)
        activity_type_name = activity_type.name if activity_type else "unknown"

        if activity_name:
            activities.append({
                "name": activity_name,
                "type": activity_type_name,
            })

    return activities


async def get_dashboard_guild(guild_id=None):
    if guild_id:
        try:
            guild_id = int(guild_id)
        except (TypeError, ValueError):
            return None

        guild = bot.get_guild(guild_id)
        if guild:
            return guild

        try:
            return await bot.fetch_guild(guild_id)
        except (discord.NotFound, discord.HTTPException):
            return None

    if bot.guilds:
        return bot.guilds[0]

    return None


async def make_dashboard_member(member, binding):
    steam_profile = None

    if binding and binding.get("steam_id_64"):
        steam_profile = await fetch_steam_profile_cached(binding["steam_id_64"])

    return {
        "discord": {
            "id": str(member.id),
            "username": member.name,
            "global_name": getattr(member, "global_name", None),
            "display_name": member.display_name,
            "nickname": member.nick,
            "mention": member.mention,
            "bot": member.bot,
            "status": str(member.status),
            "avatar_url": member.display_avatar.url,
            "joined_at": iso_or_none(member.joined_at),
            "created_at": iso_or_none(member.created_at),
            "premium_since": iso_or_none(member.premium_since),
            "top_role": member.top_role.name if member.top_role else None,
            "roles": [role.name for role in member.roles if role.name != "@everyone"],
            "activities": member_activity_names(member),
            "pending": getattr(member, "pending", False),
        },
        "binding": binding,
        "steam": {
            "steam_id_64": binding.get("steam_id_64") if binding else None,
            "ingame_name": binding.get("ingame_name") if binding else None,
            "bound_at": binding.get("bound_at") if binding else None,
            "personaname": steam_profile.get("personaname") if steam_profile else None,
            "profile_url": steam_profile.get("profileurl") if steam_profile else None,
            "avatar_url": steam_profile.get("avatarfull") if steam_profile else None,
            "country": steam_profile.get("loccountrycode") if steam_profile else None,
            "profile_state": steam_profile.get("profilestate") if steam_profile else None,
            "visibility_state": steam_profile.get("communityvisibilitystate") if steam_profile else None,
            "last_logoff": steam_profile.get("lastlogoff") if steam_profile else None,
            "persona_state": steam_profile.get("personastate") if steam_profile else None,
            "current_game": steam_profile.get("gameextrainfo") if steam_profile else None,
        },
    }


async def dashboard_home(request):
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")


async def dashboard_options(request):
    return dashboard_json({})


async def dashboard_guilds(request):
    guilds = []

    for guild in bot.guilds:
        guilds.append({
            "id": str(guild.id),
            "name": guild.name,
            "member_count": guild.member_count,
            "icon_url": guild.icon.url if guild.icon else None,
        })

    return dashboard_json({"guilds": guilds})


async def dashboard_members(request):
    guild = await get_dashboard_guild(request.query.get("guild_id"))

    if guild is None:
        return dashboard_json({"error": "The bot is not in any guild yet."}, status=404)

    bindings = load_bindings()

    if hasattr(guild, "chunked") and not guild.chunked:
        try:
            await guild.chunk(cache=True)
        except discord.HTTPException:
            pass

    members = sorted(getattr(guild, "members", []), key=lambda member: member.display_name.lower())
    member_rows = []

    for member in members:
        binding = bindings.get(str(member.id))
        member_rows.append(await make_dashboard_member(member, binding))

    bound_discord_ids = {str(member.id) for member in members}
    missing_bound_members = []

    for discord_id, binding in bindings.items():
        if discord_id in bound_discord_ids:
            continue

        missing_bound_members.append({
            "discord": {
                "id": str(discord_id),
                "username": binding.get("username"),
                "global_name": None,
                "display_name": binding.get("username"),
                "nickname": None,
                "mention": f"<@{discord_id}>",
                "bot": False,
                "status": "not in cache",
                "avatar_url": None,
                "joined_at": None,
                "created_at": None,
                "premium_since": None,
                "top_role": None,
                "roles": [],
                "activities": [],
                "pending": False,
            },
            "binding": binding,
            "steam": {
                "steam_id_64": binding.get("steam_id_64"),
                "ingame_name": binding.get("ingame_name"),
                "bound_at": binding.get("bound_at"),
                "personaname": None,
                "profile_url": None,
                "avatar_url": None,
                "country": None,
                "profile_state": None,
                "visibility_state": None,
                "last_logoff": None,
                "persona_state": None,
                "current_game": None,
            },
        })

    return dashboard_json({
        "guild": {
            "id": str(guild.id),
            "name": guild.name,
            "member_count": guild.member_count,
            "icon_url": guild.icon.url if guild.icon else None,
        },
        "members": member_rows,
        "bound_missing_from_cache": missing_bound_members,
        "total_members_loaded": len(member_rows),
        "total_bound": len(bindings),
    })


async def start_dashboard():
    global dashboard_runner

    if dashboard_runner is not None:
        return

    app = web.Application()
    app.router.add_get("/", dashboard_home)
    app.router.add_get("/api/guilds", dashboard_guilds)
    app.router.add_get("/api/members", dashboard_members)
    app.router.add_options("/{tail:.*}", dashboard_options)

    dashboard_runner = web.AppRunner(app)
    await dashboard_runner.setup()
    site = web.TCPSite(dashboard_runner, WEB_DASHBOARD_HOST, WEB_DASHBOARD_PORT)
    await site.start()
    print(f"Sharks dashboard is running at http://{WEB_DASHBOARD_HOST}:{WEB_DASHBOARD_PORT}")


def make_blacklist_embed(entry):
    avatar_url = entry.get("avatar_url") or DISCORD_LOGO_URL
    profile_url = entry.get("profile_url") or f"https://steamcommunity.com/profiles/{entry['steam_id_64']}/"

    embed = discord.Embed(
        title=f"{EMOJI_CROSS} Gang Blacklist",
        description="This player is blacklisted from the Sharks gang/base.",
        color=discord.Color.red(),
        timestamp=datetime.fromisoformat(entry["created_at"]),
    )
    embed.set_thumbnail(url=avatar_url)
    embed.add_field(name="Blacklist ID", value=entry["blacklist_id"], inline=True)
    embed.add_field(name=f"{EMOJI_GAME} In-game Name", value=entry["ingame_name"], inline=True)
    embed.add_field(name="SteamID64", value=f"`{entry['steam_id_64']}`", inline=False)
    embed.add_field(name="Steam Profile", value=f"[Open Profile]({profile_url})", inline=False)
    embed.add_field(name="Reason", value=entry["reason"], inline=False)
    embed.add_field(name=f"{EMOJI_STAFF} Blacklisted By", value=entry["staff_name"], inline=False)
    embed.add_field(name=f"{EMOJI_CLOCK} Time", value=format_discord_time(entry["created_at"]), inline=False)

    if not entry.get("avatar_url"):
        embed.add_field(name="Steam Avatar", value="Unable to fetch Pfp.", inline=False)

    embed.set_footer(text="Sharks blacklist system")

    return embed


async def send_app_error(interaction, message):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.NotFound:
        print("Could not reply to Discord because the interaction expired.")


async def sync_starter_roles():
    if GANG_MEMBER_ROLE_ID == 0 or STARTER_ROLE_ID == 0:
        print("Starter role sync skipped because GANG_MEMBER_ROLE_ID or STARTER_ROLE_ID is not set.")
        return 0

    added_count = 0

    for guild in bot.guilds:
        gang_role = guild.get_role(GANG_MEMBER_ROLE_ID)
        starter_role = guild.get_role(STARTER_ROLE_ID)

        if gang_role is None or starter_role is None:
            print(f"Starter role sync skipped in {guild.name}: role ID not found.")
            continue

        for member in gang_role.members:
            if member.bot or starter_role in member.roles:
                continue

            try:
                await member.add_roles(starter_role, reason="Has gang member role, syncing starter role")
                added_count += 1
            except discord.Forbidden:
                print("Could not add starter role. Move the bot role above the starter role.")
                return added_count
            except discord.HTTPException as error:
                print(f"Could not add starter role to {member}: {error}")

    if added_count:
        print(f"Starter role sync added the starter role to {added_count} member(s).")

    return added_count


class LOAModal(discord.ui.Modal, title="Request LOA"):
    reason = discord.ui.TextInput(
        label="Reason for LOA",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )
    start_date = discord.ui.TextInput(
        label="Start date",
        placeholder="Example: 2026-05-25",
        max_length=50,
        required=True,
    )
    end_date = discord.ui.TextInput(
        label="End date",
        placeholder="Example: 2026-05-30",
        max_length=50,
        required=True,
    )
    notes = discord.ui.TextInput(
        label="Notes",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        if LOA_PEOPLE_CHANNEL_ID == 0:
            await interaction.followup.send(
                f"{EMOJI_WARNING} LOA_PEOPLE_CHANNEL_ID must be set in the bot file.",
                ephemeral=True,
            )
            return

        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            member = await interaction.guild.fetch_member(interaction.user.id)

        loa_people_channel = bot.get_channel(LOA_PEOPLE_CHANNEL_ID)
        if loa_people_channel is None:
            loa_people_channel = await bot.fetch_channel(LOA_PEOPLE_CHANNEL_ID)

        role_status = "LOA role not configured."
        if LOA_ROLE_ID != 0:
            loa_role = interaction.guild.get_role(LOA_ROLE_ID)

            if loa_role is None:
                role_status = "LOA role ID was set, but the role was not found."
            else:
                try:
                    await member.add_roles(loa_role, reason="LOA requested through Sharks bot")
                    role_status = f"Added {loa_role.mention} role."
                except discord.Forbidden:
                    role_status = "Could not add LOA role. Move the bot role above the LOA role."

        people_embed = make_loa_people_embed(
            member,
            str(self.start_date),
            str(self.end_date),
            str(self.notes),
        )

        await loa_people_channel.send(embed=people_embed)

        await interaction.followup.send(
            f"{EMOJI_CHECK} Your LOA has been posted. {role_status}",
            ephemeral=True,
        )


class LOAView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request LOA",
        style=discord.ButtonStyle.primary,
        emoji=EMOJI_CALENDAR,
        custom_id="sharks_request_loa",
    )
    async def request_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LOAModal())


class BindModal(discord.ui.Modal, title="Bind Your Steam Account"):
    steam_id_64 = discord.ui.TextInput(
        label="SteamID64",
        placeholder="Example: 76561198000000000",
        min_length=17,
        max_length=17,
        required=True,
    )
    ingame_name = discord.ui.TextInput(
        label="In-game name",
        placeholder="Your DarkRP character/name",
        max_length=32,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        steam_id = str(self.steam_id_64).strip()
        ingame_name = str(self.ingame_name).strip()

        if not is_valid_steam_id_64(steam_id):
            await interaction.followup.send(
                f"{EMOJI_WARNING} SteamID64 must be exactly 17 numbers.",
                ephemeral=True,
            )
            return

        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            member = await interaction.guild.fetch_member(interaction.user.id)

        bindings = load_bindings()
        binding = {
            "user_id": member.id,
            "username": str(member),
            "ingame_name": ingame_name,
            "steam_id_64": steam_id,
            "bound_at": utc_now().isoformat(),
        }
        bindings[str(member.id)] = binding
        save_bindings(bindings)

        nickname_status = "Nickname updated."
        try:
            await member.edit(nick=ingame_name, reason="Bound SteamID64 through Sharks bot")
        except discord.Forbidden:
            nickname_status = "Could not update nickname. Move the bot role higher."

        role_status = "Verified role not configured."
        if VERIFIED_ROLE_ID != 0:
            verified_role = interaction.guild.get_role(VERIFIED_ROLE_ID)

            if verified_role is None:
                role_status = "Verified role ID was set, but the role was not found."
            else:
                try:
                    await member.add_roles(verified_role, reason="Bound SteamID64 through Sharks bot")
                    role_status = f"Added {verified_role.mention} role."
                except discord.Forbidden:
                    role_status = "Could not add verified role. Move the bot role above the verified role."

        embed = make_bind_embed(member, binding, nickname_status, role_status)
        await interaction.followup.send(embed=embed, ephemeral=True)


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Enter",
        style=discord.ButtonStyle.primary,
        emoji=EMOJI_GIFT,
        custom_id="sharks_giveaway_enter",
    )
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaways = load_giveaways()
        giveaway = None

        for saved_giveaway in giveaways.values():
            if saved_giveaway.get("message_id") == interaction.message.id:
                giveaway = saved_giveaway
                break

        if giveaway is None:
            await interaction.response.send_message(
                f"{EMOJI_WARNING} I could not find this giveaway in the save file.",
                ephemeral=True,
            )
            return

        if giveaway.get("ended"):
            await interaction.response.send_message(
                f"{EMOJI_WARNING} This giveaway has already ended.",
                ephemeral=True,
            )
            return

        user_id = interaction.user.id
        entrants = giveaway.setdefault("entrants", [])

        if user_id in entrants:
            await interaction.response.send_message(
                f"{EMOJI_WARNING} You are already entered in this giveaway.",
                ephemeral=True,
            )
            return

        entrants.append(user_id)
        giveaways[giveaway["giveaway_id"]] = giveaway
        save_giveaways(giveaways)

        await interaction.message.edit(embed=make_giveaway_embed(giveaway), view=GiveawayView())
        await interaction.response.send_message(
            f"{EMOJI_CHECK} You entered giveaway `{giveaway['giveaway_id']}`.",
            ephemeral=True,
        )


class GiveawayEndedView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label="Giveaway Ended",
            style=discord.ButtonStyle.secondary,
            emoji=EMOJI_GIFT,
            disabled=True,
            custom_id="sharks_giveaway_ended",
        )
        self.add_item(button)


@bot.event
async def on_ready():
    global commands_synced

    if not commands_synced:
        bot.add_view(LOAView())
        bot.add_view(GiveawayView())
        await bot.tree.sync()
        commands_synced = True

    if BOT_STATUS_CHANNEL_ID != 0 and not update_bot_status.is_running():
        update_bot_status.start()

    if GMOD_WEBHOOK_URL and is_gmod_webhook_enabled() and not watch_gmod_console_log.is_running():
        watch_gmod_console_log.start()

    if not finish_giveaways.is_running():
        finish_giveaways.start()

    if not sync_starter_roles_loop.is_running():
        sync_starter_roles_loop.start()

    schedule_all_open_giveaways()

    await start_dashboard()
    await sync_starter_roles()

    print(f"Sharks bot is online as {bot.user}")


@bot.event
async def on_member_update(before, after):
    if GANG_MEMBER_ROLE_ID == 0 or STARTER_ROLE_ID == 0:
        return

    if before.roles == after.roles:
        return

    gang_role = after.guild.get_role(GANG_MEMBER_ROLE_ID)
    starter_role = after.guild.get_role(STARTER_ROLE_ID)

    if gang_role is None or starter_role is None:
        return

    had_gang_role = gang_role in before.roles
    has_gang_role = gang_role in after.roles
    has_starter_role = starter_role in after.roles

    if not had_gang_role and has_gang_role and not has_starter_role and not after.bot:
        try:
            await after.add_roles(starter_role, reason="Gang member role added, syncing starter role")
            print(f"Added starter role to {after}.")
        except discord.Forbidden:
            print("Could not add starter role. Move the bot role above the starter role.")
        except discord.HTTPException as error:
            print(f"Could not add starter role to {after}: {error}")


@tasks.loop(seconds=10)
async def update_bot_status():
    global status_message_cache

    if BOT_STATUS_CHANNEL_ID == 0:
        return

    try:
        status_channel = bot.get_channel(BOT_STATUS_CHANNEL_ID)
        if status_channel is None:
            status_channel = await bot.fetch_channel(BOT_STATUS_CHANNEL_ID)

        embed = make_status_embed()
        saved_message = load_status_message()

        if status_message_cache is not None:
            try:
                await status_message_cache.edit(embed=embed)
                return
            except (discord.NotFound, discord.Forbidden):
                status_message_cache = None

        if saved_message:
            try:
                message = await status_channel.fetch_message(saved_message["message_id"])
                await message.edit(embed=embed)
                status_message_cache = message
                return
            except (discord.NotFound, discord.Forbidden):
                pass

        message = await status_channel.send(embed=embed)
        status_message_cache = message
        save_status_message(status_channel.id, message.id)
    except (aiohttp.ClientError, discord.HTTPException, OSError, TimeoutError) as error:
        print(f"Status heartbeat skipped because Discord/network timed out: {error}")


@update_bot_status.error
async def update_bot_status_error(error):
    print(f"Status heartbeat task error was handled: {error}")


@tasks.loop(seconds=17280)
async def sync_starter_roles_loop():
    await sync_starter_roles()


@sync_starter_roles_loop.error
async def sync_starter_roles_loop_error(error):
    print(f"Starter role sync task error was handled: {error}")


async def send_payout_webhook(message):
    payload = {"content": message[:1900]}

    async with aiohttp.ClientSession() as session:
        await session.post(PAYOUT_WEBHOOK_URL, json=payload)

@tasks.loop(seconds=1)
async def watch_gmod_console_log():
    global gmod_log_position

    if not GMOD_LOG_FILE.exists():
        return

    try:
        with GMOD_LOG_FILE.open("r", encoding="utf-8", errors="ignore") as file:

            if gmod_log_position is None:
                file.seek(0, 2)
                gmod_log_position = file.tell()
                print(f"Watching GMod console log: {GMOD_LOG_FILE}")
                return

            file.seek(0, 2)
            end_position = file.tell()

            if end_position < gmod_log_position:
                gmod_log_position = 0

            file.seek(gmod_log_position)
            lines = file.readlines()
            gmod_log_position = file.tell()

    except OSError as error:
        print(f"Could not read GMod console log: {error}")
        return

    for line in lines:
        clean_line = line.strip()

        if not clean_line:
            continue

        if "[Printer] You withdrew $" in clean_line:
            match = re.search(r"\$([\d,]+)", clean_line)

            if match:
                amount = int(match.group(1).replace(",", ""))
                print(f"Detected printer withdrawal: ${amount:,}")

                await send_printer_webhook(amount)
                continue

        if should_forward_gmod_line(clean_line):
            chat = clean_gmod_party_chat(clean_line)

            if chat:
                message = make_gmod_party_chat_webhook_message(chat)
                await send_gmod_webhook(message)

@watch_gmod_console_log.error
async def watch_gmod_console_log_error(error):
    print(f"GMod console log task error was handled: {error}")


@tasks.loop(seconds=5)
async def finish_giveaways():
    giveaways = load_giveaways()
    now = utc_now()

    for giveaway in giveaways.values():
        if giveaway.get("ended"):
            continue

        ends_at = datetime.fromisoformat(giveaway["ends_at"])
        if ends_at > now:
            schedule_giveaway_finish(giveaway)
            continue

        await finish_giveaway_by_id(giveaway["giveaway_id"])


@finish_giveaways.error
async def finish_giveaways_error(error):
    print(f"Giveaway finisher task error was handled: {error}")


@bot.tree.command(name="postbase", description="Post the Sharks forever base embed in this channel.")
@app_commands.checks.has_permissions(manage_messages=True)
async def postbase(interaction: discord.Interaction):
    embed = make_base_embed()
    message = await interaction.channel.send(embed=embed)
    save_base_message(interaction.channel_id, message.id)

    await interaction.response.send_message(
        f"{EMOJI_SHARK} Base embed posted and saved for future updates.",
        ephemeral=True,
    )


@bot.tree.command(name="updatebase", description="Update the Sharks base information embed.")
@app_commands.describe(
    party_name="The current party name",
    party_password="The current party password",
    base_location="The current base location",
)
@app_commands.checks.has_permissions(manage_messages=True)
async def updatebase(
    interaction: discord.Interaction,
    party_name: str,
    party_password: str,
    base_location: str,
):
    saved_message = load_base_message()

    if not saved_message:
        await interaction.response.send_message(
            f"{EMOJI_WARNING} No base embed has been posted yet. Use /postbase first.",
            ephemeral=True,
        )
        return

    channel = bot.get_channel(saved_message["channel_id"])
    if channel is None:
        channel = await bot.fetch_channel(saved_message["channel_id"])

    message = await channel.fetch_message(saved_message["message_id"])
    embed = make_base_embed(party_name, party_password, base_location)

    await message.edit(embed=embed)
    await interaction.response.send_message(
        f"{EMOJI_CHECK} Base information updated.",
        ephemeral=True,
    )


@bot.tree.command(name="postloa", description="Post the Sharks LOA request panel in this channel.")
@app_commands.checks.has_permissions(manage_messages=True)
async def postloa(interaction: discord.Interaction):
    embed = make_loa_panel_embed()

    await interaction.channel.send(embed=embed, view=LOAView())
    await interaction.response.send_message(
        f"{EMOJI_CHECK} LOA request panel posted.",
        ephemeral=True,
    )


@bot.tree.command(name="poststatus", description="Post or reset the Sharks bot status embed in this channel.")
@app_commands.checks.has_permissions(manage_messages=True)
async def poststatus(interaction: discord.Interaction):
    global status_message_cache

    embed = make_status_embed()
    message = await interaction.channel.send(embed=embed)
    status_message_cache = message
    save_status_message(interaction.channel_id, message.id)

    await interaction.response.send_message(
        f"{EMOJI_CHECK} Bot status embed posted. Set BOT_STATUS_CHANNEL_ID to this channel ID if it is not set yet.",
        ephemeral=True,
    )


@bot.tree.command(name="syncstarterroles", description="Give starter role to everyone with gang member role.")
@app_commands.checks.has_permissions(manage_messages=True)
async def syncstarterroles(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    added_count = await sync_starter_roles()

    await interaction.followup.send(
        f"{EMOJI_CHECK} Starter role sync complete. Added starter role to {added_count} member(s).",
        ephemeral=True,
    )


@bot.tree.command(name="gmodwebhook", description="Turn GMod console webhook forwarding on, off, or check status.")
@app_commands.describe(mode="Choose whether GMod webhook forwarding should be on, off, or show status")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="on", value="on"),
        app_commands.Choice(name="off", value="off"),
        app_commands.Choice(name="status", value="status"),
    ]
)
@app_commands.checks.has_permissions(manage_messages=True)
async def gmodwebhook(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    global gmod_log_position

    if mode.value == "status":
        saved_status = "enabled" if is_gmod_webhook_enabled() else "disabled"
        running_status = "running" if watch_gmod_console_log.is_running() else "stopped"

        await interaction.response.send_message(
            f"{EMOJI_GAME} GMod webhook is **{saved_status}** and the watcher is **{running_status}**.",
            ephemeral=True,
        )
        return

    if mode.value == "on":
        save_gmod_webhook_settings(True)

        if not watch_gmod_console_log.is_running():
            gmod_log_position = None
            watch_gmod_console_log.start()

        await interaction.response.send_message(
            f"{EMOJI_CHECK} GMod webhook forwarding enabled.",
            ephemeral=True,
        )
        return

    save_gmod_webhook_settings(False)

    if watch_gmod_console_log.is_running():
        watch_gmod_console_log.stop()

    await interaction.response.send_message(
        f"{EMOJI_CHECK} GMod webhook forwarding disabled.",
        ephemeral=True,
    )


@bot.tree.command(name="creategiveaway", description="Create a Sharks giveaway with an Enter button.")
@app_commands.describe(
    name="Giveaway prize/name",
    description="Giveaway description",
    timer="How long it should run, like 30s, 10m, 2h, or 1d",
    winners="How many winners should be picked",
    online_only="Yes skips offline winners when possible. No allows anyone who entered.",
    image_url="Optional image/banner URL for the giveaway",
)
@app_commands.checks.has_permissions(manage_messages=True)
async def creategiveaway(
    interaction: discord.Interaction,
    name: str,
    description: str,
    timer: str,
    winners: int,
    online_only: bool = False,
    image_url: str | None = None,
):
    await interaction.response.defer(ephemeral=True, thinking=True)

    duration_seconds = parse_duration_seconds(timer)
    if duration_seconds is None:
        await interaction.followup.send(
            f"{EMOJI_WARNING} Timer must look like `30s`, `10m`, `2h`, or `1d`.",
            ephemeral=True,
        )
        return

    if winners < 1 or winners > 20:
        await interaction.followup.send(
            f"{EMOJI_WARNING} Winners must be between 1 and 20.",
            ephemeral=True,
        )
        return

    image_url = normalize_optional_url(image_url)
    giveaways = load_giveaways()
    created_at = utc_now()
    ends_at = datetime.fromtimestamp(created_at.timestamp() + duration_seconds, timezone.utc)
    giveaway_id = get_next_giveaway_id(giveaways)

    giveaway = {
        "giveaway_id": giveaway_id,
        "name": name,
        "description": description,
        "winner_count": winners,
        "online_only": online_only,
        "image_url": image_url,
        "channel_id": interaction.channel_id,
        "message_id": None,
        "created_by_id": interaction.user.id,
        "created_by_name": str(interaction.user),
        "created_at": created_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "ended": False,
        "ended_at": None,
        "entrants": [],
        "winners": [],
    }

    message = await interaction.channel.send(embed=make_giveaway_embed(giveaway), view=GiveawayView())
    giveaway["message_id"] = message.id
    giveaways[giveaway_id] = giveaway
    save_giveaways(giveaways)
    schedule_giveaway_finish(giveaway)

    await interaction.followup.send(
        f"{EMOJI_CHECK} Giveaway `{giveaway_id}` created. It ends {format_discord_time(giveaway['ends_at'])}.",
        ephemeral=True,
    )


@bot.tree.command(name="giveawayinfo", description="Pull up saved information about a giveaway.")
@app_commands.describe(giveaway_id="The giveaway ID, like GW-0001")
@app_commands.checks.has_permissions(manage_messages=True)
async def giveawayinfo(interaction: discord.Interaction, giveaway_id: str):
    giveaways = load_giveaways()
    giveaway = giveaways.get(giveaway_id.upper())

    if giveaway is None:
        await interaction.response.send_message(
            f"{EMOJI_WARNING} I could not find giveaway `{giveaway_id}`.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(embed=make_giveaway_embed(giveaway), ephemeral=True)


@bot.tree.command(name="rerollgiveaway", description="Reroll an ended Sharks giveaway.")
@app_commands.describe(
    giveaway_id="The giveaway ID, like GW-0001",
    online_only="Prefer online/idle/DND entrants and skip offline entrants when possible",
)
@app_commands.checks.has_permissions(manage_messages=True)
async def rerollgiveaway(
    interaction: discord.Interaction,
    giveaway_id: str,
    online_only: bool = True,
):
    await interaction.response.defer(ephemeral=True, thinking=True)

    giveaways = load_giveaways()
    giveaway = giveaways.get(giveaway_id.upper())

    if giveaway is None:
        await interaction.followup.send(
            f"{EMOJI_WARNING} I could not find giveaway `{giveaway_id}`.",
            ephemeral=True,
        )
        return

    if not giveaway.get("ended"):
        await interaction.followup.send(
            f"{EMOJI_WARNING} Giveaway `{giveaway['giveaway_id']}` has not ended yet.",
            ephemeral=True,
        )
        return

    previous_winners = [str(user_id) for user_id in giveaway.get("winners", [])]
    channel = await get_giveaway_channel(giveaway)
    new_winners, used_online_pool = await pick_giveaway_winners(
        giveaway,
        channel.guild,
        excluded_user_ids=previous_winners,
        prefer_online=online_only,
    )

    if not new_winners:
        await interaction.followup.send(
            f"{EMOJI_WARNING} I could not reroll `{giveaway['giveaway_id']}` because there are no other entrants.",
            ephemeral=True,
        )
        return

    reroll_entry = {
        "rerolled_at": utc_now().isoformat(),
        "rerolled_by_id": interaction.user.id,
        "rerolled_by_name": str(interaction.user),
        "old_winners": previous_winners,
        "new_winners": new_winners,
        "online_only": online_only,
    }
    giveaway.setdefault("rerolls", []).append(reroll_entry)
    giveaway["winners"] = new_winners
    giveaways[giveaway["giveaway_id"]] = giveaway
    save_giveaways(giveaways)

    try:
        message = await channel.fetch_message(giveaway["message_id"])
        await message.edit(embed=make_giveaway_embed(giveaway), view=GiveawayEndedView())
    except (discord.HTTPException, OSError, TimeoutError) as error:
        print(f"Could not update giveaway message after reroll {giveaway['giveaway_id']}: {error}")

    old_winners_text = mention_user_ids(previous_winners)
    new_winners_text = mention_user_ids(new_winners)
    online_note = "\nOffline entrants were skipped." if used_online_pool else ""
    await channel.send(
        f"{EMOJI_GIFT} Giveaway `{giveaway['giveaway_id']}` rerolled for **{giveaway['name']}**.\n"
        f"Previous winner(s): {old_winners_text}\n"
        f"New winner(s): {new_winners_text}{online_note}"
    )

    await interaction.followup.send(
        f"{EMOJI_CHECK} Giveaway `{giveaway['giveaway_id']}` rerolled.",
        ephemeral=True,
    )


@bot.tree.command(name="bind", description="Bind your SteamID64 and in-game name.")
async def bind(interaction: discord.Interaction):
    await interaction.response.send_modal(BindModal())


@bot.tree.command(name="steamid", description="Look up a member's saved SteamID64.")
@app_commands.describe(member="The Discord member to look up")
@app_commands.checks.has_permissions(manage_messages=True)
async def steamid(interaction: discord.Interaction, member: discord.Member):
    bindings = load_bindings()
    binding = bindings.get(str(member.id))

    if not binding:
        await interaction.response.send_message(
            f"{EMOJI_WARNING} {member.mention} has not used /bind yet.",
            ephemeral=True,
        )
        return

    embed = make_steamid_embed(member, binding)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="blacklist", description="Blacklist an in-game player from the gang/base.")
@app_commands.describe(
    ingame_name="The player's in-game name",
    steam_id_64="The player's SteamID64",
    reason="Why this player is blacklisted",
)
@app_commands.checks.has_permissions(manage_messages=True)
async def blacklist(interaction: discord.Interaction, ingame_name: str, steam_id_64: str, reason: str):
    await interaction.response.defer(ephemeral=True, thinking=True)

    steam_id = steam_id_64.strip()
    if not is_valid_steam_id_64(steam_id):
        await interaction.followup.send(
            f"{EMOJI_WARNING} SteamID64 must be exactly 17 numbers.",
            ephemeral=True,
        )
        return

    if BLACKLIST_CHANNEL_ID == 0:
        await interaction.followup.send(
            f"{EMOJI_WARNING} BLACKLIST_CHANNEL_ID is not set in the bot file yet.",
            ephemeral=True,
        )
        return

    blacklist_entries = load_blacklist()
    steam_profile = await fetch_steam_profile(steam_id)
    created_at = utc_now().isoformat()

    entry = {
        "blacklist_id": get_next_blacklist_id(blacklist_entries),
        "ingame_name": ingame_name,
        "steam_id_64": steam_id,
        "reason": reason,
        "staff_id": interaction.user.id,
        "staff_name": str(interaction.user),
        "created_at": created_at,
        "steam_name": None,
        "profile_url": None,
        "avatar_url": None,
    }

    if steam_profile:
        entry["steam_name"] = steam_profile.get("personaname")
        entry["profile_url"] = steam_profile.get("profileurl")
        entry["avatar_url"] = steam_profile.get("avatarfull")

    blacklist_entries[steam_id] = entry
    save_blacklist(blacklist_entries)

    blacklist_channel = bot.get_channel(BLACKLIST_CHANNEL_ID)
    if blacklist_channel is None:
        blacklist_channel = await bot.fetch_channel(BLACKLIST_CHANNEL_ID)

    embed = make_blacklist_embed(entry)
    await blacklist_channel.send(embed=embed)

    avatar_status = "Steam Pfp fetched." if entry.get("avatar_url") else "Unable to fetch Pfp, used Sharks Pfp."
    await interaction.followup.send(
        f"{EMOJI_CHECK} Blacklist `{entry['blacklist_id']}` posted. {avatar_status}",
        ephemeral=True,
    )


@bot.tree.command(name="warn", description="Warn a member and DM them the warning details.")
@app_commands.describe(member="The member to warn", reason="The reason for the warning")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(thinking=True)

    warnings = load_warnings()
    user_id = str(member.id)
    created_at = utc_now().isoformat()

    warning = {
        "warn_id": get_next_warn_id(warnings),
        "user_id": member.id,
        "username": str(member),
        "display_name": member.display_name,
        "nickname": member.nick,
        "moderator_id": interaction.user.id,
        "moderator_name": str(interaction.user),
        "reason": reason,
        "created_at": created_at,
    }

    warnings.setdefault(user_id, []).append(warning)
    save_warnings(warnings)

    dm_sent = True
    try:
        await member.send(embed=make_warning_dm_embed(member, warning))
    except discord.Forbidden:
        dm_sent = False

    embed = make_warning_embed(member, warning)
    footer = "DM sent to warned member" if dm_sent else "Could not DM this member"
    embed.set_footer(text=footer)

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="viewwarnings", description="View all warnings for a member.")
@app_commands.describe(member="The member whose warnings you want to view")
@app_commands.checks.has_permissions(manage_messages=True)
async def viewwarnings(interaction: discord.Interaction, member: discord.Member):
    warnings = load_warnings()
    user_warnings = warnings.get(str(member.id), [])
    embed = make_warning_list_embed(member, user_warnings)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="removewarn", description="Remove one warning from a member by warning ID.")
@app_commands.describe(member="The member whose warning should be removed", warn_id="The warning ID to remove")
@app_commands.checks.has_permissions(manage_messages=True)
async def removewarn(interaction: discord.Interaction, member: discord.Member, warn_id: str):
    warnings = load_warnings()
    user_id = str(member.id)
    user_warnings = warnings.get(user_id, [])
    warning_to_remove = None

    for warning in user_warnings:
        if warning["warn_id"].lower() == warn_id.lower():
            warning_to_remove = warning
            break

    if warning_to_remove is None:
        await interaction.response.send_message(
            f"{EMOJI_WARNING} I could not find warning `{warn_id}` for {member.mention}.",
            ephemeral=True,
        )
        return

    user_warnings.remove(warning_to_remove)

    if user_warnings:
        warnings[user_id] = user_warnings
    else:
        warnings.pop(user_id, None)

    save_warnings(warnings)

    await interaction.response.send_message(
        f"{EMOJI_CHECK} Removed warning `{warning_to_remove['warn_id']}` from {member.mention}.\n"
        f"Reason was: {warning_to_remove['reason']}",
        ephemeral=True,
    )


@postbase.error
@updatebase.error
@postloa.error
@poststatus.error
@syncstarterroles.error
@gmodwebhook.error
@creategiveaway.error
@giveawayinfo.error
@rerollgiveaway.error
@bind.error
@steamid.error
@blacklist.error
@warn.error
@viewwarnings.error
@removewarn.error
async def command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await send_app_error(
            interaction,
            f"{EMOJI_CROSS} You need the Manage Messages permission to use this command.",
        )
        return

    await send_app_error(
        interaction,
        f"{EMOJI_CROSS} Something went wrong while running that command.",
    )
    print(f"Command error: {error}")


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_BOT_TOKEN environment variable.")


    bot.run(TOKEN)
