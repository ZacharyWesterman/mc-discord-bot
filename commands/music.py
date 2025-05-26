from commands import *
import subsonic

import json
from pathlib import Path
import discord

with open(str(Path(__file__).parent.parent) + '/secrets.json', 'r') as fp:
    data = json.load(fp)
    SUBSONIC = subsonic.SubsonicClient(
        host=data['subsonic']['url'],
        username=data['subsonic']['username'],
        password=data['subsonic']['password'],
        client='discord'
    )


FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
PLAYER = None
PLAYER_CHANNEL = None
PAUSED = False
QUEUE = []


@command('play', 'Play a song from the music server (only works in The Abyss).', 'music')
class MusicCmd(Command):
    async def default(self, message: Message, command: list[str]) -> str:
        global PLAYER
        global PLAYER_CHANNEL
        global QUEUE
        global PAUSED

        if message.author.voice is None:
            return 'This command only works in The Abyss.'

        query = ' '.join([i for i in command if i[0] not in ['@', '-']])
        artist = ' '.join([i[1::] for i in command if i[0] == '@'])
        negate = [i[1::] for i in command if i[0] == '-']

        if len(query) == 0:
            if len(QUEUE):
                # Just continue to the next song in the queue.
                PAUSED = False
                return

            return 'Please input a search term, or use `!play help` for usage info.'

        if not PLAYER_CHANNEL:
            PLAYER_CHANNEL = message.author.voice.channel

        results = SUBSONIC.search(' '.join(command))
        song = None
        for i in results.songs:
            if any([k.lower() in i.title.lower() for k in negate]):
                continue

            if artist == '' or artist.lower() in i.artist.lower():
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
        PAUSED = False

        return f"Added **{song.title}** by *{song.artist}* to the queue." if len(QUEUE) and QUEUE[0]['playing'] else None

    @subcommand
    async def album(self, message: Message, command: list[str]) -> str:
        global PLAYER
        global PLAYER_CHANNEL
        global QUEUE
        global PAUSED

        if message.author.voice is None:
            return 'This command only works in The Abyss.'

        query = ' '.join([i for i in command if i[0] not in ['@', '-']])
        artist = ' '.join([i[1::] for i in command if i[0] == '@'])
        negate = [i[1::] for i in command if i[0] == '-']

        if len(query) == 0:
            if len(QUEUE):
                # Just continue to the next song in the queue.
                PAUSED = False
                return

            return 'Please input a search term, or use `!play help` for usage info.'

        if not PLAYER_CHANNEL:
            PLAYER_CHANNEL = message.author.voice.channel

        results = SUBSONIC.search(' '.join(command))
        album = None
        for i in results.albums:
            if any([k.lower() in i.title.lower() for k in negate]):
                continue

            if artist == '' or artist.lower() in i.artist.lower():
                album = i
                break

        if album is None:
            return 'Album not found.'

        await PLAYER_CHANNEL.send(f"Adding album **{album.title}** by *{album.artist}* ({len(album.songs)} songs) to the queue.")

        for song in album.songs:
            QUEUE += [{
                'url': song.uri,
                'title': song.title,
                'artist': song.artist,
                'playing': False,
            }]

        PAUSED = False

    @subcommand
    def help(self, message: Message, command: list[str]) -> str:
        return '\n'.join([
            'Search the music server for a song and play the first result, or add to the queue if a song is already playing.',
            'You can put @ in front of a word to indicate the artist name, e.g.:',
            '`!play billie jean @jackson`',
            'You can also put - in front of a word to exclude it from the search, e.g.:',
            '`!play the best it\'s gonna get -instrumental`',
            '----',
            '`!play next` skips to the next song in the queue.',
            '`!play album {album name}` adds an entire album to the queue.',
        ])

    @subcommand
    def next(self, message: Message, command: list[str]) -> str:
        PLAYER.stop()
        return None

    @repeat(seconds=1)
    async def check_queue():
        global PLAYER
        global QUEUE

        if not PLAYER_CHANNEL:
            return

        if PLAYER and PLAYER.is_playing():
            return

        if PAUSED:
            return

        # If not playing audio, continue to next song

        # First exit the channel
        if PLAYER:
            PLAYER.stop()
            # if not PLAYER.is_connected():
            await PLAYER.disconnect()
            PLAYER = None

        # Remove any finished song from the queue
        if len(QUEUE) and QUEUE[0]['playing']:
            QUEUE.pop(0)

        # Connect to the channel and play what's next in the queue
        if len(QUEUE) == 0:
            return

        try:
            PLAYER = await PLAYER_CHANNEL.connect()
        except Exception as e:
            print(f'ERROR: {e}', flush=True)
            return

        item = QUEUE[0]
        item['playing'] = True
        await PLAYER_CHANNEL.send(f'Playing **{item["title"]}** by *{item["artist"]}*')

        PLAYER.play(discord.FFmpegPCMAudio(item['url'], **FFMPEG_OPTIONS))
        PLAYER.source = discord.PCMVolumeTransformer(PLAYER.source, volume=0.25)


@command('stop', 'Stop any music that\'s currently playing.', 'music')
class MusicCmd(Command):
    async def default(self, message: Message, command: list[str]) -> str:
        global PLAYER
        global PAUSED
        global QUEUE

        PAUSED = True
        if len(QUEUE) and QUEUE[0]['playing']:
            QUEUE.pop(0)

        if PLAYER:
            PLAYER.stop()
            try:
                await PLAYER.disconnect()
            except Exception as e:
                return f'ERROR: {e}'
            PLAYER = None


@command('queue', 'List all songs in the music queue.', 'music')
class MusicCmd(Command):
    async def default(self, message: Message, command: list[str]) -> str:
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

        maxprint = offset+20
        for i in range(offset, min(offset+maxprint, len(QUEUE))):
            msg += [f'{i-offset+1}. **{QUEUE[i]["title"]}** by *{QUEUE[i]["artist"]}*']

        if maxprint < len(QUEUE):
            msg += [f'\n(and {len(QUEUE)-maxprint} more.)']

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
    async def help(self, message: Message, command: list[str]) -> str:
        return '\n'.join([
            'View and edit the music queue.',
            '`!queue` lists all songs in the queue and what\'s playing, if anything.',
            '`!queue clear` removes all songs from the queue, except what\'s currently playing.',
        ])

    @subcommand
    async def clear(self, message: Message, command: list[str]) -> str:
        global QUEUE
        if len(QUEUE):
            QUEUE = [i for i in QUEUE if i['playing']]

        return 'All songs have been removed from the queue.'
