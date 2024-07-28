#!/usr/bin/env python3

import discord
from discord.ext import tasks
import json, re
import subprocess
from pathlib import Path
from mcstatus import BedrockServer
from pymongo import MongoClient
from datetime import datetime
import math

with open(str(Path(__file__).parent) + '/secrets.json', 'r') as fp:
	data = json.load(fp)
	DISCORD_TOKEN = data['token']
	GUILD_ID = data['guild']

db = MongoClient().flatearth

def read_message(id: int) -> dict:
	return db.messages.find_one({'message_id': id})

def count_messages(label: str) -> int:
	return db.messages.count_documents({'label': label.upper()})

def find_message(label: str) -> dict|None:
	return db.messages.find_one({'label': label.upper()})

def create_message(id: int, msg: dict) -> None:
	msg['message_id'] = id
	msg['updated'] = False
	msg['created'] = datetime.utcnow()
	msg['last_updated'] = None
	db.messages.insert_one(msg)

def update_message_emojis(id: int, emojis: list[str]) -> None:
	db.messages.update_one({'message_id': id}, {'$set': {
		'emojis': emojis,
		'updated': True,
		'last_updated': datetime.utcnow(),
	}})

def get_valid_messages(start: int, count: int) -> list[dict]:
	return [
		i for i in db.messages.find({
			'emojis.0': {'$exists': True},
		}).sort({'label': 1}).skip(start).limit(count)
	]

def count_valid_messages() -> int:
	return db.messages.count_documents({
		'emojis.0': {'$exists': True},
	})

def get_logfile_paths() -> list[str]:
	now = datetime.now().strftime('%Y.%m.%d.')
	logfile_paths = []
	for i in Path('../minecraftbe/flatearth/logs/').glob(f'flatearth.{now}*'):
		if len(logfile_paths) == 0 or str(i) > logfile_paths[-1]:
			logfile_paths += [str(i)]

	return logfile_paths

#Returns false if another user already has that alias
def set_alias(user_id: str, alias: str) -> bool:
	if user := db.users.find_one({'alias': alias}):
		if user.get('user_id') == user_id:
			db.users.update_one({'user_id': user_id}, {'$set': {'alias': alias}})
			return True

		return False

	db.users.insert_one({
		'user_id': user_id,
		'alias': alias,
	})
	return True

#Returns false if no alias for user was found
def delete_alias(user_id: str) -> bool:
	if not db.users.find_one({'user_id': user_id}):
		return False

	db.users.delete_one({'user_id': user_id})
	return True

def get_alias(user_id: str) -> str|None:
	if data := db.users.find_one({'user_id': user_id}):
		return data.get('alias')
	return None

def get_whitelist() -> list[str]:
	with open('../minecraftbe/flatearth/allowlist.json') as fp:
		return [i.get('name', 'ERROR') for i in json.load(fp)]

def unauthorized_msg() -> str:
	return 'You are not authorized to perform that action.'

def log(msg: str) -> None:
	print(msg, flush=True)

def mc_command(text: str) -> None:
	subprocess.run(['screen', '-r', 'flatearth', '-p', '0', '-X', 'stuff', text.replace('\\','\\\\').replace('$', '\\$') + '\\n'])

# Fake a player message
def send_message_minecraft(author: str, content: str) -> None:
	repl = {
		'“': '"',
		'”': '"',
		'‘': "'",
		'’': "'",
		'’': "'",
		'…': "...",
		'😀': ':)',
		'😃': ':D',
		'😄': '=)',
		'😆': 'XD',
		'😉': ';)',
		'😅': '^_^\'',
		'🤗': ':hug',
		'😁': ':D',
		'😂': 'XD',
		'😊': '^_^',
		'😍': '<3',
		'😘': ':-*',
		'😜': ';P',
		'😎': 'B)',
		'😔': ':(',
		'😢': ':\'(',
		'😡': '>:(',
		'😱': ':O',
		'😴': '-_-',
		'👍': ':thumbsup:',
		'👏': ':clap:',
		'🙌': '\\o/',
		'🙏': ':pray:',
		'💪': ':muscle:',
		'🎉': ':party:',
		'🌟': ':star:',
	}
	for i in repl:
		content = content.replace(i, repl[i])

	response = {
		'rawtext': [{
			'text': f'<{author}> {content}'
		}]
	}
	mc_command('tellraw @a ' + json.dumps(response))

