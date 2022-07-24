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
