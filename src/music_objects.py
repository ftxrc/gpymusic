import consts
from os.path import expanduser, isfile, join
from subprocess import call


class MusicObject(dict):
    """A dict representing a song, artist, or album."""

    def __init__(self, id, name, kind, full):
        """
        Assign to fields common to Songs, Artists, and Albums.

        Arguments:
        id: Unique item id as determined by gmusicapi.
        name: Title of song/album or name of artist.
        kind: Type of object: song, artist, or album.
        full: Whether or not the item contains all possible information.
          All Songs are full, but in general only Artists and Albums
          generated from get_{artist|album}_info}() are full.
        """
        self['id'] = id
        self['name'] = name
        self['kind'] = kind
        self['full'] = full

    @staticmethod
    def play(songs):
        """
        Play some songs.

        Arguments:
        songs: List of songs to play.

        Returns: None if all songs were played, or the index of the
          first unplayed song to be used in restoring the queue.
        """
        conf_path = join(expanduser('~'), '.config', 'pmcli', 'mpv_input.conf')
        if not isfile(conf_path):
            consts.w.goodbye('No mpv_input.conf found.')
        i = 1

        for song in songs:
            url = consts.mc.get_stream_url(song['id'])
            consts.w.now_playing('(%d/%d) %s (%s)' %
                                 (i, len(songs), str(song), song['time']))

            if call(
                    ['mpv', '--really-quiet', '--input-conf', conf_path, url]
            ) == 11:  # 'q' returns this exit code.
                return i if i < len(songs) else None
            i += 1

        return None

    def __hash__(self):
        """Use ID to hash. This doesn't need to be strong."""
        return ''.join(str(ord(c)) for c in self['id'])


class Artist(MusicObject):
    """A dict representing an artist."""

    def __init__(self, artist, full=False, source='api'):
        """
        # Create a new Artist.

        Arguments:
        artist: Dict with artist information from gmusicapi.

        Keyword arguments:
        full=False: Whether or not the artist's song list is populated.
        source='api': The source of the argument dict, which changes how
          we initialize the artist.
        """
        if source == 'api':
            super().__init__(artist['artistId'], artist['name'], 'artist', full)  # noqa
            try:
                self['songs'] = [Song(s) for s in artist['topTracks']]
            except KeyError:
                self['songs'] = []
            try:
                self['albums'] = [Album(a) for a in artist['albums']]
            except KeyError:
                self['albums'] = []

        elif source == 'json':
            super().__init__(artist['id'], artist['name'], 'artist', full)
            self['songs'] = [Song(song, source='json')
                             for song in artist['songs']]
            self['albums'] = [Album(album, source='json')
                              for album in artist['albums']]

    @staticmethod
    def verify(item):
        """
        Make sure a dict contains all necessary artist data.

        Arguments:
        item: The dict being checked.

        Returns: Whether or not the item contains sufficient data.
        """
        return all(k in item for k in
                   ('id', 'name', 'kind', 'full', 'songs', 'albums'))

    def __str__(self):
        """
        Format an artist into a string.

        Returns: The artist name.
        """
        return self['name']

    def play(self):
        """Play an artist's song list."""
        if not self['full']:
            self.fill(consts.mapping['artists']['lookup'])
        MusicObject.play(self['songs'])

    def collect(self, limit=20):
        """
        Collect all of an artist's information: songs, artist, and albums.

        Keyword arguments:
        limit=20: Upper limit of each element to collect,
          determined by terminal height.

        Returns: A dict of lists with keys 'songs, 'artists', and 'albums'.
        """
        return {
            'songs': self['songs'][:min(len(self['songs']), limit)],
            'artists': [self],
            'albums': self['albums'][:min(len(self['albums']), limit)]
        }

    def fill(self, func, limit=100):
        """
        If an artist is not full, fill in its song list.

        Arguments:
        func: Function to get data from the api.

        Keyword arguments:
        limit=100: The number of songs to generate, determined
          by terminal height.
        """
        if self['full']:
            return
        data = func(self['id'], max_top_tracks=limit)
        self['songs'] = [Song(song) for song in data['topTracks']]
        self['albums'] = [Album(album) for album in data['albums']]
        self['full'] = True


