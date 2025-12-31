"""
Music commands for the Discord bot, using Subsonic as the music server.

This module allows users to play music from a Subsonic server, manage a queue,
and control playback within a Discord voice channel.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import discord
from discord import Message

import subsonic
from commands import Command, command, repeat, subcommand

with open(str(Path(__file__).parent.parent) + '/secrets.json', 'r', encoding='utf8') as fp:
    data = json.load(fp)
    SUBSONIC = subsonic.SubsonicClient(
        host=data['subsonic']['url'],
        username=data['subsonic']['username'],
        password=data['subsonic']['password'],
        client='discord'
    )


FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


class Player:
    def __init__(self, channel: discord.channel.VocalGuildChannel):
        self.client: discord.VoiceClient | None = None
        self.channel = channel
        self.name = channel.name
        self.queue: list[dict[str, Any]] = []
        self.stopped = True

    def add_song(self, url: str, title: str, artist: str | None) -> None:
        self.queue += [{
            'url': url,
            'title': title,
            'artist': artist,
            'playing': False,
        }]

    async def require_client(self) -> discord.VoiceClient | None:
        if not self.client or not self.client.is_connected():
            for player in PLAYERS.values():
                if player.client and player.client.is_connected():
                    await self.channel.send('**ERROR**: Already connected to a voice channel.')
                    return

            try:
                self.client = await self.channel.connect(self_deaf=True)
            except (asyncio.TimeoutError, discord.ClientException, discord.opus.OpusNotLoaded) as e:
                print(f'ERROR: {e}', flush=True)
                await self.channel.send(f'**ERROR**: {e}')
                return None

        return self.client

    async def play_next_song(self) -> None:
        # If the current song was in progress but no longer is,
        # Remove it and play the next one
        if len(self.queue) > 0 and self.queue[0]['playing'] == True:
            self.queue.pop(0)

        if len(self.queue) == 0:
            return

        if not (client := await self.require_client()):
            return

        item = self.queue[0]
        item['playing'] = True

        client.stop()

        client.play(discord.FFmpegPCMAudio(item['url'], **FFMPEG_OPTIONS))  # type: ignore
        if client.source is not None:
            client.source = discord.PCMVolumeTransformer(client.source, volume=0.25)

        await self.channel.send(f'Playing **{item["title"]}** by *{item["artist"]}*')

    async def play(self) -> None:
        if self.is_paused():
            if not (client := await self.require_client()):
                return
            client.resume()
        if not self.is_playing():
            await self.play_next_song()

    def is_playing(self) -> bool:
        if self.client:
            return self.client.is_playing()
        return False

    async def pause(self) -> None:
        if not self.client:
            return

        self.client.pause()

    def is_paused(self) -> bool:
        if self.client:
            return self.client.is_paused()
        return False

    async def next(self) -> None:
        await self.play_next_song()

    async def stop(self) -> None:
        if self.is_paused() or self.is_playing():
            # Remove the current song from the queue.
            if len(self.queue) > 0:
                self.queue.pop(0)

        # Stop the player and disconnect
        if self.client:
            self.client.stop()
            await self.client.disconnect()
            self.client = None

    def is_stopped(self) -> bool:
        return self.client is not None


PLAYERS: dict[str, Player] = {}


def get_player(channel: discord.channel.VocalGuildChannel) -> Player:
    if channel.name not in PLAYERS:
        PLAYERS[channel.name] = Player(channel)
    return PLAYERS[channel.name]


def get_channel(message: Message) -> tuple[discord.VoiceChannel | None, str | None]:
    if (
        isinstance(message.author, discord.User) or
        message.author.voice is None or
        message.author.voice.channel is None
    ):
        return None, 'This command only works in voice channels.'

    channel: discord.VoiceChannel = message.author.voice.channel  # type: ignore
    return channel, None


@command('play', 'Play a song from the music server (only works in voice channels).', 'music')
class MusicCmdPlay(Command):
    """
    Command to play music from a Subsonic server in a Discord voice channel.
    This command allows users to search for songs, albums, and manage a queue.
    """

    async def default(self, message: Message, cmd: list[str]) -> str | None:
        channel, msg = get_channel(message)
        if channel is None:
            return msg

        query = ' '.join([i for i in cmd if i[0] not in ['@', '-']])
        artist = ' '.join([i[1::] for i in cmd if i[0] == '@'])
        negate = [i[1::] for i in cmd if i[0] == '-']

        if len(query) == 0:
            if channel.name not in PLAYERS:
                return 'No music is currently playing in this channel. See `!play help` for usage info.'

            player = get_player(channel)
            if len(player.queue) == 0:
                return 'No songs are in the queue. To add a song, append some search terms to your command, or use `!play help` for usage info.'

            await player.play()
            return

        results = SUBSONIC.search(' '.join(cmd))
        song = None
        for i in results.songs:
            if any(k.lower() in i.title.lower() for k in negate):
                continue

            if artist == '' or (i.artist is not None and artist.lower() in i.artist.lower()):
                song = i
                break

        if song is None:
            return 'Song not found.'

        player = get_player(channel)
        player.add_song(song.uri, song.title, song.artist)
        await player.play()

        if len(player.queue) == 1:
            return

        return f"Added **{song.title}** by *{song.artist}* to the queue."

    @subcommand
    async def album(self, message: Message, cmd: list[str]) -> str | None:
        """
        Add an entire album to the music queue.
        This command searches for an album by name and adds all its songs to the queue.

        Args:
            message (Message): The Discord message that triggered the command.
            cmd (list[str]): The command arguments, where the first element is the command name.

        Returns:
            str | None: A message indicating the result of the operation, or None if successful.
        """

        channel, msg = get_channel(message)
        if channel is None:
            return msg

        query = ' '.join([i for i in cmd if i[0] not in ['@', '-']])
        artist = ' '.join([i[1::] for i in cmd if i[0] == '@'])
        negate = [i[1::] for i in cmd if i[0] == '-']

        if len(query) == 0:
            if channel.name not in PLAYERS:
                return 'No music is currently playing in this channel. See `!play help` for usage info.'

            player = get_player(channel)
            if len(player.queue) == 0:
                return 'No songs are in the queue. To add a song, append some search terms to your command, or use `!play help` for usage info.'

            await player.play()
            return

        results = SUBSONIC.search(' '.join(cmd))
        album = None
        for i in results.albums:
            if any([k.lower() in i.title.lower() for k in negate]):
                continue

            if artist == '' or (i.artist is not None and artist.lower() in i.artist.lower()):
                album = i
                break

        if album is None:
            return 'Album not found.'

        await channel.send(
            f"Adding album **{album.title}** by *{album.artist}* " +
            f"({len(album.songs)} songs) to the queue."
        )

        player = get_player(channel)
        for song in album.songs:
            player.add_song(song.uri, song.title, song.artist)

        await player.play()

    @subcommand
    async def help(self, message: Message, cmd: list[str]) -> str | None:
        """
        Display help information for the play command.
        This method provides usage instructions for the play command, including
        how to search for songs, specify artists, and manage the queue.

        Args:
            message (Message): The Discord message that triggered the command.
            cmd (list[str]): The command arguments, where the first element is the command name.

        Returns:
            str | None: A string containing the help information for the play command.
        """

        return '\n'.join([
            (
                'Search the music server for a song and play the first result, ' +
                'or add to the queue if a song is already playing.'
            ),
            'You can put @ in front of a word to indicate the artist name, e.g.:',
            '`!play billie jean @jackson`',
            'You can also put - in front of a word to exclude it from the search, e.g.:',
            '`!play the best it\'s gonna get -instrumental`',
            '----',
            '`!play next` skips to the next song in the queue.',
            '`!play album {album name}` adds an entire album to the queue.',
        ])

    @subcommand
    async def next(self, message: Message, cmd: list[str]) -> str | None:
        """
        Skip to the next song in the queue.
        This method stops the current song and plays the next song in the queue,
        if available. It also disconnects from the voice channel if no songs are left.

        Args:
            message (Message): The Discord message that triggered the command.
            cmd (list[str]): The command arguments, where the first element is the command name.

        Returns:
            str | None: A message indicating the result of the operation, or None if successful.
        """

        channel, msg = get_channel(message)
        if channel is None:
            return msg

        player = get_player(channel)
        await player.next()

    @repeat(seconds=1)
    async def check_queue(self) -> None:
        """
        Check the music queue and play the next song if necessary.
        This method is called periodically to ensure that the music player
        is playing the next song in the queue if no song is currently playing.
        """

        # Continue in the currently connected channel, if any
        for player in PLAYERS.values():
            if not player.client:
                continue

            if not player.client.is_connected():
                await player.play()
                await player.pause()
                continue

            if player.is_paused() or player.is_stopped():
                continue

            await player.play()

        # Otherwise, pick the first channel
        # for player in PLAYERS.values():
        #     await player.play()
        #     break


@command('pause', 'Stop any music that\'s currently playing.', 'music')
class MusicCmdPause(Command):
    """
    Command to pause the music player and disconnect from the voice channel.
    This command stops any currently playing music, but does not remove the
    current song from the queue.
    Any songs in the queue will remain, but playback will be paused.
    """

    async def default(self, message: Message, cmd: list[str]) -> str | None:
        channel, msg = get_channel(message)
        if channel is None:
            return msg

        player = get_player(channel)
        await player.pause()


@command('stop', 'Stop any music that\'s currently playing.', 'music')
class MusicCmdStop(Command):
    """
    Command to stop the music player and disconnect from the voice channel.
    This command stops any currently playing music, removes the current song from the queue,
    and disconnects the bot from the voice channel.
    Any songs in the queue will remain, but playback will be paused.
    """

    async def default(self, message: Message, cmd: list[str]) -> str | None:
        channel, msg = get_channel(message)
        if channel is None:
            return msg

        player = get_player(channel)
        await player.stop()


@command('queue', 'List all songs in the music queue.', 'music')
class MusicCmdQueue(Command):
    """
    Command to manage the music queue.
    This command allows users to view the current music queue, see what song is currently playing,
    and clear the queue if necessary.
    """

    async def default(self, message: Message, cmd: list[str]) -> str | None:
        channel, msg = get_channel(message)
        if channel is None:
            return msg

        player = get_player(channel)

        if len(player.queue) == 0:
            return 'There are no songs in the queue.'

        offset = 0
        msg = []
        if player.queue[0]['playing']:
            offset = 1
            msg += [
                'Currently Playing:',
                f'- **{player.queue[0]["title"]}** by *{player.queue[0]["artist"]}*',
            ]

        if len(player.queue) > offset:
            msg += ['Up Next:']

        maxprint = offset + 2
        for i in range(offset, min(offset + maxprint, len(player.queue))):
            msg += [f'{i - offset + 1}. **{player.queue[i]["title"]}** by *{player.queue[i]["artist"]}*']

        if maxprint < len(player.queue):
            msg += [f'\n(and {len(player.queue) - maxprint} more.)']

        # Split up big responses into multiple messages
        text = msg.pop(0)
        for i in msg:
            if len(text + '\n' + i) > 2000:
                await message.channel.send(text)
                text = i
            else:
                text += '\n' + i

        return text

    @subcommand
    async def help(self, message: Message, cmd: list[str]) -> str:
        """
        Display help information for the queue command.
        This method provides usage instructions for the queue command, including
        how to view the queue and clear it.

        Args:
            message (Message): The Discord message that triggered the command.
            cmd (list[str]): The command arguments, where the first element is the command name.

        Returns:
            str: A string containing the help information for the queue command.
        """

        return '\n'.join([
            'View and edit the music queue.',
            '`!queue` lists all songs in the queue and what\'s playing, if anything.',
            '`!queue clear` removes all songs from the queue, except what\'s currently playing.',
        ])

    @subcommand
    async def clear(self, message: Message, cmd: list[str]) -> str | None:
        """
        Clear the music queue.
        This method removes all songs from the queue, except for the currently playing song.

        Args:
            message (Message): The Discord message that triggered the command.
            cmd (list[str]): The command arguments, where the first element is the command name.

        Returns:
            str: A message indicating that the queue has been cleared.
        """

        channel, msg = get_channel(message)
        if channel is None:
            return msg

        player = get_player(channel)
        player.queue = [i for i in player.queue if i['playing']]

        return 'Any upcoming songs have been removed from the queue.'
