#!/usr/bin/env python3

import discord
from discord.ext import tasks
import json
import subprocess
import requests
from pathlib import Path

DISCORD_TOKEN = open(str(Path(__file__).parent) + '/secret.txt', 'r').read().strip()

def log(msg: str) -> None:
	print(msg, flush=True)

# Fake a player message
def send_message_minecraft(author: str, content: str) -> None:
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

	@tasks.loop(seconds = 60)
	async def sync_status_message(self):
		activity = 'ERROR'
		status = discord.Status.do_not_disturb

		#Side note, this data is cached for 5 minutes. Might want a more accurate way to do this...
		res = requests.get('https://api.mcsrvstat.us/bedrock/2/mc.skrunky.com')
		if res.status_code == 200:
			data = json.loads(res.text)
			count = data.get('players',{}).get('online')

			if count == 0:
				status = discord.Status.idle
				activity = 'an empty server'
			else:
				status = discord.Status.online
				activity = str(count) + ' player' + ('' if count == 1 else 's')


		if activity is None:
			await self.change_presence(status = status)
		else:
			act = discord.Activity(name = activity, type = discord.ActivityType.watching)
			await self.change_presence(status = status, activity = act)

	async def on_message(self, message):
		#Don't respond to ourselves
		if message.author == self.user:
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


INTENTS = discord.Intents.default()
CLIENT = DiscordClient(intents=INTENTS)
CLIENT.run(DISCORD_TOKEN)

