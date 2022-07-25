import discord
import logging
import pymongo.errors
import re
from datetime import datetime, timedelta
from asyncio import proactor_events
from urllib import parse
from discord.ext import commands
from functools import wraps
from .config import Configuration
from .database import MongoDB
from .reminder import Reminder

__all__ = "Bot",


def _sanitize(context: discord.ext.commands.Context) -> bool:
    content = context.message.content
    if re.search('[F,f]unction\\(\\)', content):
        raise AttemptedInjectionException
    if re.search('[$;]|\\(\\)', content):
        raise UnsupportedCharactersException
    return True


class AttemptedInjectionException(discord.ext.commands.CommandError):
    def __init__(self):
        super().__init__()


class UnsupportedCharactersException(discord.ext.commands.CommandError):
    def __init__(self):
        super().__init__()


class Bot:
    def __init__(self, configuration: Configuration, database_connection: MongoDB,
                 intents: discord.Intents):
        self.configuration = configuration
        self.database_connection = database_connection

        assert "DISCORD" in self.configuration.configuration
        for key in ("clientID", "token", "ownerID"):
            assert key in self.configuration["DISCORD"]

        self.clientID = parse.quote_plus(self.configuration["DISCORD"]["clientID"])
        self.token = parse.quote_plus(self.configuration["DISCORD"]["token"])
        self.ownerID = int(parse.quote_plus(self.configuration["DISCORD"]["ownerID"]))
        self.owner = None

        self.bot = commands.Bot(command_prefix="@@", intents=intents, owner_id=self.ownerID)

        self._events()
        self._commands()

        """
        # What is this? On Bot._commands.stop, discord.py stops the running loop in asyncio cleanly, but
        # asyncio does not close everything up after that cleanly. A dangling 'RuntimeError' would be raised
        # even though asyncio itself ignored it. This was the only way I found to suppress the output for a
        # harmless and meaningless exception. Even discord.py contributors recognize it, though their proposed fix
        # failed to solve it for me.
        # Source: https://pythonalgos.com/runtimeerror-event-loop-is-closed-asyncio-fix/
        # Discord.py issue: https://github.com/Rapptz/discord.py/issues/5209
        """
        # noinspection PyProtectedMember
        proactor_events._ProactorBasePipeTransport.__del__ = \
            self._silence_event_loop_closed(proactor_events._ProactorBasePipeTransport.__del__)

    @staticmethod
    def _silence_event_loop_closed(func):
        """
        # What is this? On bot._commands.stop, discord.py stops the running loop in asyncio cleanly, but
        # asyncio does not close everything up after that cleanly. A dangling 'RuntimeError' would be raised
        # even though asyncio itself ignored it. This was the only way I found to suppress the output for a
        # harmless and meaningless exception. Even discord.py contributors recognize it, though their proposed fix
        # failed to solve it for me.
        # Source: https://pythonalgos.com/runtimeerror-event-loop-is-closed-asyncio-fix/
        # Discord.py issue: https://github.com/Rapptz/discord.py/issues/5209
        """
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except RuntimeError as e:
                if str(e) != 'Event loop is closed':
                    raise

        return wrapper

    def _events(self):
        @self.bot.event
        async def on_command_error(context, exception):
            exception_type = type(exception)
            responses = {
                discord.ext.commands.errors.NotOwner: "You're not the boss of me!",
                discord.ext.commands.errors.MissingRequiredArgument: "You're missing something. Try typing $help.",
                discord.ext.commands.errors.CommandInvokeError: "Something went wrong. Sorry.",
                pymongo.errors.WriteError: "There was a problem writing that to my internal database.",
                AttemptedInjectionException: "You stop that. You know what you did.",
                UnsupportedCharactersException: "Sorry, I can't support $, () or ;. Try again without those."
            }

            serious_errors = [
                pymongo.errors.WriteError,
                AttemptedInjectionException
            ]

            if exception_type in serious_errors:
                await alert_owner(context, exception)

            if exception_type in responses:
                logging.warning(f"bot.py: Handled exception: {exception_type}, {context.invoked_with}, "
                                f"by: {context.message.author.id}")
                await context.send(responses[exception_type])
            else:
                logging.error(f"bot.py: Unhandled exception: {exception_type}, {context.invoked_with}, "
                              f"by: {context.message.author.id}")
                raise

        @self.bot.event
        async def on_ready():
            params = {
                "client_id": self.clientID,
                "permissions": discord.Permissions(permissions=3072)  # View messages, channels and send messages
            }
            print(f"Bot started and connected to Discord! Invite link: {discord.utils.oauth_url(**params)}")
            logging.info("Bot.py: Bot successfully connected to Discord.")

            self.owner = await self.bot.fetch_user(user_id=self.ownerID)
            await self.owner.send("[In Starcraft SCV voice]: Reporting for duty!")

        async def alert_owner(context, exception: Exception):
            await self.owner.send(f"Hi, I ran into an issue. Encountered {type(exception)} during\n"
                                  f"{context.message.content}\non {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
                                  f"Please investigate.")

    def _commands(self):
        @self.bot.command(name="stop")
        @commands.is_owner()
        async def stop(context):
            await context.send("Signing off, bye bye!")
            await self.bot.close()  # NOTE: This would normally raise RuntimeError. See Bot._silence_event_loop_closed

        @commands.check(_sanitize)
        @self.bot.command(name="remind", aliases=("remindme", "reminder"),
                          brief="Will DM you a message you give it at the time you set",
                          usage="remind (whole number) (years/months/days/hours/minutes) (message)"
                                "\nExample: $remindme 1 day Do Project")
        async def remind(context, amount, units, *args):
            # FIXME: All of the custom errors from pymongo or internally raise as CommandInvokeError, which is nasty.
            if type(amount) is not int:
                try:
                    amount = int(amount)
                except ValueError:
                    raise discord.ext.commands.errors.CommandInvokeError

            if type(units) is not str:
                try:
                    units = str(units)
                except ValueError:
                    raise discord.ext.commands.errors.CommandInvokeError

            if type(args) is tuple:
                args = "{}".format(" ").join(args)

            if 0 < amount < 1000000:
                pass  # OK
            else:
                await context.send(f"You can't specify more than 999,999 {units}.")
                return

            if units in ('year', 'years', 'month', 'months', 'day', 'days', 'hour', 'hours', 'minute', 'minutes'):
                if units[len(units) - 1] != 's':
                    units += 's'
            else:
                await context.send(f"{units} needs to be year(s), month(s), day(s), hour(s) or minute(s).")
                return

            if context and amount and units and args:
                timedelta_keyword = {units: amount}
                reminder_time = datetime.now() + timedelta(**timedelta_keyword)
                reminder = Reminder(time=reminder_time, message=args, recipient=context.message.author.id)
                reminder_id = await reminder.write(database_connection=self.database_connection)

                if reminder_id:
                    reminder_time_friendly = reminder_time.strftime('%d %b %Y, %H:%M')
                    response = f"Successfully created a reminder on {reminder_time_friendly}! I'll DM you then!"
                else:
                    response = f"Your reminder was not saved. I'll report this to my owner."
            else:
                response = "I didn't fully understand that, check $help remind"

            await context.send(response)

    def run(self):
        self.bot.run(self.token)