class DiscordClient(discord.Client):
	async def on_ready(self):
		print('Logged in as ', self.user)
		self.sync_status_message.start()

		self.activity = None

	@tasks.loop(seconds = 15)
	async def sync_status_message(self):
		#Update discord bot status to reflect whether players are online
		status = MINECRAFT.status()
		count = status.players.online

		if count == 0:
			status = discord.Status.idle
			activity = 'an empty server'
		else:
			status = discord.Status.online
			activity = str(count) + ' player' + ('' if count == 1 else 's')

		if self.activity != activity:
			act = discord.Activity(name = activity, type = discord.ActivityType.watching)
			await self.change_presence(status = status, activity = act)

		#Fetch any updated messages and convert them into markers
		updated = {
			'overworld': False,
			'nether': False,
			'end': False,
		}

		for message in db.messages.find({'updated': True}):
			x_coord = message['coords'][0]
			z_coord = message['coords'][1] if len(message['coords']) == 2 else message['coords'][2]
			label = message['label']

			#Remove any marker on the specified position, in any dimension.
			for i in db.markers.find({'x': x_coord, 'z': z_coord}):
				updated[i['dimension']] = True
			db.markers.delete_many({'x': x_coord, 'z': z_coord})

			#Place the new marker
			for dimension in message['emojis']:
				marker = {
					'x': x_coord,
					'z': z_coord,
					'image': 'custom.pin.png',
					'imageAnchor': [0.5, 1],
					'imageScale': 0.3,
					'dimension': dimension,
					'text': f'{label}',
					'textColor': 'white',
					'offsetX': 0,
					'offsetY': 20,
					'font': 'bold 20px Calibri,sans serif',
					'style': 'border: 2px solid red;',
				}
				db.markers.insert_one(marker)
				updated[dimension] = True

			db.messages.update_one({'_id': message['_id']}, {'$set': {'updated': False}})

		#If marker updates involved any change, update only the respective files
		for dimension in [i for i in updated if updated[i]]:
			def process(marker: dict) -> dict:
				del marker['_id']
				del marker['dimension']
				return marker

			text = 'UnminedCustomMarkers = { isEnabled: true, markers: ' + json.dumps([
				process(i) for i in db.markers.find({'dimension': dimension})
			], indent = 2) + '}'

			with open(f'/var/www/html/maps/{dimension}/custom.markers.js', 'w') as fp:
				fp.write(text)

			print(f'Updated {dimension} map.', flush=True)


	async def on_message(self, message: discord.Message):
		#Don't respond to ourselves
		if message.author == self.user:
			return

		#Only respond to commands & messages if this is a DM, or it's in the games channel
		if not isinstance(message.channel, discord.channel.DMChannel) and message.channel.name != 'games':
			return

		user_is_admin = db.admins.find_one({'id': str(message.author.id)})

		async def players_cmd(command: list[str]):
			#Scan most recent log file for list of online players

			logfile_paths = get_logfile_paths()
			players = {}

			for logfile_path in logfile_paths:
				try:
					with open(logfile_path, 'r') as fp:
						lines = [ i for i in fp.readlines() if ' INFO] Player ' in i ]

						for i in range(len(lines) - 1, 0, -1):
							info = lines[i].split(' ')
							action, player = info[6][:-1], info[7][:-1]
							if player not in players and action != 'Spawned':
								players[player] = (action == 'connected')

				except FileNotFoundError:
					pass

			if len(logfile_paths) == 0:
				response = f'ERROR: Failed to get list of users: cannot open server log.'
			else:
				player_list = [i for i in players if players[i]]
				count = len(player_list)
				plural = 's' if count != 1 else ''
				verb = 'are' if count != 1 else 'is'
				response = f'There {verb} {count} player{plural} logged in currently.'
				if count:
					response += ''.join([f'\n> {i}' for i in player_list])

			await message.channel.send(response)

		async def alias_cmd(command: list[str]):
			if len(command) < 2:
				response = 'Please choose an alias, e.g. `!alias MinecraftPlayer123`.\nAlternatively, you can type `!alias help` for usage info.'
			elif command[1] == 'remove':
				if delete_alias(message.author.id):
					response = 'Alias sucessfully removed.'
				else:
					response = 'No alias was found.'
			elif command[1] == 'show':
				alias = get_alias(message.author.id)
				if alias:
					response = f'Current alias: {alias}'
				else:
					response = 'No alias was found.'
			elif command[1] == 'help':
				response = '\n'.join([
					'Set the username that players see when you send messages to the Flat Earth.',
					'* `!alias help`: Display this help message.',
					'* `!alias remove`: Remove your alias, setting username to match your discord name.',
					'* `!alias show`: Show your current alias.',
					'* `!alias {anything else}`: Sets your alias to the chosen name.',
				])
			else:
				if set_alias(message.author.id, command[1]):
					response = 'Alias has been updated.'
				else:
					response = 'Failed to set alias: a different person is already using that name.'

			await message.channel.send(response)

		async def whitelist_cmd(command: list[str]):
			whitelist = get_whitelist()

			if len(command) < 2:
				response = f'{len(whitelist)} players are whitelisted:\n> ' + '\n> '.join(whitelist)
			elif command[1] == 'help':
				msgs = [
					'View and manage whitelisted players.',
					'* `!whitelist`: List all whitelisted players.',
					'* `!whitelist help`: Display this help message.',
				]
				if user_is_admin:
					msgs += [
						'* `!whitelist remove {username}`: Remove a player from the whitelist.',
						'* `!whitelist {username}`: Add a player to the whitelist.',
					]

				response = '\n'.join(msgs)
			elif command[1] == 'remove':
				if user_is_admin:
					if len(command) < 3:
						response = 'ERROR: No player name specified. Correct usage is `!whitelist remove {username}`.'
					elif command[2] not in whitelist:
						response = f'ERROR: Player `{command[2]}` is not in the whitelist.'
					else:
						#Remove the user from the whitelist
						mc_command(f'whitelist remove {command[2]}')
						response = f'Removed player `{command[2]}` from the whitelist.'
				else:
					response = unauthorized_msg()
			else:
				if user_is_admin:
					if command[1] in whitelist:
						response = f'ERROR: Player `{command[1]}` is already in the whitelist.'
					else:
						#Add the user to the whitelist
						mc_command(f'whitelist add {command[1]}')
						response = f'Added player `{command[1]}` to the whitelist.'
				else:
					response = unauthorized_msg()

			await message.channel.send(response)

		async def admin_cmd(command: list[str]):
			pass #Not really sure what to do with this...

		async def message_cmd(command: list[str]):
			#When a user DMs the bot, react to the message to indicate that their message has been sent to the server

			if len(command) < 2 or command[1] == 'help':
				response = '\n'.join([
					'To send a message to the Flat Earth, specify some text like `!say your message here`.',
					'Alternatively, you can DM me and all messages will go directly to the Flat Earth.',
				])
				await message.channel.send(response)

			else:
				alias = get_alias(message.author.id)
				if alias is None:
					alias = str(message.author)
					log(f'Received DM from {message.author}: {message.content}')
				else:
					log(f'Received DM from {message.author}({alias}): {message.content}')

				send_message_minecraft(alias, ' '.join(command[1::]))

				try:
					await message.add_reaction('✅')
				except Exception as e:
					log(f'Failed to respond to DM: {e}')

		async def location_cmd(command: list[str]):
			MAX_POI = 10
			msg_ct = count_valid_messages()
			page_ct = math.ceil(msg_ct / MAX_POI)

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

			if len(command) < 2 or command[1] == 'help':
				response = '\n'.join([
					'View or edit points of interest in the Flat Earth.',
					'Note that points of interest are sorted alphabetically.',
					'* `!location list`: Show the first page of all points of interest.',
					'* `!location list {page}`: Show the given page of points of interest.',
					'* `!location count`: Show the total number of points of interest.',
					'* `!location delete {location name}`: Delete a point of interest. The name is not case sensitive.',
					'To add a new point of interest, type a description of the location along with the coordinates, then click an emoji indicating what dimension it\'s in.',
					'For example, `village -123 456`, `-12,34,-56 mesa biome`, and `deep 123,-456 dark` are all valid points of interest.',
					'To rename a point of interest, just add a new one with the exact same coordinates.',
					'To delete a point of interest, remove all your emojis from the original message, or use the `!location delete` command.',
				])
			elif command[1] == 'list':
				response = ''
				page_number = 1

				if len(command) >= 3:
					if not re.match(r'^\d+$', command[2]) or int(command[2]) < 1:
						response += f'Invalid page number `{command[2]}`, defaulting to `1`.\n'
						page_number = 1
					else:
						page_number = int(command[2])

				if page_number > page_ct:
					response += f'Invalid page number `{page_number}`, defaulting to `{page_ct}`.\n'
					page_number = page_ct

				response += f'Points of interest (page {page_number}/{page_ct})'
				for i in get_valid_messages((page_number-1) * MAX_POI, MAX_POI):
					response += f"\n> `{i.get('label', 'ERR: NO LABEL')}`: {i.get('coords', [])} {''.join(emojis[i] for i in i.get('emojis', []))}"
			elif command[1] == 'count':
				response = f'There are {msg_ct} points of interest ({page_ct} page{"s" if page_ct != 1 else ""}).'

			elif command[1] == 'delete' and len(command) < 3:
				response = 'Please specify a point of interest to delete.'

			elif command[1] == 'delete':
				label = ' '.join(command[2::])
				ct = count_messages(label)
				if ct == 0:
					response = f'No point of interest was found with label `{label}`.'
				elif ct > 1:
					response = 'Multiple points of interest were found with that label... Please talk to zachy this shouldn\'t be happening :('
				else:
					msg = find_message(label)
					if msg is None:
						response = 'ERROR: PoI exists but also doesnt??? Poke and prod zachy!!'
					else:
						update_message_emojis(msg['message_id'], []) #Delete all locations
						response = f'Deleted `{msg["label"]}`.'
			else:
				response = 'ERROR: Invalid command.'

			await message.channel.send(response)

		valid_commands = {
			'help': {
				'info': 'Display this help message.',
				'action': None,
			},
			'players': {
				'info': 'List what players are logged in.',
				'action': players_cmd,
			},
			'alias': {
				'info': 'Set the username that players see when you send messages to the Flat Earth.',
				'action': alias_cmd,
			},
			'whitelist': {
				'info': 'Show whitelist info or add/remove players from the whitelist.',
				'action': whitelist_cmd,
			},
			'say': {
				'info': 'Send a message to the Flat Earth.',
				'action': message_cmd,
			},
			'location': {
				'info': 'View or edit points of interest in the Flat Earth.',
				'action': location_cmd,
			}
			# 'admin': {
			# 	'info': 'Add or remove discord users from making admin actions related to the Flat Earth.',
			# 	'action': admin_cmd,
			# 	'admin_only': True,
			# }
		}

		async def help_cmd(command: list[str]):
			response = 'Here is a list of available commands. Note that you must put a `/` or `!` in front of the command, or you can @ me. For example, `help @mc.skrunky.com` and `!help` are both valid.\n'
			response += '\n'.join(f'* `{i}`: {valid_commands[i]["info"]}' for i in valid_commands if user_is_admin or not valid_commands[i].get('admin_only'))
			response += '\nMost commands have help text to let you know how to use them, e.g. `!alias help`.'
			response += '\nYou can also DM me to send messages directly to the Minecraft server.'
			await message.channel.send(response)

		valid_commands['help']['action'] = help_cmd

		#If someone sent a command, handle that
		this_command = None
		msg = None
		if f'<@{self.user.id}>' in message.content:
			msg = message.content.replace(f'<@{self.user.id}>', '')
			this_command = msg.strip().split(' ')
		else:
			this_command = message.content.strip().split(' ')
			if len(this_command) and this_command[0][1::] in valid_commands:
				this_command[0] = this_command[0][1::]
				msg = message.content

		if msg is not None:
			if len(this_command) == 0 or this_command[0] == '':
				this_command = ['help']

			if this_command[0] not in valid_commands or (valid_commands[this_command[0]].get('admin_only') and not user_is_admin):
				await message.channel.send('Unknown command. Type `@mc.skrunky.com`, `!help` or `/help` for a list of commands.')
				return

			action = valid_commands[ this_command[0] ]['action']
			await action(this_command)
			return


		if isinstance(message.channel, discord.channel.DMChannel):
			await message_cmd(['message', message.content])
			return

		if message.channel.name != 'games':
			return

		#Check if the message has two consecutive integers in it. If so, it's most likely coordinates
		pattern = re.compile(r'(-?\b([0-9]+)([, ]+|$)){2,}')
		match = pattern.search(message.content)

		if match:
			begin, end = match.span(0)
			pre, mid, post = message.content[0:begin], message.content[begin:end], message.content[end::]

			text = f'{pre} {post}'.replace(',', '').replace(':', '').strip().upper()
			coords = [int(i) for i in mid.replace(',', ' ').split()]

			msg = {
				'emojis': [],
				'text': message.content,
				'label': text,
				'coords': coords,
				'author': message.author.id,
			}
			create_message(message.id, msg)

			for i in ['overworld', 'nether', 'end']:
				for emoji in message.guild.emojis:
					if emoji.name == i:
						try:
							await message.add_reaction(emoji)
						except Exception as e:
							log(f'Failed to react with custom emoji: {e}')
						break

	async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
		if payload.emoji.name not in ['overworld', 'nether', 'end']:
			return

		#Ignore reactions from this bot
		if payload.user_id == self.user.id:
			return

		msg = read_message(payload.message_id)
		if msg is None:
			return

		#Ignore users reacting to someone else's message
		if msg['author'] != payload.user_id:
			return

		if payload.emoji.name not in msg['emojis']:
			msg['emojis'] += [payload.emoji.name]

		update_message_emojis(payload.message_id, msg['emojis'])

		#Remove automatic reactions
		channel = await self.fetch_channel(payload.channel_id)
		message = await channel.fetch_message(payload.message_id)
		for i in ['overworld', 'nether', 'end']:
			for emoji in message.guild.emojis:
				if emoji.name == i:
					try:
						await message.remove_reaction(emoji, self.user)
					except Exception as e:
						log(f'Failed to react with custom emoji: {e}')
					break

	async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
		if payload.emoji.name not in ['overworld', 'nether', 'end']:
			return

		if payload.user_id == self.user.id:
			return

		msg = read_message(payload.message_id)
		if msg is None:
			return

		if msg['author'] != payload.user_id:
			return

		msg['emojis'].remove(payload.emoji.name)
		update_message_emojis(payload.message_id, msg['emojis'])

MINECRAFT = BedrockServer.lookup('127.0.0.1')

INTENTS = discord.Intents.all()
CLIENT = DiscordClient(intents=INTENTS)
CLIENT.run(DISCORD_TOKEN)
