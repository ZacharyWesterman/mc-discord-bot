from commands import *

@command('alias', 'Set the username that players see when you send messages to the Flat Earth.', 'minecraft')
class AliasCmd(Command):
	#Returns false if another user already has that alias
	def set_alias(self, user_id: str, alias: str) -> bool:
		if user := self.db.users.find_one({'alias': alias}):
			if user.get('user_id') == user_id:
				self.db.users.update_one({'user_id': user_id}, {'$set': {'alias': alias}})
				return True

			return False

		self.db.users.insert_one({
			'user_id': user_id,
			'alias': alias,
		})
		return True

	#Returns false if no alias for user was found
	def delete_alias(self, user_id: str) -> bool:
		if not self.db.users.find_one({'user_id': user_id}):
			return False

		self.db.users.delete_one({'user_id': user_id})
		return True

	def get_alias(self, user_id: str) -> str|None:
		if data := self.db.users.find_one({'user_id': user_id}):
			return data.get('alias')
		return None

	def default(self, message: object, command: list[str]) -> str:
		if len(command):
			if self.set_alias(message.author.id, command[1]):
				return 'Alias has been updated.'

			return 'Failed to set alias: a different person is already using that name.'

		return 'Please choose an alias, e.g. `!alias MinecraftPlayer123`.\nAlternatively, you can type `!alias help` for usage info.'

	@subcommand
	def help(self, message: object, command: list[str]) -> str:
		return '\n'.join([
			'Set the username that players see when you send messages to the Flat Earth.',
			f'* `{self} help`: Display this help message.',
			f'* `{self} remove`: Remove your alias, setting username to match your discord name.',
			f'* `{self} show`: Show your current alias.',
			f'* `{self} {{anything else}}`: Sets your alias to the chosen name.',
		])

	@subcommand
	def remove(self, message: object, command: list[str]) -> str:
		if self.delete_alias(message.author.id):
			return 'Alias sucessfully removed.'

		return 'No alias was found.'

	@subcommand
	def show(self, message: object, command: list[str]) -> str:
		if alias := self.get_alias(message.author.id):
			return f'Current alias: {alias}'

		return 'No alias was found.'
