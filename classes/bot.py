import discord
import logging
from classes import Configuration, MongoDB

__all__ = "Bot",


class Bot:
    def __init__(self, configuration: Configuration, database_connection: MongoDB,
                 intents: discord.Intents):
        self.configuration = configuration
        self.database_connection = database_connection
        self.client = discord.Client(intents=intents)

        assert "DISCORD" in self.configuration.configuration
        assert "clientID", "token" in self.configuration["DISCORD"]

        @self.client.event
        async def on_ready():
            params = {
                "client_id": self.configuration["DISCORD"]["clientID"],
                "permissions": discord.Permissions(permissions=3072)  # View messages, channels and send messages
            }
            print(f"Bot started and connected to Discord! Invite link: {discord.utils.oauth_url(**params)}")
            logging.info("Bot.py: Bot successfully connected to Discord.")

    def run(self):
        self.client.run(self.configuration["DISCORD"]["token"])
