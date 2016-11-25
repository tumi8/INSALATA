import logging
import logging.handlers
import os

LOG_PATH = "/var/log/insalata"

def createLogger(name, logFile, level, maxBytes, backup):
    """
    Get RotatingFile-Logger with the correct output format configured.
    Standard log-path is /var/log/insalata.

    :param name: Name the logger shall have.
    :type name: str

    :param logFile: Name of the log file the logger should use
    :type logFile: str

    :param maxBytes: Maximum size of the logfile before logger starts rotating
    :type maxBytes: int

    :param backup: Number of files to hold as log backup
    :type backup: int

    :returns: Configured logger object
    :rtype: :class:'logging.Logger'
    """
    if not os.path.exists(LOG_PATH):
        os.makedirs(LOG_PATH, 0o755)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.handlers.RotatingFileHandler("{0}/{1}".format(LOG_PATH, logFile), maxBytes=maxBytes, backupCount=backup)
    formatter = logging.Formatter('%(asctime)s - Module:%(module)s::%(lineno)d - %(levelname)s: %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger


def getLogLevel(level):
    """
    Return the python internal value for a loglevel given as character string.

    :param level: Log-level to use
    :type level: str

    :returns: Log level int representation used by :seealso:'logging' module
    :rtype: int
    """
    return {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
        }.get(level, None)
