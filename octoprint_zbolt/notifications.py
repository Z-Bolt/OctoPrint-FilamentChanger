class Notifications:
    def __init__(self):
        self._message = "Hello"

    def display(self, message):
        self._message = message

    def get_message_to_display(self):
        m = self._message
        self._message = None
        return m
        


