import discord
from discord.ext import commands
from discord import app_commands
import datetime
from collections import defaultdict, deque
import os
import asyncio

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
    @app_commands.describe(
        channel="도배 로그를 보낼 채널",
        seconds="N초 안에",
        count="N회 이상",
        timeout="타임아웃 시간 (초)"
    )
    async def spam_protect(self, interaction: discord.Interaction, channel: discord.TextChannel, seconds: int, count: int, timeout: int):
        spam_settings[interaction.guild_id] = {
            "log_channel_id": channel.id,
            "seconds": seconds,
            "count": count,
            "timeout": timeout,
            "enabled": True
        }
        await interaction.response.send_message(
            f"✅ 도배방지 설정 완료: 모든 채널 감지\n"
            f"📩 로그: {channel.mention}\n"
            f"⏱️ {seconds}초 안에 {count}회 이상 → {timeout}초 타임아웃",
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

        now = datetime.datetime.utcnow()
        user_deque = user_messages[guild_id][message.author.id]
        user_deque.append(now)

        # 설정한 seconds 시간보다 오래된 기록은 삭제
        while user_deque and (now - user_deque[0]).total_seconds() > settings["seconds"]:
            user_deque.popleft()

        if len(user_deque) >= settings["count"]:
            try:
                timeout_seconds = settings["timeout"]
                timeout_until = discord.utils.utcnow() + datetime.timedelta(seconds=timeout_seconds)
                await message.author.timeout(timeout_until, reason="도배 감지")

                # 도배 메시지 삭제 (최근 100개 메시지 중 설정 시간 내 해당 사용자 메시지 삭제)
                def check(m):
                    return (
                        m.author == message.author and 
                        (now - m.created_at).total_seconds() <= settings["seconds"]
                    )
                deleted = await message.channel.purge(limit=100, check=check)

                log_channel = message.guild.get_channel(settings["log_channel_id"])
                if log_channel:
                    embed = discord.Embed(
                        title="🚫 도배 감지",
                        description=f"{message.author.mention}님이 도배로 인해 {timeout_seconds}초 타임아웃 되었습니다.",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="설정", value=f"{settings['seconds']}초 안에 {settings['count']}회 이상")
                    embed.add_field(name="발생 채널", value=message.channel.mention)
                    embed.add_field(name="삭제된 메시지 수", value=str(len(deleted)))
                    embed.set_footer(text="봇이 자동으로 처리했습니다.")
                    await log_channel.send(embed=embed)

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


asyncio.run(main())


