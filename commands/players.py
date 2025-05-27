"""A command to list players currently logged into the Minecraft server."""

from datetime import datetime
from pathlib import Path

from discord import Message

from commands import Command, command


@command('players', 'List what players are logged in.', 'minecraft')
class PlayersCmd(Command):
    """
    Command to list players currently logged into the Minecraft server.
    This command scans the server log files for player connection events
    and returns a list of players who are currently online.
    """

    def get_logfile_paths(self) -> list[str]:
        """
        Get the paths of today's log files.
        The log files are expected to be in the format 'flatearth.YYYY.MM.DD.*'.

        Returns:
            list[str]: A list of paths to the log files for today.
        """

        now = datetime.now().strftime('%Y.%m.%d.')
        logfile_paths = []
        for i in Path('../minecraftbe/flatearth/logs/').glob(f'flatearth.{now}*'):
            if len(logfile_paths) == 0 or str(i) > logfile_paths[-1]:
                logfile_paths += [str(i)]

        return logfile_paths

    def calculate_players(self, logfile_paths: list[str]) -> dict[str, bool]:
        """
        Calculate the list of players currently online based on the log files.

        Args:
            logfile_paths (list[str]): A list of paths to the log files.

        Returns:
            dict[str, bool]: A dictionary where keys are player names and values
                are booleans indicating if the player is online.
        """

        logfile_paths = self.get_logfile_paths()
        players = {}

        for logfile_path in logfile_paths:
            try:
                with open(logfile_path, 'r', encoding='utf8') as fp:
                    lines = [i for i in fp.readlines() if ' INFO] Player ' in i]

                    for line in lines:
                        info = line.split(' ')

                        action, player = info[6][:-1].lower(), info[7][:-1]
                        if action != 'spawned':
                            players[player] = action == 'connected'

            except FileNotFoundError:
                pass

        return players

    async def default(self, message: Message, cmd: list[str]) -> str:
        # Scan today's log files for list of online players

        logfile_paths = self.get_logfile_paths()

        if len(logfile_paths) == 0:
            return 'ERROR: Failed to get list of users: cannot open server log.'

        players = self.calculate_players(logfile_paths)

        player_list = [key for key, val in players.items() if val]
        count = len(player_list)
        plural = 's' if count != 1 else ''
        verb = 'are' if count != 1 else 'is'
        response = f'There {verb} {count} player{plural} logged in currently.'
        if count:
            response += ''.join([f'\n> {i}' for i in player_list])

        return response
