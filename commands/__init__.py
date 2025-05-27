"""
This module initializes the command system for the bot.
It registers commands, subcommands, and repeatable tasks,
and provides utility functions for command handling.
"""

__all__ = ['get', 'all', 'command', 'Command', 'subcommand',
           'repeat', 'bad_cmd', 'bad_subcmd', 'Message', 'mc_command', 'db']

import argparse
import asyncio
import subprocess
from pathlib import Path
from typing import Callable

from discord import Message
from pymongo import MongoClient
from pymongo.database import Database

commands = {}
temp_subcommands = {}
temp_repeatables = {}
valid_choices = ['minecraft', 'music']

ARGS = argparse.ArgumentParser()
ARGS.add_argument('-f', '--features', nargs='+', type=str,
                  default=valid_choices, choices=valid_choices)
features = ARGS.parse_args().features

db = MongoClient().flatearth


class Command:
    """
    Base class for commands in the bot.
    This class provides the structure for commands, including subcommands,
    repeatable tasks, and basic command handling.
    """

    def __init__(self, database: Database) -> None:
        self.db: Database = database
        self.subcommands: dict[str, Callable] = {}
        self.id: str = 'NO ID'
        self.desc: str = 'NO DESCRIPTION'
        self.admin_only: bool = False
        self.user_is_admin: bool = False
        self.sub = 'NO SUB'
        self.repeat_tasks: list[tuple[Callable, float]] = []

    def __str__(self) -> str:
        return f'!{self.id}'

    def log(self, msg: str) -> None:
        """
        Log a message to the console, flushing the output immediately.

        Args:
            msg (str): The message to log.
        """
        print(msg, flush=True)

    async def default(self, message: Message, cmd: list[str]) -> str | None:
        """
        Default method to handle commands.

        This method should be overridden by subclasses to provide specific command functionality.
        The default (error message) method is called when the command
        does not match any registered subcommands.

        Args:
            message (Message): The Discord message that triggered the command.
            cmd (list[str]): The command arguments.
        Returns:
        """

        return bad_subcmd(cmd[0])

    async def call(self, message: Message, cmd: list[str]) -> str | None:
        """
        Call the appropriate method based on the command and subcommand.
        This method checks if the user is an admin and whether the command
        is restricted to admins only. It then calls the appropriate method
        based on the command and subcommand provided.

        Args:
            message (Message): The Discord message that triggered the command.
            cmd (list[str]): The command arguments, where the first element is the command name.

        Returns:
            str | None: The result of the command execution, or an error message.
        """

        self.user_is_admin = bool(
            self.db.admins.find_one({'id': str(message.author.id)}))

        if not self.user_is_admin and self.admin_only:
            return bad_cmd()

        if len(cmd) and cmd[0] in self.subcommands:
            params = {'self': self, 'message': message,
                      'command': cmd[1::]}
            method = self.subcommands[cmd[0]]
            self.sub = cmd[0]
        else:
            params = {'message': message, 'command': cmd}
            method = self.default
            self.sub = 'NO SUB'

        return await method(**params)


def command(
    name: str,
    description: str,
    feature: str | None = None,
    *,
    admin_only: bool = False
) -> Callable:
    """Decorator to register a command with the bot.

    Args:
        name (str): The name of the command.
        description (str): A brief description of the command.
        feature (str | None): The feature this command belongs to, if any.
        admin_only (bool): Whether the command is restricted to admins only.
    Returns:
        Callable: A decorator that wraps the command class.
    """

    if feature and feature not in features:
        def dummy(object: Command) -> None:
            return None
        return dummy

    def wrapper(object: type) -> type:
        global temp_subcommands
        global temp_repeatables

        obj = object(db)
        obj.subcommands = temp_subcommands
        obj.repeat_tasks = temp_repeatables.values()
        obj.id = name
        obj.desc = description
        obj.admin_only = admin_only
        temp_subcommands = {}
        temp_repeatables = {}

        commands[name] = obj
        return object

    return wrapper


def subcommand(func: Callable) -> Callable:
    """
    Decorator to register a function as a subcommand of a command.

    Args:
        func (Callable): The function to register as a subcommand.

    Returns:
        Callable: The original function, now registered as a subcommand.
    """

    temp_subcommands[func.__name__] = func
    return func


def repeat(seconds: float) -> Callable:
    """
    Decorator to register a function as a repeatable task.

    Args:
        seconds (float): The interval in seconds at which the task should repeat.

    Returns:
        Callable: A decorator that wraps the function to make it repeatable.
    """

    def wrapper(func: Callable) -> Callable:
        temp_repeatables[func.__name__] = (func, seconds)
        return func

    return wrapper


def bad_cmd() -> str:
    """
    Generate an error message for an unknown command.

    Returns:
        str: An error message indicating the command is unknown.
    """

    return (
        'ERROR: Unknown command. Type `@mc.skrunky.com`, ' +
        '`!help` or `/help` for a list of commands.'
    )


def bad_subcmd(subcmd: str) -> str:
    """
    Generate an error message for an invalid subcommand.

    Args:
        subcmd (str): The invalid subcommand that was attempted.

    Returns:
        str: An error message indicating the invalid subcommand.
    """

    return f'ERROR: Invalid subcommand "{subcmd}".'


def mc_command(text: str) -> None:
    """
    Send a command to the Minecraft server running in a screen session.

    Args:
        text (str): The command to send to the Minecraft server.
    """

    subprocess.run(
        [
            'screen', '-r', 'flatearth', '-p', '0', '-X', 'stuff',
            text.replace('\\', '\\\\').replace('$', '\\$') + '\\n'
        ],
        check=False
    )


def get(name: str) -> Command | None:
    """
    Retrieve a command by its name.

    Args:
        name (str): The name of the command to retrieve.

    Returns:
        Command | None: The command object if found, otherwise None.
    """
    return commands.get(name)


def all() -> dict[str, Command]:
    """
    Retrieve all registered commands.

    Returns:
        dict[str, Command]: A dictionary of all commands,
            where keys are command names and values are Command objects.
    """
    return commands


# Dynamically import and register all commands in the 'commands' directory.
for i in [
    f.name[:-3]
    for f in Path(__file__).parent.iterdir()
    if f.name != '__init__.py' and not f.is_dir()
]:
    __import__(f'commands.{i}')
