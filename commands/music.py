from commands import *

import urllib, random, hashlib, requests, json, functools, re
from pathlib import Path
from discord import FFmpegPCMAudio

_P = re.compile(r'[\[\(][^\)]*[\[\)\]]')
SUBSONIC_ALBUMID_CACHESZ = 8196

class SessionError(Exception):
    def __init__(self, message: str):
        super().__init__(f'Subsonic Error: {message}')

class SubsonicSession:
    def __init__(self, host: str, username: str, password: str, *, client: str = 'serverclient', version: str = '1.15.0'):
        salt = ('%32x' % random.randrange(16**32)).strip() #random 32 digit hex string

        # Note that the password you pass in depends on how the credentials are stored on the server side!
        # E.g. if it's stored in plaintext, pass in the plain text password
        # however, if the encoder is MD5, pass in the md5sum to this function, NOT the plaintext password!
        md5sum = hashlib.md5((password + salt).encode('utf-8')).hexdigest()

        self.rest_params = f'u={username}&t={md5sum}&s={salt}&c={client}&v={version}&f=json'
        self.connection_uri = host

    def query(self, action: str, parameters: dict = {}, *, process: bool = True) -> dict:
        url = f'{self.connection_uri}/rest/{action}.view?{self.rest_params}'
        for p in parameters:
            if parameters[p] is not None:
                url += f'&{p}={urllib.parse.quote_plus(str(parameters[p]))}'

        try:
            res = requests.get(url, timeout = 31)
        except requests.exceptions.ConnectionError as e:
            raise SessionError(e)
        except requests.exceptions.Timeout:
            raise SessionError('Connection timed out.')

        if res.status_code >= 300 or res.status_code < 200:
            raise SessionError(f'Failed to connect to server (code {res.status_code})')

        if not process:
            return res.content

        data = json.loads(res.text)
        if data['subsonic-response']['status'] != 'ok':
            raise SessionError(data['subsonic-response']['error']['message'])

        return data['subsonic-response']

    def ping(self) -> dict:
        return self.query('ping')

    @functools.cache
    def search(self, text: str, *, artist_count: int|None = None, artist_offset: int|None = None, album_count: int|None = None, album_offset: int|None = None, song_count: int|None = None, song_offset: int|None = None, music_folder_id: int|None = None) -> list:
        data = self.query('search2', {
            'query': text,
            'artistCount': artist_count,
            'artistOffset': artist_offset,
            'albumCount': album_count,
            'albumOffset': album_offset,
            'songCount': song_count,
            'songOffset': song_offset,
            'musicFolderId': music_folder_id,
        })
        return data['searchResult2']


    @functools.cached_property
    def folders(self) -> dict:
        data = self.query('getMusicFolders')

        output = {}
        for i in data['musicFolders']['musicFolder']:
            output[i['name']] = i['id']

        return output

    @functools.cached_property
    def license(self) -> str:
        return self.query('getLicense').get('license')

    @functools.cached_property
    def playlists(self) -> list:
        return self.query('getPlaylists').get('playlists', [])

    @functools.cache
    def playlist(self, name: str) -> dict:
        return self.query('getPlaylist').get('playlist')

    @functools.cache
    def albums(self, folder: str, page: int = 0) -> list:
        size = 100

        folder_id = self.folders.get(folder)
        if folder_id is None:
            raise SessionError(f'Folder "{folder}" does not exist')

        return self.query('getAlbumList', {
            'type': 'alphabeticalByName',
            'size': size,
            'offset': page * size,
            'musicFolderId': folder_id,
        }).get('albumList')

    @functools.cache
    def all_albums(self, folder: str) -> list[str]:
        global _P
        result = {}
        page = 0

        while True:
            res = self.albums(folder, page).get('album')
            if res is None:
                break

            for i in res:
                result[_P.sub('', i['title']).strip().lower()] = i['id']
            page += 1

        return result

    @functools.lru_cache(maxsize = SUBSONIC_ALBUMID_CACHESZ)
    def get_album_id(self, album: str, folder: str) -> str:
        global _P

        all_albums = self.all_albums(folder)
        album = _P.sub('', album).strip().lower()

        for i in all_albums:
            if i.startswith(album) or album.startswith(i):
                return all_albums[i]

        return None
    
    def get_song_url(self, id: str) -> str:
        return f'{self.connection_uri}/rest/stream?id={id}&{self.rest_params}'


with open(str(Path(__file__).parent.parent) + '/secrets.json', 'r') as fp:
    data = json.load(fp)
    SUBSONIC = SubsonicSession(
        host = data['subsonic']['url'],
        username = data['subsonic']['username'],
        password = data['subsonic']['password'],
        client = 'discord'
    )


FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn'}
PLAYER = None

@command('play', 'Play a song from the music server (only works in The Abyss).')
class MusicCmd(Command):
    async def default(self, message: Message, command: list[str]) -> str:
        global PLAYER
        if PLAYER:
            PLAYER.stop()
            if not PLAYER.is_connected():
                PLAYER.disconnect()
                PLAYER = None

        if message.author.voice is None:
            return 'This command only works in The Abyss.'
        
        query = ' '.join([i for i in command if i[0] not in ['@', '-']])
        artist = ' '.join([i[1::] for i in command if i[0] == '@'])
        negate = [i[1::] for i in command if i[0] == '-']

        if len(query) == 0:
            return 'Please input a search term, or use `!play help` for usage info.'

        if not PLAYER:
            channel = message.author.voice.channel
            try:
                PLAYER = await channel.connect()
            except Exception as e:
                return f'ERROR: {e}'

        results = SUBSONIC.search(' '.join(command))
        song = None
        for i in results.get('song', []):
            if any([k.lower() in i.get('title', '').lower() for k in negate]):
                continue

            if artist == '' or artist.lower() in i.get('artist', '').lower():
                song = i
                break

        if song is None:
            return 'Song not found.'

        url = SUBSONIC.get_song_url(song['id'])

        PLAYER.play(FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
        return f"Playing **{song['title']}** by {song['artist']}."
    
    @subcommand
    def help(self, message: Message, command: list[str]) -> str:
        return '\n'.join([
            'Search the music server for a song and play the first result.',
            'You can put @ in front of a word to indicate the artist name, e.g.:',
            '`!play billie jean @jackson`',
            'You can also put - in front of a word to exclude it from the search, e.g.:',
            '`!play the best it\'s gonna get -instrumental`',
        ])

@command('stop', 'Stop any music that\'s currently playing.')
class MusicCmd(Command):
    async def default(self, message: Message, command: list[str]) -> str:
        global PLAYER
        if PLAYER:
            PLAYER.stop()
            try:
                await PLAYER.disconnect()
            except Exception as e:
                return f'ERROR: {e}'
            PLAYER = None

