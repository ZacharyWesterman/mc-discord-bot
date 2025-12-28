"""
Music commands for the Discord bot, using Subsonic as the music server.

This module allows users to play music from a Subsonic server, manage a queue,
and control playback within a Discord voice channel.
"""

import asyncio
import json
from pathlib import Path

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
PLAYER: discord.VoiceClient | None = None
PLAYER_CHANNEL: discord.channel.VocalGuildChannel | None = None
PAUSED = False
QUEUE = []


@command('play', 'Play a song from the music server (only works in voice channels).', 'music')
class MusicCmdPlay(Command):
    """
    Command to play music from a Subsonic server in a Discord voice channel.
    This command allows users to search for songs, albums, and manage a queue.
    """

    async def default(self, message: Message, cmd: list[str]) -> str | None:
        global PLAYER_CHANNEL
        global QUEUE
        global PAUSED
        global PLAYER

        if isinstance(message.author, discord.User) or message.author.voice is None:
            return 'This command only works in voice channels.'

        query = ' '.join([i for i in cmd if i[0] not in ['@', '-']])
        artist = ' '.join([i[1::] for i in cmd if i[0] == '@'])
        negate = [i[1::] for i in cmd if i[0] == '-']

        if len(query) == 0:
            if len(QUEUE) > 0:
                if PLAYER and PLAYER.is_paused():
                    PLAYER.resume()
                # Just continue to the next song in the queue.
                PAUSED = False
                return

            return 'Please input a search term, or use `!play help` for usage info.'

        if not PLAYER_CHANNEL:
            if PLAYER:
                if PLAYER.is_connected():
                    await PLAYER.disconnect()
                PLAYER = None
            PLAYER_CHANNEL = message.author.voice.channel

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

        QUEUE += [{
            'url': song.uri,
            'title': song.title,
            'artist': song.artist,
            'playing': False,
        }]
        if not PLAYER or not PLAYER.is_paused():
            PAUSED = False

        return (
            f"Added **{song.title}** by *{song.artist}* to the queue."
            if len(QUEUE) > 0 and QUEUE[0]['playing']
            else None
        )

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

        global PLAYER_CHANNEL
        global QUEUE
        global PAUSED

        if isinstance(message.author, discord.User) or message.author.voice is None:
            return 'This command only works in The Abyss.'

        query = ' '.join([i for i in cmd if i[0] not in ['@', '-']])
        artist = ' '.join([i[1::] for i in cmd if i[0] == '@'])
        negate = [i[1::] for i in cmd if i[0] == '-']

        if len(query) == 0:
            if len(QUEUE) > 0:
                # Just continue to the next song in the queue.
                PAUSED = False
                return

            return 'Please input a search term, or use `!play help` for usage info.'

        if not PLAYER_CHANNEL:
            PLAYER_CHANNEL = message.author.voice.channel

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

        if PLAYER_CHANNEL:
            await PLAYER_CHANNEL.send(
                f"Adding album **{album.title}** by *{album.artist}* " +
                f"({len(album.songs)} songs) to the queue."
            )

        for song in album.songs:
            QUEUE += [{
                'url': song.uri,
                'title': song.title,
                'artist': song.artist,
                'playing': False,
            }]

        if not PLAYER or not PLAYER.is_paused():
            PAUSED = False

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

        global PAUSED

        if PLAYER:
            PLAYER.stop()
            PAUSED = False

    @repeat(seconds=1)
    async def check_queue(self) -> None:
        """
        Check the music queue and play the next song if necessary.
        This method is called periodically to ensure that the music player
        is playing the next song in the queue if no song is currently playing.
        """

        global PLAYER

        if not PLAYER_CHANNEL:
            return

        if PLAYER and not PLAYER.is_connected():
            await PLAYER.disconnect()
            PLAYER = await PLAYER_CHANNEL.connect(self_deaf=True)

        if PLAYER and PLAYER.is_playing():
            return

        if PAUSED:
            return

        # If not playing audio, continue to next song

        # First exit the channel
        if PLAYER:
            PLAYER.stop()

        # Remove any finished song from the queue
        if len(QUEUE) > 0 and QUEUE[0]['playing']:
            QUEUE.pop(0)

        # Connect to the channel and play what's next in the queue
        if len(QUEUE) == 0:
            return

        try:
            if not PLAYER or not PLAYER.is_connected():
                PLAYER = await PLAYER_CHANNEL.connect(self_deaf=True)
        except (asyncio.TimeoutError, discord.ClientException, discord.opus.OpusNotLoaded) as e:
            print(f'ERROR: {e}', flush=True)
            return

        item = QUEUE[0]
        item['playing'] = True
        await PLAYER_CHANNEL.send(f'Playing **{item["title"]}** by *{item["artist"]}*')

        PLAYER.play(discord.FFmpegPCMAudio(item['url'], **FFMPEG_OPTIONS))  # type: ignore
        if PLAYER.source is not None:
            PLAYER.source = discord.PCMVolumeTransformer(PLAYER.source, volume=0.25)


