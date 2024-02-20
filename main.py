#!/usr/bin/env python3

import discord
from discord.ext import tasks
import json
import subprocess
import requests
from pathlib import Path
from mcstatus import BedrockServer

with open(str(Path(__file__).parent) + '/secrets.json', 'r') as fp:
	data = json.load(fp)
	DISCORD_TOKEN = data['token']
	GUILD_ID = data['guild']

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
		await TREE.sync(guild=discord.Object(id=GUILD_ID))

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

MINECRAFT = BedrockServer.lookup('127.0.0.1')

INTENTS = discord.Intents.default()
CLIENT = DiscordClient(intents=INTENTS)
TREE = discord.app_commands.CommandTree(CLIENT)


@TREE.command(name="test_command", description="this is a test command")
async def slash_command(interaction: discord.Interaction):
	await interaction.response.send_message("test response")


CLIENT.run(DISCORD_TOKEN)

