from pymongo.errors import WriteError
from classes import MongoDB
from datetime import datetime

__all__ = "Reminder",


class Reminder:
    def __init__(self, time: datetime, message: str, recipient: int):
        self.id = None
        self.time = time
        self.message = message
        self.recipient = recipient

    def __bool__(self) -> bool:
        return bool(self.id)

    async def write(self, database_connection: MongoDB) -> int:
        query = {
            "time": self.time,
            "message": self.message,
            "recipient": self.recipient
        }
        result = await database_connection.insert_one(database="CinnamonSwirl", collection="Reminders", query=query)
        if result is not None:
            self.id = result
            return self.id
        else:
            raise WriteError

    def time_remaining(self) -> str:
        """
        Will calculate the time remaining between the current UTC time and the Reminder's time property.
        :return: str
        """
        def _check_plural(number: int, word: str) -> str:
            if number > 1:
                return word + "s"
            else:
                return word

        now = datetime.utcnow()
        then = self.time
        difference = then - now
        seconds = difference.total_seconds()
        days = int(seconds // 86400)
        seconds = seconds - (days * 86400)
        hours = int(seconds // 3600)
        seconds = seconds - (hours * 3600)
        minutes = int(seconds // 60)
        result = ([days, "day"], [hours, "hour"], [minutes, "minute"])
        response = ""
        for amount, unit in result:
            if amount:
                response += f"{amount} {_check_plural(amount, unit)}"
                if unit != "minute":
                    response += ", "
        return response

