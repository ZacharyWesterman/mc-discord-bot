#!/usr/bin/env python3

import json
import re
from datetime import datetime
from pathlib import Path

import discord
from discord import Forbidden, HTTPException, NotFound
from discord.ext import tasks
from mcstatus import BedrockServer

import commands

with open(str(Path(__file__).parent) + '/secrets.json', 'r', encoding='utf8') as fp:
    data = json.load(fp)
    DISCORD_TOKEN = data['token']
    GUILD_ID = data['guild']


def read_message(id: int) -> dict | None:
    """
    Read a message from the database by its ID.

    Args:
        id (int): The ID of the message to read.

    Returns:
        dict | None: The message document if found, otherwise None.
    """
    return commands.db.messages.find_one({'message_id': id})


def create_message(id: int, msg: dict) -> None:
    """
    Create a new message in the database with the given ID and content.

    Args:
        id (int): The ID of the message to create.
        msg (dict): The content of the message, including emojis, text, label, coordinates, and author.
    """
    msg['message_id'] = id
    msg['updated'] = False
    msg['created'] = datetime.utcnow()
    msg['last_updated'] = None
    commands.db.messages.insert_one(msg)


def update_message_emojis(id: int, emojis: list[str]) -> None:
    """
    Update the reactions for a message with the given ID.

    Args:
        id (int): The ID of the message to update.
        emojis (list[str]): A list of emojis to set for the message.
    """
    commands.db.messages.update_one({'message_id': id}, {'$set': {
        'emojis': emojis,
        'updated': True,
        'last_updated': datetime.utcnow(),
    }})


