from threading import Timer as pyTimer
from functools import partial
import datetime

class Timer():
    """
    Own Timer implementation that uses pythons threading.Timer but supports pausing and resuming.
    """
    
    def __init__(self, duration, method, args=[], kwargs={}):
        """
        Initialize the Timer object. 

        :param duration: Time in seconds the timer shall wait before executing the method
        :type duration: int

        :param method: Method to execute if duration is elapsed
        :type method: Function pointer

        :param args: List of arguments for the method
        :type args: list

        :param kwargs: Keyword arguments for the method
        :type kwargs: dict
        """
        self.duration = duration
        self.method = method
        self.args = args
        self.kwargs = kwargs

        self.running = False
        self.startTime = None
        self.pauseTime = None
        self.timer = None
        self.over = False

    def start(self):
        """
        Start the timer.
        """
        self.running = True
        self.startTime = datetime.datetime.now()
        self.pauseTime = None
        if self.duration != -1: #Do nothing if duration is -1
            self.timer = pyTimer(self.duration, partial(self.caller, self.method), self.args, self.kwargs)
            self.timer.setDaemon(True)
            self.timer.start()

    def caller(self, method, *args, **kwargs):
        self.over = True
        method(*args, **kwargs)

    def getOver(self):
        return self.over

    def pause(self):
        """
        Pause the timer.
        """
        if self.running and self.duration != -1 and self.timer:
            self.timer.cancel()
            self.timer = None
            self.pauseTime = datetime.datetime.now()
        self.running = False

    def resume(self):
        """
        Resume the timer.
        Duration is the overall duration minus the time elapsed till pause.
        """
        if not self.pauseTime:
            self.start()
        if not self.running and self.duration != -1:
            self.duration = self.duration - (int((self.pauseTime-self.startTime).total_seconds()))
            self.start()


    def cancel(self):
        """
        Cancel the timer execution.
        """
        if self.duration != -1 and self.timer:
            self.timer.cancel()
        self.running = False