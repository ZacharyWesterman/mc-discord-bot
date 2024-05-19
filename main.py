#!/usr/bin/env python3

import discord
from discord.ext import tasks
import json, re
import subprocess
from pathlib import Path
from mcstatus import BedrockServer
from pymongo import MongoClient

with open(str(Path(__file__).parent) + '/secrets.json', 'r') as fp:
	data = json.load(fp)
	DISCORD_TOKEN = data['token']
	GUILD_ID = data['guild']

db = MongoClient().flatearth

def read_message(id: int) -> dict:
	return db.messages.find_one({'message_id': id})

def create_message(id: int, msg: dict) -> None:
	msg['message_id'] = id
	msg['updated'] = False
	db.messages.insert_one(msg)

def update_message_emojis(id: int, emojis: list[str]) -> None:
	db.messages.update_one({'message_id': id}, {'$set': {
		'emojis': emojis,
		'updated': True,
	}})

def log(msg: str) -> None:
	print(msg, flush=True)

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

	response_text = 'tellraw @a ' + json.dumps(response).replace('\\','\\\\').replace('$', '\\$') + '\\n'

	command = ['screen', '-r', 'flatearth', '-p', '0', '-X', 'stuff', response_text]
	subprocess.run(command)

class DiscordClient(discord.Client):
	async def on_ready(self):
		print('Logged in as ', self.user)
		self.sync_status_message.start()

		self.activity = None

	@tasks.loop(seconds = 15)
	async def sync_status_message(self):
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

	async def on_message(self, message: discord.Message):
		#Don't respond to ourselves
		if message.author == self.user:
			return

		#Doesn't work, need to find some other way to get the player list!
		async def players_cmd(command: list[str]):
			status = MINECRAFT.status()
			count = status.players.online
			plural = 's' if count != 1 else ''
			verb = 'are' if count != 1 else 'is'
			response = f'There {verb} {count} player{plural} logged in currently.'
			if count:
				response += '\n'.join([f'> {i}' for i in status.players.sample])

			await message.channel.send(response)

		valid_commands = {
			'help': {
				'info': 'Display this help message.',
				'action': None,
			},
			# 'players': {
			# 	'info': 'List what players are logged in.',
			# 	'action': players_cmd,
			# },
		}

		async def help_cmd(command: list[str]):
			response = 'Here is a list of available commands. Note that you must put a `/` or `!` in front of the command, or you can @ me. For example, `help @mc.skrunky.com` and `!help` are both valid.\n'
			response += '\n'.join(f'* {i}: {valid_commands[i]["info"]}' for i in valid_commands)
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
			if len(this_command) == 0:
				this_command = ['help']

			if this_command[0] not in valid_commands:
				await message.channel.send('Unknown command. Type `@mc.skrunky.com`, `!help` or `/help` for a list of commands.')
				return

			action = valid_commands[ this_command[0] ]['action']
			await action(this_command)


		return

		if isinstance(message.channel, discord.channel.DMChannel):
			#When a user DMs the bot, react to the message to indicate that their message has been sent to the server
			log(f'Received DM from {message.author}: {message.content}')
			send_message_minecraft(message.author, message.content)

			try:
				await message.add_reaction('✅')
			except Exception as e:
				log(f'Failed to respond to DM: {e}')

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
