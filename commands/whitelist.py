from commands import *
import json

@command('whitelist', 'Show whitelist info or add/remove players from the whitelist.')
class WhitelistCmd(Command):
	def get_whitelist(self) -> list[str]:
		with open('../minecraftbe/flatearth/allowlist.json') as fp:
			return [i.get('name', 'ERROR') for i in json.load(fp)]

	def default(self, message: Message, command: list[str]) -> str:
		whitelist = self.get_whitelist()

		if not len(command):
			return '\n'.join([
				f'{len(whitelist)} players are whitelisted:',
				*[f'> {i}' for i in whitelist],
			])

		player = command[0]

		if player in whitelist:
			return f'ERROR: Player `{player}` is already in the whitelist.'

		mc_command(f'whitelist add {player}')
		return f'Added player `{player}` to the whitelist.'

	@subcommand
	def help(self, message: Message, command: list[str]) -> str:
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
	def remove(self, message: Message, command: list[str]) -> str:
		if not self.user_is_admin:
			return bad_subcmd()

		if not len(command):
			return f'ERROR: No player name specified. Correct usage is `{self} {self.sub} {{username}}`.'

		whitelist = self.get_whitelist()
		player = command[0]

		if player not in whitelist:
			return f'ERROR: Player `{player}` is not in the whitelist.'

		mc_command(f'whitelist remove {player}')
		return f'Removed player `{player}` from the whitelist.'
