#!/usr/bin/python3

import sys, os
from xmlrpc.client import ServerProxy
from inspect import getdoc

SHELL_STATUS_RUN = 1
SHELL_STATUS_STOP = 0


def shell_loop():
    status = SHELL_STATUS_RUN

    while status == SHELL_STATUS_RUN:
        # Display a command prompt
        sys.stdout.write('-> ')
        sys.stdout.flush()

        processCommand(sys.stdin.readline())

def processCommand(cmd):

    # Read command input
    cmd = cmd.rstrip('\n').split()
    #strip quotes of every parameter if there are any
    cmd = [cmd[0]] + [x.lstrip('"').rstrip('"').lstrip("'").rstrip("'") for x in cmd[1:]]

    if cmd[0] == "exit" or cmd[0] == "quit":
        dispose()
    elif cmd[0] == "help" and len(cmd) > 1:
        showCommand(cmd[1])
    elif cmd[0] == "help":
        showCommands()
    elif cmd[0] == "uploadConfiguration" and len(cmd) == 3:
        uploadConfiguration(cmd[1], cmd[2]) #special because client side code is needed
    else:   #all other 'non-special' commands
        if cmd[0] in commands:
            command = commands[cmd[0]]
            paramCount = len(cmd[1:])
            if (paramCount >= command[0]) and (paramCount <= command[1]):
                if len(cmd[1:]) > 0:
                    cmdString = "server.{0}({1})".format(cmd[0], ','.join(['"' + str(x) + '"' for x in cmd[1:]]))
                else:
                    cmdString = "server.{0}()".format(cmd[0])
                res = eval(cmdString)
                print(res)
            else:
                print("Unsupported number of paramters for command {0}. Allowed are {1} to {2}".format(cmd[0], *command)) 
        else:
            print("Unsupported command {0} ".format(cmd[0]))

def dispose():
    print("Bye")
    sys.exit(0)

def showCommands():
    for k in commands.keys():
        print("Command {0} with {1} to {2} parameter(s)".format(k, commands[k][0], commands[k][1]))

def showCommand(c):
    if c in commands:
        print("Command {0}:\n-------------------------------------------------------------------------------\n{1}\n-------------------------------------------------------------------------------".format(c, commands[c][2]))
    else:
        print("Unknown command {0}".format(c)) 

def uploadConfiguration(environmentName, filePath):
    """
    Upload a new configuration file 

    :param environmentName: Name of the environment the XML will be part of
    :type environmentName: str

    :param filePath: Path to the file locally.
    :type filePath: str
    """

    fileName = os.path.basename(filePath)
    with open (filePath, "r") as f:
        data = f.read()

    print(server.uploadConfiguration(environmentName, fileName, data))

if len(sys.argv) < 3:
    print("Usage: client [ADDRESS] [PORT]")
else:
    #login
    serverAddress = str(sys.argv[1])
    serverPort = str(sys.argv[2])
    uri = "http://" + serverAddress + ":" + serverPort

    server = ServerProxy(uri)

    if server:
        print("Connected to " + uri)
        print("Write commands with: command [PARAM1] [PARAM2] ...")
        print("Use 'help' for list of all commands available and \n'help COMMAND' for a description of a command")

        #get a list of all commands
        commands = server.getCommands()

        #add an additional custom command (just for help/doc)
        commands["uploadConfiguration"] = (2, 2, getdoc(uploadConfiguration))

        #start the shell
        shell_loop()