class DiscordClient(discord.Client):
    """
    A Discord client that listens for messages and reacts to them.
    It handles commands, updates player status, and manages point of interest markers.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the Discord client with the given arguments and keyword arguments.
        It sets up the database connection and prepares the client for use.
        """
        super().__init__(*args, **kwargs)
        self.activity = None

    async def on_ready(self):
        """
        Called when the client is ready and connected to Discord.
        It initializes the bot, sets the status message, and starts repeating tasks.
        """

        print('Logged in as ', self.user)
        self.sync_status_message.start()

        self.activity = None

        # Set up all tasks to start repeating
        for cmd in commands.all().values():
            for task in cmd.repeat_tasks:
                tasks.loop(seconds=task[1])(lambda fn=task[0]: fn(cmd)).start()

    def set_markers(self, updated) -> None:
        """
        Update the custom markers for the Minecraft map based on the provided updates.
        This function generates JavaScript files for each dimension that has markers,
        removing the '_id' and 'dimension' fields from each marker.

        Args:
            updated (dict): A dictionary indicating which dimensions have updated markers.
                Keys are dimension names ('overworld', 'nether', 'end') and values are booleans
                indicating whether there were updates for that dimension.
        """

        # If marker updates involved any change, update only the respective files
        for dimension in [key for key, val in updated.items() if val]:
            def process(marker: dict) -> dict:
                del marker['_id']
                del marker['dimension']
                return marker

            text = 'UnminedCustomMarkers = { isEnabled: true, markers: ' + json.dumps([
                process(i) for i in commands.db.markers.find({'dimension': dimension})
            ], indent=2) + '}'

            with open(
                f'/var/www/html/maps/{dimension}/custom.markers.js',
                'w', encoding='utf8'
            ) as f:
                f.write(text)

            print(f'Updated {dimension} map.', flush=True)

    @tasks.loop(seconds=15)
    async def sync_status_message(self) -> None:
        """
        A task that runs every 15 seconds to update the bot's status and markers.
        It checks the Minecraft server status, updates the Discord bot's presence,
        and updates any markers based on messages in the database.
        """

        # Update discord bot status to reflect whether players are online
        status = MINECRAFT.status()
        count = status.players.online

        if count == 0:
            status = discord.Status.idle
            activity = 'an empty server'
        else:
            status = discord.Status.online
            activity = str(count) + ' player' + ('' if count == 1 else 's')

        if self.activity != activity:
            act = discord.Activity(
                name=activity, type=discord.ActivityType.watching)
            await self.change_presence(status=status, activity=act)

        # Fetch any updated messages and convert them into markers
        updated = {
            'overworld': False,
            'nether': False,
            'end': False,
        }

        for message in commands.db.messages.find({'updated': True}):
            x_coord = message['coords'][0]
            z_coord = message['coords'][1] if len(message['coords']) == 2 else message['coords'][2]
            label = message['label']

            print(f'Updating marker for {label} at {x_coord}, {z_coord}', flush=True)

            # Remove any marker on the specified position, in any dimension.
            for i in commands.db.markers.find({'x': x_coord, 'z': z_coord}):
                updated[i['dimension']] = True
            commands.db.markers.delete_many({'x': x_coord, 'z': z_coord})

            # Place the new marker
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
                commands.db.markers.insert_one(marker)
                updated[dimension] = True

            commands.db.messages.update_one({'_id': message['_id']}, {'$set': {'updated': False}})

        # If marker updates involved any change, update only the respective files
        self.set_markers(updated)

    async def detect_point_of_interest(self, message: discord.Message) -> None:
        """
        Detect if a message contains coordinates and create a point of interest marker.
        If the message contains two consecutive integers, it is assumed to be coordinates.
        If so, it creates a marker in the database and adds reactions for the dimensions.

        Args:
            message (discord.Message): The Discord message to check for coordinates.
        """

        if not message.guild:
            return  # Ignore DMs

        pattern = re.compile(r'(-?\b([0-9]+)([, ]+|$)){2,}')
        match = pattern.search(message.content)

        if match:
            begin, end = match.span(0)
            pre = message.content[0:begin]
            mid = message.content[begin:end]
            post = message.content[end::]

            text = f'{pre} {post}'.replace(
                ',', '').replace(':', '').strip().upper()
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
                        except (HTTPException, Forbidden, NotFound, TypeError) as e:
                            print(f'Failed to react with custom emoji: {e}', flush=True)
                        break

    async def on_message(self, message: discord.Message):
        """
        Called when a message is sent in a channel the bot can see.
        It processes the message to check for commands, coordinates, and responds accordingly.

        Args:
            message (discord.Message): The message that was sent.
        """

        # Don't respond to ourselves
        if message.author == self.user:
            return

        if not self.user:
            print('Discord client is not logged in. Exiting...')
            return

        # Only respond to commands & messages if this is a DM, or it's in the games channel
        valid_channels = ('games', 'The Abyss')
        if (
            not isinstance(message.channel, discord.channel.DMChannel) and (
                isinstance(message.channel, discord.PartialMessageable) or
                message.channel.name not in valid_channels
            )
        ):
            return

        # If someone sent a command, handle that
        this_command = None
        msg = None
        if f'<@{self.user.id}>' in message.content:
            msg = message.content.replace(f'<@{self.user.id}>', '')
            this_command = [i for i in msg.strip().split(' ') if len(i)]
            if len(this_command) == 0:
                this_command = ['!help']
        else:
            this_command = [
                i for i in message.content.strip().split(' ') if len(i)]

        if len(this_command) == 0:
            return

        if this_command[0][0] not in ['!', '/']:
            if isinstance(message.channel, discord.channel.DMChannel):
                # if this is a non-command DM, send message to the flat earth.
                this_command.insert(0, '!say')
            else:
                # If this is a non-command in the games channel, check if it looks like coordinates
                await self.detect_point_of_interest(message)
                return  # Don't follow through with any command

        # Now commands are all uniform,
        # Remove command indicator from first param
        this_command[0] = this_command[0][1::]

        if cmd := commands.get(this_command[0]):

            response = await cmd.call(message, this_command[1::])
            emoji = None
            if isinstance(response, tuple):
                emoji, response = response[1], response[0]

            if response:
                await message.channel.send(response)
            if emoji:
                await message.add_reaction(emoji)
        else:
            await message.channel.send(commands.bad_cmd())

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Called when a reaction is added to a message.
        It checks if the reaction is one of the custom emojis for dimensions,
        and updates the message accordingly.

        Args:
            payload (discord.RawReactionActionEvent):
                The payload containing information about the reaction.
        """

        if not self.user:
            print('Discord client is not logged in. Exiting...')
            return

        if payload.emoji.name not in ['overworld', 'nether', 'end']:
            return

        # Ignore reactions from this bot
        if payload.user_id == self.user.id:
            return

        msg = read_message(payload.message_id)
        if msg is None:
            return

        # Ignore users reacting to someone else's message
        if msg['author'] != payload.user_id:
            return

        if payload.emoji.name not in msg['emojis']:
            msg['emojis'] += [payload.emoji.name]

        update_message_emojis(payload.message_id, msg['emojis'])

        # Remove automatic reactions
        channel = await self.fetch_channel(payload.channel_id)

        message = await channel.fetch_message(payload.message_id)  # type: ignore
        if not message.guild:
            return

        for i in ['overworld', 'nether', 'end']:
            for emoji in message.guild.emojis:
                if emoji.name == i:
                    try:
                        await message.remove_reaction(emoji, self.user)
                    except (HTTPException, Forbidden, NotFound, TypeError) as e:
                        print(f'Failed to react with custom emoji: {e}', flush=True)
                    break

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Called when a reaction is removed from a message.
        It checks if the reaction is one of the custom emojis for dimensions,
        and updates the message accordingly.

        Args:
            payload (discord.RawReactionActionEvent):
                The payload containing information about the reaction.
        """

        if not self.user:
            print('Discord client is not logged in. Exiting...')
            return

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
