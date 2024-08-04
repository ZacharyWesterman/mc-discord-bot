from commands import *

@command('help', 'Display this help message.')
class HelpCmd(Command):
	def default(self, message: object, command: list[str]) -> str:
		cmds = all()

		return '\n'.join([
			'Here is a list of available commands. Note that you must put a `/` or `!` in front of the command, or you can @ me. For example, `help @mc.skrunky.com` and `!help` are both valid.',
			*[f'* `{i}`: {cmds[i].desc}' for i in cmds if not cmds[i].admin_only or self.user_is_admin],
			'Most commands have help text to let you know how to use them, e.g. `!alias help`.',
			'You can also DM me to send messages directly to the Minecraft server.',
			'To view a map of the Flat Earth, or to download copy of the world, go to https://mc.skrunky.com',
		])
