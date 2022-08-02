from discord import Intents, utils, Permissions
from logging import debug, info, warning, error
from re import search
from datetime import datetime, timedelta
from asyncio import proactor_events, sleep, wait_for, TimeoutError
from urllib import parse
from discord.ext import commands, tasks
from functools import wraps
from .config import Configuration
from .database import MongoDB
from .reminder import Reminder
from typing import Optional

__all__ = "Bot",


def _sanitize(context: commands.Context) -> bool:
    """
    Meant to clean input to prevent injection of malicious code. Only covers the most common scenarios
    :param context: A context passed from a command event via discord.py
    :return: True if context.message.content is clean.
    :exception: AttemptedInjectionException
    :exception: UnsupportedCharactersException
    """
    content = context.message.content
    if search('[F,f]unction\\(\\)', content):
        raise AttemptedInjectionException
    if search('[$;]|\\(\\)', content):
        raise UnsupportedCharactersException
    return True


# The following classes MUST be a child of commands.CommandError so they are handled by on_command_error
class AttemptedInjectionException(commands.CommandError):
    def __init__(self):
        super().__init__()


class UnsupportedCharactersException(commands.CommandError):
    def __init__(self):
        super().__init__()


class InternalBufferNotReady(commands.CommandError):
    def __init__(self):
        super().__init__()


class InvalidArguments(commands.CommandError):
    def __init__(self):
        super().__init__()

class DatabaseCommunicationError(commands.CommandError):
    def __init__(self):
        super().__init__()


