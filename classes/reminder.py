from pymongo.errors import WriteError
from classes import MongoDB
from datetime import datetime
from bson import objectid
from typing import Optional

__all__ = "Reminder",


class Reminder:
    def __init__(self, time: datetime, message: str, recipient: int, _id: Optional[objectid.ObjectId] = None):
        self._id = _id
        self.time = time
        self.message = message
        self.recipient = recipient
        self.completed = False

    def __bool__(self) -> bool:
        return bool(self._id)

    async def write(self, database_connection: MongoDB) -> objectid.ObjectId:
        query = {
            "time": self.time,
            "message": self.message,
            "recipient": self.recipient,
            "completed": False
        }
        result = await database_connection.insert_one(database="CinnamonSwirl", collection="Reminders", query=query)
        if result is not None:
            self._id = result
            return self._id
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
        if len(response) < 1:
            response = "less than a minute"
        return response

    async def complete(self, database_connection: MongoDB) -> None:
        self.completed = True
        criteria = {
            '_id': self._id
        }
        update = {
            '$set': {'completed': True}
        }
        await database_connection.update_one(database="CinnamonSwirl", collection="Reminders",
                                             criteria=criteria, update=update)

