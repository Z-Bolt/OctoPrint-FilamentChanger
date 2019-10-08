class NotificationsStorage:
    def __init__(self):
        self._message = "Wake up, Neo...\nThe Matrix has you...\nFollow the white rabbit.\n\n\nKnock, Knock, Neo."

    def display(self, message):
        self._message = message

    def get_message_to_display(self):
        m = self._message
        self._message = None
        return m
        

Notifications = NotificationsStorage()

