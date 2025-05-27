"""
Alias command for the Flat Earth Minecraft server.
This command allows users to set, remove, and show their aliases,
which are the usernames that players see when they send messages to the server.
"""

from discord import Message

from commands import Command, command, subcommand


@command('alias', (
	'Set the username that players see ' +
	'when you send messages to the Flat Earth.'
), 'minecraft')
class AliasCmd(Command):
    """
    Command to manage user aliases for the Flat Earth Minecraft server.
    This command allows users to set, remove, and show their aliases,
    which are the usernames that players see when they send messages to the server.
    """

    def set_alias(self, user_id: int, alias: str) -> bool:
        """
        Set the alias for a user.

        Args:
            user_id (int): The ID of the user.
            alias (str): The alias to set for the user.

        Returns:
            bool: True if the alias was set successfully,
                False if another user already has that alias.
        """

        if user := self.db.users.find_one({'alias': alias}):
            if user.get('user_id') == user_id:
                self.db.users.update_one({'user_id': user_id}, {
                                         '$set': {'alias': alias}})
                return True

            return False

        self.db.users.insert_one({
            'user_id': user_id,
            'alias': alias,
        })
        return True

    def delete_alias(self, user_id: int) -> bool:
        """
        Remove the alias for a user.

        Args:
            user_id (int): The ID of the user whose alias is to be removed.

        Returns:
            bool: True if the alias was removed successfully,
                False if no alias was found for the user.
        """

        if not self.db.users.find_one({'user_id': user_id}):
            return False

        self.db.users.delete_one({'user_id': user_id})
        return True

    def get_alias(self, user_id: int) -> str | None:
        """
        Get the alias for a user.

        Args:
            user_id (int): The ID of the user whose alias is to be retrieved.

        Returns:
            str | None: The alias of the user if it exists, otherwise None.
        """

        if data := self.db.users.find_one({'user_id': user_id}):
            return data.get('alias')
        return None

    async def default(self, message: Message, cmd: list[str]) -> str:
        if len(cmd) > 0:
            if self.set_alias(message.author.id, cmd[1]):
                return 'Alias has been updated.'

            return 'Failed to set alias: a different person is already using that name.'

        return (
            'Please choose an alias, e.g. `!alias MinecraftPlayer123`.\n' +
            'Alternatively, you can type `!alias help` for usage info.'
        )

    @subcommand
    async def help(self, message: Message, cmd: list[str]) -> str:
        """
        Display help information for the alias command.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments.

        Returns:
            str: A string containing the help information for the alias command.
        """

        return '\n'.join([
            'Set the username that players see when you send messages to the Flat Earth.',
            f'* `{self} help`: Display this help message.',
            f'* `{self} remove`: Remove your alias, setting username to match your discord name.',
            f'* `{self} show`: Show your current alias.',
            f'* `{self} {{anything else}}`: Sets your alias to the chosen name.',
        ])

    @subcommand
    async def remove(self, message: Message, cmd: list[str]) -> str:
        """
        Remove the alias for the user.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments.

        Returns:
            str: A message indicating whether the alias was successfully removed or not.
        """

        if self.delete_alias(message.author.id):
            return 'Alias sucessfully removed.'

        return 'No alias was found.'

    @subcommand
    async def show(self, message: Message, cmd: list[str]) -> str:
        """
        Show the current alias for the user.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments.

        Returns:
            str: A message indicating the current alias or that no alias was found.
        """

        if alias := self.get_alias(message.author.id):
            return f'Current alias: {alias}'

        return 'No alias was found.'