class Bot:
    def __init__(self, configuration: Configuration, database_connection: MongoDB,
                 intents: Intents):
        self.configuration = configuration
        self.database_connection = database_connection
        self.buffer = RemindersBuffer(database_connection=database_connection)

        assert "DISCORD" in self.configuration
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
            # Exceptions must be children of commands.CommandError to be handled here.
            debug(f"classes.bot.py: on_command_error called for {type(exception)}")
            exception_type = type(exception)
            responses = {
                commands.errors.NotOwner: "You're not the boss of me!",
                commands.errors.MissingRequiredArgument: "You're missing something. Try typing $help.",
                commands.errors.CommandInvokeError: "Something went wrong. Sorry.",
                AttemptedInjectionException: "You stop that. You know what you did.",
                UnsupportedCharactersException: "Sorry, I can't support $, () or ;. Try again without those.",
                InvalidArguments: "Sorry, you gave me something I couldn't understand. Can you try looking at @@help?",
                DatabaseCommunicationError: "Your reminder was not saved. I'll report this to my owner."
            }

            # Add exceptions here to send an alert to the owner. (That could be you!)
            serious_errors = [
                AttemptedInjectionException,
                commands.errors.CommandInvokeError,
                DatabaseCommunicationError
            ]

            if exception_type in serious_errors:
                await alert_owner(context, exception)

            if exception_type in responses:
                warning(f"bot.py: Handled exception: {exception_type}, {context.invoked_with}, "
                        f"by: {context.message.author.id}")
                await context.send(responses[exception_type])
            else:
                error(f"bot.py: Unhandled exception: {exception_type}, {context.invoked_with}, "
                      f"by: {context.message.author.id}")
                raise

        @self.bot.event
        async def on_ready():
            params = {
                "client_id": self.clientID,
                "permissions": Permissions(permissions=3072)  # View messages, channels and send messages
            }
            print(f"Bot started and connected to Discord! Invite link: {utils.oauth_url(**params)}")
            info("Bot.py: Bot successfully connected to Discord.")

            # Tasks must be explicitly started! Failure to add a task's start() here means the task never runs!
            self.refresh_buffer.start()
            self.check_buffer.start()

            self.owner = await self.bot.fetch_user(user_id=self.ownerID)
            await self.owner.send("[In Starcraft SCV voice]: Reporting for duty!")

        async def alert_owner(context: Optional[commands.Context], exception: Exception):
            # Be sure to have the bot in a server you're in and allow messages from server members.
            debug(f"classes.bot.py: alert_owner triggered for {type(exception)}")
            if context:
                content = context.message.content
            else:
                content = "An internal task, loop or event"
            await self.owner.send(f"Hi, I ran into an issue. Encountered {type(exception)} during\n"
                                  f"{content}\non {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
                                  f"Please investigate.")

    def _commands(self):
        @self.bot.command(name="stop", hidden=True)
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
            info(f"classes.bot.py: remind called with {context.message.content}: {amount} {units} {args}")
            if type(amount) is not int:
                try:
                    amount = int(amount)
                except ValueError:
                    debug("classes.bot.py: remind rejected the amount parameter. It was not an int")
                    raise InvalidArguments

            if type(units) is not str:
                try:
                    units = str(units)
                except ValueError:
                    debug("classes.bot.py: remind rejected the units parameter. It was not a str")
                    raise InvalidArguments

            if type(args) is tuple:
                args = "{}".format(" ").join(args)

            if not 0 < amount < 1000000:
                debug("classes.bot.py: remind rejected the amount parameter. It was too high or too low")
                await context.send(f"You can't specify more than 999,999 {units}.")
                return

            if units in ('year', 'years', 'month', 'months', 'day', 'days', 'hour', 'hours', 'minute', 'minutes'):
                if units[len(units) - 1] != 's':
                    units += 's'
            else:
                debug("classes.bot.py: remind rejected the units parameter. It was not an expected value.")
                await context.send(f"{units} needs to be year(s), month(s), day(s), hour(s) or minute(s).")
                return

            if context and amount and units and args:
                reminder_time = datetime.utcnow() + timedelta(**{units: amount})
                reminder = Reminder(time=reminder_time, message=args,
                                    recipient=context.message.author.id)
                await reminder.write(database_connection=self.database_connection)

                if reminder:
                    self.buffer.append(reminder)
                    info("classes.bot.py: remind accepted and committed a new reminder to the DB")
                    response = f"Successfully created a reminder! I'll DM you in {reminder.time_remaining()}!"
                else:
                    error("classes.bot.py: remind accepted but was unable to commit a new reminder to the DB")
                    raise DatabaseCommunicationError
            else:
                warning("classes.bot.py: remind rejected the reminder for an unhandled reason.")
                response = "I didn't fully understand that, check @@help remind"

            await context.send(response)

        @self.bot.command(name="list", aliases=("get", "find"), help="List your upcoming reminders.")
        async def _list(context):
            info(f"classes.bot.py: list called with {context.message.content}")
            query = {
                "recipient": context.message.author.id,
                "completed": False
            }
            reminders_raw = await self.database_connection.find_many(database="CinnamonSwirl", collection="Reminders",
                                                                     query=query, length=5, sort_by="time",
                                                                     sort_direction=1)

            if reminders_raw:
                reminders = []
                for item in reminders_raw:
                    reminders.append(Reminder(time=item['time'], message=item['message'],
                                              recipient=item['recipient']))

                response = "These are your 5 next upcoming reminders:\n"
                for iteration, reminder in enumerate(reminders):
                    response += f"{iteration + 1}. In {reminder.time_remaining()}:" \
                                f"\n    `{reminder.message}`\n"
            else:
                response = "You either don't have any upcoming reminders or I failed to find them."

            await context.send(response)

    @tasks.loop(minutes=5)
    async def refresh_buffer(self) -> None:
        """
        Every 5 minutes we will ask the database for a fresh set of reminders that are coming soon.
        :return: None
        """
        debug("classes.bot.py: Refreshing internal buffer for reminders.")
        try:
            await wait_for(self.buffer.refresh(), timeout=90.0)
        except TimeoutError:
            error("classes.bot.py: Buffer refresh timed out.")
            await self._events().alert_owner(exception=InternalBufferNotReady)
        return

    @tasks.loop(minutes=1)
    async def check_buffer(self) -> None:
        """
        Every minute we will inspect our internal list of reminders for ones happening this minute.
        :return: None
        """
        debug("classes.bot.py: Checking internal buffer for reminders to send")
        if not self.buffer:
            debug("classes.bot.py: Buffer is empty. Skipping.")
            return
        try:
            await self.send_reminders()
        except TimeoutError:
            error("classes.bot.py: Waiting for the buffer to be ready for send_reminders timed out.")
            await self._events().alert_owner(exception=InternalBufferNotReady)

    async def send_reminders(self) -> None:
        """
        Look at our internal list of reminders and send them to their recipients if they are due this minute.
        Mark them as completed and remove them from the list once sent.
        :return: None
        """
        debug("classes.bot.py: Preparing to send reminders")
        one_minute_from_now = datetime.utcnow() + timedelta(seconds=60)

        def filter_reminders(x: Reminder):
            if x.time < one_minute_from_now and not x.completed:
                return True
            return False

        if not self.buffer.ready:
            await wait_for(self.buffer.wait(5), timeout=45.0)

        self.buffer.ready = False
        upcoming_reminders = filter(filter_reminders, self.buffer)
        for reminder in upcoming_reminders:
            recipient = await self.bot.fetch_user(user_id=reminder.recipient)
            await recipient.send(f"Reminder: {reminder.message}")
            self.buffer.remove(reminder)
            await reminder.complete(database_connection=self.database_connection)
        self.buffer.ready = True
        return

    def run(self):
        # The actual "start the bot" function.
        self.bot.run(self.token)


class RemindersBuffer(list):
    def __init__(self, database_connection: MongoDB):
        super().__init__()
        self.database_connection = database_connection
        self.ready = True

    async def refresh(self) -> None:
        debug("classes.bot.py: Refreshing internal buffer...")

        if not self.ready:
            debug("classes.bot.py: Internal buffer was not ready when asked to be refreshed, waiting...")
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
            debug(item)
            reminder = Reminder(time=item['time'], message=item['message'],
                                recipient=item['recipient'], _id=item['_id'])
            self.append(reminder)
        self.ready = True

    async def wait(self, interval):
        while not self.ready:
            await sleep(interval)
