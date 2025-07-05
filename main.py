import discord
from discord.ext import commands
from discord import app_commands
import datetime
from collections import defaultdict, deque
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

spam_settings = {}
user_messages = defaultdict(lambda: defaultdict(deque))

class SpamPrevention(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="도배방지", description="도배 방지를 설정합니다.")
    @app_commands.describe(channel="감시할 채널", seconds="N초 안에", count="N회 이상")
    async def spam_protect(self, interaction: discord.Interaction, channel: discord.TextChannel, seconds: int, count: int):
        spam_settings[interaction.guild_id] = {
            "channel_id": channel.id,
            "seconds": seconds,
            "count": count,
            "enabled": True
        }
        await interaction.response.send_message(
            f"✅ 도배방지 설정 완료: {channel.mention} | {seconds}초 안에 {count}회 이상 시 타임아웃",
            ephemeral=True
        )

    @app_commands.command(name="도배방지끄기", description="도배 방지를 끕니다.")
    async def disable_spam_protect(self, interaction: discord.Interaction):
        if interaction.guild_id in spam_settings:
            spam_settings[interaction.guild_id]["enabled"] = False
            await interaction.response.send_message("❌ 도배방지 기능이 꺼졌습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ 도배방지 기능이 설정되어 있지 않습니다.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        guild_id = message.guild.id
        settings = spam_settings.get(guild_id)
        
        if not settings or not settings.get("enabled"):
            return
        
        if message.channel.id != settings["channel_id"]:
            return

        now = datetime.datetime.utcnow()
        user_deque = user_messages[guild_id][message.author.id]
        user_deque.append(now)

        while user_deque and (now - user_deque[0]).total_seconds() > settings["seconds"]:
            user_deque.popleft()

        if len(user_deque) >= settings["count"]:
            try:
                timeout_until = discord.utils.utcnow() + datetime.timedelta(seconds=60)
                await message.author.timeout(timeout_until, reason="도배 감지")
                
                embed = discord.Embed(
                    title="🚫 도배 감지",
                    description=f"{message.author.mention}님이 도배로 인해 1분 타임아웃 되었습니다.",
                    color=discord.Color.red()
                )
                embed.add_field(name="설정", value=f"{settings['seconds']}초 안에 {settings['count']}회 이상")
                embed.set_footer(text="봇이 자동으로 처리했습니다.")
                await message.channel.send(embed=embed)

            except Exception as e:
                print(f"타임아웃 실패: {e}")

            user_messages[guild_id][message.author.id].clear()

async def setup(bot):
    await bot.add_cog(SpamPrevention(bot))

@bot.event
async def on_ready():
    print(f"✅ 봇 준비 완료: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash commands synced: {len(synced)}개")
    except Exception as e:
        print(f"⚠️ Slash command sync 실패: {e}")

async def main():
    await setup(bot)
    await bot.start(TOKEN)

import asyncio
asyncio.run(main())
