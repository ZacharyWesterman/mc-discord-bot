from commands import *
from math import ceil
import re
from datetime import datetime

MAX_POI = 10

@command('location', 'View or edit points of interest in the Flat Earth.')
class LocationCmd(Command):
	def count_valid_messages(self) -> int:
		return self.db.messages.count_documents({
			'emojis.0': {'$exists': True},
		})

	def get_valid_messages(self, start: int, count: int) -> list[dict]:
		return [
			i for i in self.db.messages.find({
				'emojis.0': {'$exists': True},
			}).sort({'label': 1}).skip(start).limit(count)
		]

	def count_messages(self, label: str) -> int:
		return self.db.messages.count_documents({'label': label.upper()})

	def find_message(self, label: str) -> dict|None:
		return self.db.messages.find_one({'label': label.upper()})

	def get_emojis(self, message: Message) -> list[str]:
		emojis = {
			'overworld': 'overworld ',
			'nether': 'nether ',
			'end': 'end ',
		}
		if message.guild:
			for i in ['overworld', 'nether', 'end']:
				for emoji in message.guild.emojis:
					if emoji.name == i:
						emojis[i] = f'<:{i}:{emoji.id}>'

		return emojis

	def update_message_emojis(self, id: int, emojis: list[str]) -> None:
		self.db.messages.update_one({'message_id': id}, {'$set': {
			'emojis': emojis,
			'updated': True,
			'last_updated': datetime.utcnow(),
		}})

	def default(self, message: Message, command: list[str]) -> str:
		if not len(command) or command[0] == 'help':
			return '\n'.join([
				'View or edit points of interest in the Flat Earth.',
				'Note that points of interest are sorted alphabetically.',
				f'* `{self} list`: Show the first page of all points of interest.',
				f'* `{self} list {{page}}`: Show the given page of points of interest.',
				f'* `{self} count`: Show the total number of points of interest.',
				f'* `{self} delete {{location name}}`: Delete a point of interest. The name is not case sensitive.',
				'To add a new point of interest, type a description of the location along with the coordinates, then click an emoji indicating what dimension it\'s in.',
				'For example, `village -123 456`, `-12,34,-56 mesa biome`, and `deep 123,-456 dark` are all valid points of interest.',
				'To rename a point of interest, just add a new one with the exact same coordinates.',
				f'To delete a point of interest, remove all your emojis from the original message, or use the `{self} delete` command.',
			])

		return bad_subcmd(command[0])

	@subcommand
	def count(self, message: Message, command: list[str]) -> str:
		msg_ct = self.count_valid_messages()
		page_ct = ceil(msg_ct / MAX_POI)
		return f'There are {msg_ct} points of interest ({page_ct} page{"s" if page_ct != 1 else ""}).'

	@subcommand
	def delete(self, message: Message, command: list[str]) -> str:
		if not len(command):
			return 'ERROR: Please specify a point of interest to delete.'

		label = ' '.join(command)
		ct = self.count_messages(label)

		if ct == 0:
			return f'No point of interest was found with label `{label}`.'

		if ct > 1:
			return 'Multiple points of interest were found with that label... Please talk to zachy this shouldn\'t be happening :('

		msg = self.find_message(label)
		if msg is None:
			return 'ERROR: PoI exists but also doesnt??? Poke and prod zachy!!'

		self.update_message_emojis(msg['message_id'], []) #Delete all locations
		return f'Deleted `{msg["label"]}`.'

	@subcommand
	def list(self, message: Message, command: list[str]) -> str:
		response = ''
		page_number = 1
		msg_ct = self.count_valid_messages()
		page_ct = ceil(msg_ct / MAX_POI)

		if len(command):
			if not re.match(r'^\d+$', command[0]) or int(command[0]) < 1:
				response += f'Invalid page number `{command[0]}`, defaulting to `1`.\n'
				page_number = 1
			else:
				page_number = int(command[0])

		if page_number > page_ct:
			response += f'Invalid page number `{page_number}`, defaulting to `{page_ct}`.\n'
			page_number = page_ct

		emojis = self.get_emojis(message)

		response += f'Points of interest, page {page_number} of {page_ct} ({msg_ct} total)'
		for i in self.get_valid_messages((page_number-1) * MAX_POI, MAX_POI):
			response += f"\n> `{i.get('label', 'ERR: NO LABEL')}`: {i.get('coords', [])} {''.join(emojis[i] for i in i.get('emojis', []))}"

		return response
