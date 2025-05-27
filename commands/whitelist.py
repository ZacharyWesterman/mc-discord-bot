"""
Manage the Minecraft whitelist.
"""

import json

from discord import Message

from commands import Command, bad_subcmd, command, mc_command, subcommand


@command('whitelist', 'Show whitelist info or add/remove players from the whitelist.', 'minecraft')
class WhitelistCmd(Command):
    """
    Command to manage the Minecraft whitelist.
    This command allows privileged users to view the current whitelist,
    add players to it, or remove players from it.
    """

    def get_whitelist(self) -> list[str]:
        """
        Load the whitelist from the allowlist.json file.

        Returns:
            list[str]: A list of whitelisted player names.
        """

        with open('../minecraftbe/flatearth/allowlist.json', 'r', encoding='utf8') as fp:
            return [i.get('name', 'ERROR') for i in json.load(fp)]

    async def default(self, message: Message, cmd: list[str]) -> str:
        whitelist = self.get_whitelist()

        if len(cmd) == 0:
            return '\n'.join([
                f'{len(whitelist)} players are whitelisted:',
                *[f'> {i}' for i in whitelist],
            ])

        player = cmd[0]

        if player in whitelist:
            return f'ERROR: Player `{player}` is already in the whitelist.'

        mc_command(f'whitelist add {player}')
        return f'Added player `{player}` to the whitelist.'

    @subcommand
    async def add(self, message: Message, cmd: list[str]) -> str:
        """
        Add a player to the whitelist.
        This command can only be used by users with admin privileges.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments, where the first argument is the player name to add.

        Returns:
            str: A message indicating the result of the operation.
        """

        return await self.default(message, cmd)

    @subcommand
    async def help(self, message: Message, cmd: list[str]) -> str:
        """
        Display help information for the whitelist command.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments, where the first argument is 'help'.

        Returns:
            str: A help message detailing the usage of the whitelist command.
        """

        return '\n'.join([
            'View and manage whitelisted players.',
            f'* `{self}`: List all whitelisted players.',
            f'* `{self} help`: Display this help message.',
            *([
                f'* `{self} remove {{username}}`: Remove a player from the whitelist.',
                f'* `{self} {{username}}`: Add a player to the whitelist.',
            ] if self.user_is_admin else []),
        ])

    @subcommand
    async def remove(self, message: Message, cmd: list[str]) -> str:
        """
        Remove a player from the whitelist.
        This command can only be used by users with admin privileges.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments, where the
                first argument is the player name to remove.

        Returns:
            str: A message indicating the result of the operation.
        """

        if not self.user_is_admin:
            return bad_subcmd('remove')

        if len(cmd) == 0:
            return (
                'ERROR: No player name specified. ' +
                f'Correct usage is `{self} {self.sub} {{username}}`.'
            )

        whitelist = self.get_whitelist()
        player = cmd[0]

        if player not in whitelist:
            return f'ERROR: Player `{player}` is not in the whitelist.'

        mc_command(f'whitelist remove {player}')
        return f'Removed player `{player}` from the whitelist.'