class Album(MusicObject):
    """A dict representing an album."""

    def __init__(self, album, full=False, source='api'):
        """
        Create a new Album

        Arguments:
        artist: Dict with album information from gmusicapi.

        Keyword arguments:
        full=False: Whether or not the album's song list is populated.
        source='api': The source of the argument dict, which changes how
          we initialize the album.
        """
        if source == 'api':
            super().__init__(album['albumId'], album['name'], 'album', full)
            self['artist'] = Artist({
                'artistId': album['artistId'][0], 'name': album['artist']})
            try:
                self['songs'] = [Song(s) for s in album['tracks']]
            except KeyError:
                self['songs'] = []

        elif source == 'json':
            super().__init__(album['id'], album['name'], 'album', full)
            self['artist'] = Artist(album['artist'], source='json')
            self['songs'] = [Song(song, source='json')
                             for song in album['songs']]

    @staticmethod
    def verify(item):
        """
        Make sure a dict contains all necessary album data.

        Arguments:
        item: The dict being checked.

        Returns: Whether or not the item contains sufficient data.
        """
        return all(k in item for k in
                   ('id', 'name', 'kind', 'full', 'artist', 'songs'))

    def __str__(self):
        """Format an album into a string.

        Returns: The album name and artist.
        """
        return ' - '.join((self['name'], self['artist']['name']))

    def play(self):
        """Play an album's song list."""
        if not self['full']:
            self.fill(consts.mapping['albums']['lookup'])
        MusicObject.play(self['songs'])

    def collect(self, limit=20):
        """
        Collect all of an album's information: songs, artist, and albums.

        Keyword arguments:
        limit=20: Upper limit of each element to collect,
          determined by terminal height.

        Returns: A dict of lists with keys 'songs, 'artists', and 'albums'.
        """
        return {
            'songs': self['songs'][:min(len(self['songs']), limit)],
            'artists': [self['artist']],
            'albums': [self]
        }

    def fill(self, func, limit=100):
        """
        If an album is not full, fill in its song list.

        Arguments:
        func: Function to get data from the api.

        Keyword arguments:
        limit: Irrelevant, we always generate all songs.

        Returns: A new, full, Album.
        """
        if self['full']:
            return

        self['songs'] = [
            Song(song) for song in func(self['id'])['tracks']
        ]
        self['full'] = True


class Song(MusicObject):
    """A dict representing a song."""

    def __init__(self, song, full=True, source='api'):
        """
        Create a new Song.

        Arguments:
        song: Dict with a song's information.

        Keyword arguments:
        full=True: A song is always considered full.
        source='api': The source of the argument dict, which changes how
          we initialize the song.
        """
        if source == 'api':  # Initializing from api results.
            super().__init__(song['storeId'], song['title'], 'song', full)
            try:
                self['artist'] = Artist({
                    'name': song['artist'], 'artistId': song['artistId'][0]
                })
            except TypeError:
                self['artist'] = Artist({
                    'name': song['artist'], 'artistId': song['artistId']
                })
            self['album'] = Album({
                'name': song['album'], 'albumId': song['albumId'],
                'artist': song['artist'], 'artistId': song['artistId'],
            })
            self['time'] = Song.time_from_ms(song['durationMillis'])

        elif source == 'json':  # Initializing from JSON.
            super().__init__(song['id'], song['name'], 'song', full)
            self['artist'] = Artist(song['artist'], source='json')
            self['album'] = Album(song['album'], source='json')
            self['time'] = song['time']

    @staticmethod
    def verify(item):
        """
        Make sure a dict contains all necessary song data.

        Arguments:
        item: The dict being checked.

        Returns: Whether or not the item contains sufficient data.
        """
        return all(k for k in
                   ('id', 'name', 'kind', 'full', 'artist', 'album', 'time'))

    @staticmethod
    def time_from_ms(ms):
        """
        Converts milliseconds into a mm:ss formatted string.

        Arguments:
        ms: Number of milliseconds.

        Returns: ms in mm:ss.
        """
        ms = int(ms)
        minutes = str(ms // 60000).zfill(2)
        seconds = str(ms // 1000 % 60).zfill(2)
        return "%s:%s" % (minutes, seconds)

    def __str__(self):
        """
        Format a song into a string.

        Returns: The song title, artist name, and album name.
        """
        return ' - '.join((self['name'], self['artist']['name']))

    def play(self):
        """Play a song."""
        MusicObject.play([self])

    def collect(self, limit=None):
        """
        Collect all of a song's information: songs, artist, and albums.

        Keyword arguments:
        limit=None: Irrelevant.

        Returns: A dict of lists with keys 'songs, 'artists', and 'albums'.
        """
        return {
            'songs': [self],
            'artists': [self['artist']],
            'albums': [self['album']]
        }

    def fill(self, func, limit=0):
        """
        Do nothing. All songs are already 'full'.

        Arguments:
        func: Function to get data from the api. Irrelevant here.

        Keyword arguments:
        limit=0: Irrelevant.
        """
        return
