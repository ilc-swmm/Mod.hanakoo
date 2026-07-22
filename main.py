import discord
from discord.ext import commands
import json
import logging
import os
import asyncio
from database import Database
from utils.logging import setup_logging

class ModerationBot(commands.Bot):
    def __init__(self):
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=self.config['prefix'],
            intents=intents,
            help_command=None
        )
        
        self.db = Database()
        self.logger = setup_logging()
        
    async def setup_hook(self):
        await self.db.initialize()
        await self.load_extension('cogs.moderation_cog')
        await self.load_extension('cogs.automod_cog')
        await self.load_extension('cogs.admin_cog')
        
    async def on_ready(self):
        self.logger.info(f'{self.user} has connected to Discord!')
        self.logger.info(f'Bot is ready and serving {len(self.guilds)} guilds')
        
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} servers | {self.config['prefix']}help"
        )
        await self.change_presence(activity=activity)
        
    async def on_guild_join(self, guild):
        self.logger.info(f'Joined new guild: {guild.name} (ID: {guild.id})')
        await self.db.add_guild(guild.id)
        
        embed = discord.Embed(
            title="Thanks for adding me!",
            description=f"Use `{self.config['prefix']}help` to get started with moderation commands.",
            color=0x00ff00
        )
        embed.add_field(
            name="Getting Started",
            value=f"• Set up auto-mod: `{self.config['prefix']}automod setup`\n"
                  f"• Configure settings: `{self.config['prefix']}config`\n"
                  f"• View all commands: `{self.config['prefix']}help`",
            inline=False
        )
        
        if guild.system_channel and isinstance(guild.system_channel, discord.TextChannel):
            try:
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                pass
                
    async def on_member_join(self, member):
        guild_config = await self.db.get_guild_config(member.guild.id)
        if guild_config and guild_config.get('welcome_enabled', False):
            welcome_channel_id = guild_config.get('welcome_channel')
            if welcome_channel_id:
                channel = self.get_channel(welcome_channel_id)
                if channel:
                    welcome_message = guild_config.get('welcome_message', 
                        f'Welcome to {member.guild.name}, {member.mention}!')
                    
                    embed = discord.Embed(
                        title="Welcome!",
                        description=welcome_message,
                        color=0x00ff00,
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text=f"Member #{len(member.guild.members)}")
                    
                    try:
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        pass
                        
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
            
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description=f"You don't have the required permissions: {', '.join(error.missing_permissions)}",
                color=0xff0000
            )
            await ctx.send(embed=embed, delete_after=10)
            return
            
        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="❌ Bot Missing Permissions",
                description=f"I don't have the required permissions: {', '.join(error.missing_permissions)}",
                color=0xff0000
            )
            await ctx.send(embed=embed, delete_after=10)
            return
            
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Command on Cooldown",
                description=f"Try again in {error.retry_after:.2f} seconds",
                color=0xff9900
            )
            await ctx.send(embed=embed, delete_after=10)
            return
            
        self.logger.error(f'Unhandled error in command {ctx.command}: {error}')
        
        embed = discord.Embed(
            title="❌ An Error Occurred",
            description="An unexpected error occurred while processing your command.",
            color=0xff0000
        )
        await ctx.send(embed=embed, delete_after=10)

async def main():
    bot = ModerationBot()
    
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN environment variable not set")
        return
        
    try:
        await bot.start(token)
    except discord.LoginFailure:
        print("Error: Invalid Discord token")
    except Exception as e:
        print(f"Error starting bot: {e}")
    finally:
        await bot.db.close()

if __name__ == "__main__":
    asyncio.run(main())
