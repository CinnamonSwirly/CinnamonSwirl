import asyncio

import discord
import logging
import pymongo.errors
import re
from datetime import datetime, timedelta
from asyncio import proactor_events, sleep, wait_for
from urllib import parse
from discord.ext import commands, tasks
from functools import wraps
from .config import Configuration
from .database import MongoDB
from .reminder import Reminder
from typing import Optional

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


class InternalBufferNotReady(discord.ext.commands.CommandError):
    def __init__(self):
        super().__init__()


class Bot:
    def __init__(self, configuration: Configuration, database_connection: MongoDB,
                 intents: discord.Intents):
        self.configuration = configuration
        self.database_connection = database_connection
        self.buffer = RemindersBuffer(database_connection=database_connection)

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
            logging.debug(f"classes.bot.py: on_command_error called for {type(exception)}")
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

            self.refresh_buffer.start()
            self.check_buffer.start()

            self.owner = await self.bot.fetch_user(user_id=self.ownerID)
            await self.owner.send("[In Starcraft SCV voice]: Reporting for duty!")

        async def alert_owner(context: Optional[discord.ext.commands.Context], exception: Exception):
            logging.debug(f"classes.bot.py: alert_owner triggered for {type(exception)}")
            if context:
                content = context.message.content
            else:
                content = "An internal task, loop or event"
            await self.owner.send(f"Hi, I ran into an issue. Encountered {type(exception)} during\n"
                                  f"{content}\non {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
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
        async def _remind(context, amount, units, *args):
            logging.info(f"classes.bot.py: remind called with {context.message.content}: {amount} {units} {args}")
            if type(amount) is not int:
                try:
                    amount = int(amount)
                except ValueError:
                    logging.debug("classes.bot.py: remind rejected the amount parameter. It was not an int")
                    raise discord.ext.commands.errors.CommandInvokeError

            if type(units) is not str:
                try:
                    units = str(units)
                except ValueError:
                    logging.debug("classes.bot.py: remind rejected the units parameter. It was not a str")
                    raise discord.ext.commands.errors.CommandInvokeError

            if type(args) is tuple:
                args = "{}".format(" ").join(args)

            if 0 < amount < 1000000:
                pass  # OK
            else:
                logging.debug("classes.bot.py: remind rejected the amount parameter. It was too high or too low")
                await context.send(f"You can't specify more than 999,999 {units}.")
                return

            if units in ('year', 'years', 'month', 'months', 'day', 'days', 'hour', 'hours', 'minute', 'minutes'):
                if units[len(units) - 1] != 's':
                    units += 's'
            else:
                logging.debug("classes.bot.py: remind rejected the units parameter. It was not an expected value.")
                await context.send(f"{units} needs to be year(s), month(s), day(s), hour(s) or minute(s).")
                return

            if context and amount and units and args:
                timedelta_keyword = {units: amount}
                reminder_time = datetime.utcnow() + timedelta(**timedelta_keyword)
                reminder = Reminder(time=reminder_time, message=args,
                                    recipient=context.message.author.id)
                reminder_id = await reminder.write(database_connection=self.database_connection)

                if reminder_id:
                    self.buffer.append(reminder)
                    logging.info("classes.bot.py: remind accepted and committed a new reminder to the DB")
                    reminder_time_friendly = reminder_time.strftime('%d %b %Y, %H:%M')
                    response = f"Successfully created a reminder on {reminder_time_friendly}! I'll DM you then!"
                else:
                    logging.error("classes.bot.py: remind accepted but was unable to commit a new reminder to the DB")
                    response = f"Your reminder was not saved. I'll report this to my owner."
            else:
                logging.warning("classes.bot.py: remind rejected the reminder for an unhandled reason.")
                response = "I didn't fully understand that, check $help remind"

            await context.send(response)

        @self.bot.command(name="list", aliases=("get", "find"), help="List your upcoming reminders.")
        async def _list(context):
            logging.info(f"classes.bot.py: list called with {context.message.content}")
            author = context.message.author
            query = {
                "recipient": author.id,
                "completed": False
            }
            reminders_raw = await self.database_connection.find_many(database="CinnamonSwirl", collection="Reminders",
                                                                     query=query, length=5, sort_by="time",
                                                                     sort_direction=pymongo.ASCENDING)

            if reminders_raw:
                reminders = []
                for item in reminders_raw:
                    reminders.append(Reminder(time=item['time'], message=item['message'],
                                              recipient=item['recipient']))

                response = "These are your 5 next upcoming reminders:\n"
                counter = 0
                for reminder in reminders:
                    counter += 1
                    response += f"{counter}. In {reminder.time_remaining()}:" \
                                f"\n    `{reminder.message}`\n"
                response += ""
            else:
                response = "You either don't have any upcoming reminders or I failed to find them."

            await context.send(response)

    @tasks.loop(minutes=5)
    async def refresh_buffer(self) -> None:
        logging.debug("classes.bot.py: Refreshing internal buffer for reminders.")
        try:
            await wait_for(self.buffer.refresh(), timeout=90.0)
        except asyncio.TimeoutError:
            logging.error("classes.bot.py: Buffer refresh timed out.")
            await self._events().alert_owner(exception=InternalBufferNotReady)
        return

    @tasks.loop(minutes=1)
    async def check_buffer(self) -> None:
        logging.debug("classes.bot.py: Checking internal buffer for reminders to send")
        if not self.buffer:
            logging.debug("classes.bot.py: Buffer is empty. Skipping.")
            return
        try:
            await self.send_reminders()
        except asyncio.TimeoutError:
            logging.error("classes.bot.py: Waiting for the buffer to be ready for send_reminders timed out.")
            await self._events().alert_owner(exception=InternalBufferNotReady)

    async def send_reminders(self) -> None:
        logging.debug("classes.bot.py: Preparing to send reminders")
        if not self.buffer.ready:
            await wait_for(self.buffer.wait(5), timeout=45.0)

        self.buffer.ready = False
        one_minute_from_now = datetime.utcnow() + timedelta(seconds=60)
        upcoming_reminders = filter(lambda a: a.time < one_minute_from_now, self.buffer)
        for reminder in upcoming_reminders:
            if not reminder.completed:
                recipient = await self.bot.fetch_user(user_id=reminder.recipient)
                await recipient.send(f"Reminder: {reminder.message}")
                self.buffer.remove(reminder)
                await reminder.complete(database_connection=self.database_connection)
        self.buffer.ready = True
        return

    def run(self):
        self.bot.run(self.token)


class RemindersBuffer(list):
    def __init__(self, database_connection: MongoDB):
        super().__init__()
        self.database_connection = database_connection
        self.ready = True

    async def refresh(self) -> None:
        logging.debug("classes.bot.py: Refreshing internal buffer...")

        if not self.ready:
            logging.debug("classes.bot.py: Internal buffer was not ready when asked to be refreshed, waiting...")
            await wait_for(self.wait(5), timeout=60.0)

        self.ready = False

        twenty_minutes_from_now = datetime.utcnow() + timedelta(minutes=20.0)
        query = {
            "time": {"$lt": twenty_minutes_from_now},
            "completed": False
        }

        results = await self.database_connection.find_many(database="CinnamonSwirl", collection="Reminders",
                                                           query=query, length=50, sort_by="time", sort_direction=1)
        self.clear()
        for item in results:
            logging.debug(item)
            reminder = Reminder(time=item['time'], message=item['message'],
                                recipient=item['recipient'], _id=item['_id'])
            self.append(reminder)
        self.ready = True

    async def wait(self, interval):
        while not self.ready:
            await sleep(interval)


