from commands import *
from datetime import datetime
from pathlib import Path

@command('players', 'List what players are logged in.')
class PlayersCmd(Command):
	def get_logfile_paths(self) -> list[str]:
		now = datetime.now().strftime('%Y.%m.%d.')
		logfile_paths = []
		for i in Path('../minecraftbe/flatearth/logs/').glob(f'flatearth.{now}*'):
			if len(logfile_paths) == 0 or str(i) > logfile_paths[-1]:
				logfile_paths += [str(i)]

		return logfile_paths

	def default(self, message: Message, command: list[str]) -> str:
		#Scan today's log files for list of online players

		logfile_paths = self.get_logfile_paths()
		players = {}

		for logfile_path in logfile_paths:
			try:
				with open(logfile_path, 'r') as fp:
					lines = [ i for i in fp.readlines() if ' INFO] Player ' in i ]

					for i in range(len(lines)):
						info = lines[i].split(' ')

						action, player = info[6][:-1].lower(), info[7][:-1]
						if action != 'spawned':
							players[player] = (action == 'connected')

			except FileNotFoundError:
				pass

		if len(logfile_paths) == 0:
			return f'ERROR: Failed to get list of users: cannot open server log.'

		player_list = [i for i in players if players[i]]
		count = len(player_list)
		plural = 's' if count != 1 else ''
		verb = 'are' if count != 1 else 'is'
		response = f'There {verb} {count} player{plural} logged in currently.'
		if count:
			response += ''.join([f'\n> {i}' for i in player_list])

		return response
