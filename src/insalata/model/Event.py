class Event:
    """
    Implement Events in Python.

    Class allows to add a handler to the event.
    If the event is triggered, all handlers will be informed.
    """
    def __init__(self):
        self.handlers = set()

    def add(self, fun):
        """
        Add a handler to this event.

        :param fun: Function that should be called, if the event is triggered
        :type fun: function reference
        """
        self.handlers.add(fun)

    def remove(self, fun):
        """
        Remove a function from this event.

        :param fun: Function to remove
        :type fun: function reference
        """
        if fun in self.handlers:
            self.handlers.remove(fun)

    def trigger(self, sender, args):
        """
        Trigger the event and inform all handlers.

        :param sender: The trigger of the event
        :type sender: object reference

        :param args: Arguements of the triggered event
        :type args: dict
        """
        for handler in self.handlers:
            handler(sender, args)