@command('pause', 'Stop any music that\'s currently playing.', 'music')
class MusicCmdPause(Command):
    """
    Command to pause the music player and disconnect from the voice channel.
    This command stops any currently playing music, but does not remove the
    current song from the queue.
    Any songs in the queue will remain, but playback will be paused.
    """

    async def default(self, message: Message, cmd: list[str]) -> str | None:
        global PAUSED

        PAUSED = True

        if PLAYER:
            PLAYER.pause()


@command('stop', 'Stop any music that\'s currently playing.', 'music')
class MusicCmdStop(Command):
    """
    Command to stop the music player and disconnect from the voice channel.
    This command stops any currently playing music, removes the current song from the queue,
    and disconnects the bot from the voice channel.
    Any songs in the queue will remain, but playback will be paused.
    """

    async def default(self, message: Message, cmd: list[str]) -> str | None:
        global PLAYER
        global PAUSED

        PAUSED = True
        if len(QUEUE) > 0 and QUEUE[0]['playing']:
            QUEUE.pop(0)

        if PLAYER:
            PLAYER.stop()
            # pylint: disable=broad-exception-caught
            try:
                await PLAYER.disconnect()
            except Exception as e:
                return f'ERROR: {e}'
            # pylint: enable=broad-exception-caught

            PLAYER = None


@command('queue', 'List all songs in the music queue.', 'music')
class MusicCmdQueue(Command):
    """
    Command to manage the music queue.
    This command allows users to view the current music queue, see what song is currently playing,
    and clear the queue if necessary.
    """

    async def default(self, message: Message, cmd: list[str]) -> str:
        if len(QUEUE) == 0:
            return 'There are no songs in the queue.'

        offset = 0
        msg = []
        if QUEUE[0]['playing']:
            offset = 1
            msg += [
                'Currently Playing:',
                f'- **{QUEUE[0]["title"]}** by *{QUEUE[0]["artist"]}*',
            ]

        if len(QUEUE) > offset:
            msg += ['Up Next:']

        maxprint = offset + 2
        for i in range(offset, min(offset + maxprint, len(QUEUE))):
            msg += [f'{i - offset + 1}. **{QUEUE[i]["title"]}** by *{QUEUE[i]["artist"]}*']

        if maxprint < len(QUEUE):
            msg += [f'\n(and {len(QUEUE) - maxprint} more.)']

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
    async def clear(self, message: Message, cmd: list[str]) -> str:
        """
        Clear the music queue.
        This method removes all songs from the queue, except for the currently playing song.

        Args:
            message (Message): The Discord message that triggered the command.
            cmd (list[str]): The command arguments, where the first element is the command name.

        Returns:
            str: A message indicating that the queue has been cleared.
        """

        global QUEUE
        if len(QUEUE) > 0:
            QUEUE = [i for i in QUEUE if i['playing']]

        return 'All songs have been removed from the queue.'
