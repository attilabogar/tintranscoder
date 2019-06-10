from .shared import *


class TrackMeta(object):
    """
    Metadata of audio track
    """

    def __init__(self, meta) -> None:
        self.meta = meta

    def multitag(self, field: str, separator: str) -> str:
        """
        Internal helper to convert a tag's (array) into a flattened string

        Arguments:
            field {str} -- Metadata' key/tag-field
            separator {str} -- Joining separator to use

        Returns:
            str -- Flattened string
        """
        first = True
        out = u''
        for t in self.meta[field]:
            if not first:
                out += separator
            out += t
            first = False
        return out

    def title(self) -> str:
        """
        Flattens multiple title(s)

        Returns:
            str -- Flattened title(s)
        """
        title = self.multitag('title', ' · ')
        return title

    def artist(self) -> str:
        """
        Flattens multiple artist(s)

        Returns:
            str -- Flattened artist(s)
        """
        artist = self.multitag('artist', '/')
        return artist

    def album(self) -> str:
        """
        Flattens multiple album name(s)

        Returns:
            str -- Flattened album name(s)
        """
        album = self.multitag('album', ' - ')
        return album

    def albumartist(self) -> str:
        """
        Flattens multiple albumartist(s) (eg. sort key)

        Returns:
            str -- Flattened albumartist(s)
        """
        albumartist = ''
        if 'albumartist' in self.meta:
            albumartist = self.multitag('albumartist', '/')
        else:
            albumartist = self.multitag('artist', '/')
        return albumartist

    def composer(self) -> str:
        """
        Flattens multiple composer(s)

        Returns:
            str -- Flattened composer(s)
        """
        composer = None
        if 'composer' in self.meta:
            composer = self.multitag('composer', ' & ')
        return composer

    def date(self) -> str:
        """
        Date

        Returns:
            str -- Track's date
        """
        date = None
        if 'date' in self.meta:
            date = self.meta['date'][0]
        return date

    def tracknumber(self) -> str:
        """
        Tracknumber

        Returns:
            str -- Track number
        """
        return self.meta['tracknumber'][0]

    def tracktotal(self) -> str:
        """
        Total track number (in album)

        Returns:
            str -- Total track number
        """
        return self.meta['tracktotal'][0]

    def discnumber(self) -> str:
        """
        Disc number

        Returns:
            str -- Disc number
        """
        discnumber = '1'
        if 'discnumber' in self.meta:
            discnumber = self.meta['discnumber'][0]
        return discnumber

    def disctotal(self) -> str:
        """
        Total discs in album set

        Returns:
            str -- Total discs
        """
        disctotal = '1'
        if 'disctotal' in self.meta:
            disctotal = self.meta['disctotal'][0]
        return disctotal


class Album(object):
    """
    Generic Album
    """

    def __init__(self) -> None:
        self.key = None
        self.coverfile = None
        self.covertime = 0
        self.trackname = []
        self.tracktime = []
        self.trackmeta = []
        self.tracktotal = 0

    def dump(self) -> List[str]:
        """
        Lists tracks in the album

        Returns:
            List[str] -- Track filenames as "<tracknumber> <trackname>"
        """
        tracks = []
        for i in range(0, self.tracktotal):
            if self.tracktotal > 99:
                s = "{:03d} ".format(i + 1)
            else:
                s = "{:02d} ".format(i + 1)
            tracks.append(s + self.trackname[i])
        return tracks

    def getmeta(self, tracknumber: int) -> Dict[str, List[str]]:
        """
        Track's metadata

        Arguments:
            tracknumber {int} -- Track index

        Returns:
            Dict[str, List[str]] -- Metadata
        """
        return self.trackmeta[tracknumber - 1]

    def recalcmtimes(self) -> None:
        """
        Re-calculates album modification times
        """
        if self.coverfile:
            for i in range(0, self.tracktotal):
                self.tracktime[i] = max(self.tracktime[i], self.covertime)

    def getcover(self) -> str:
        """
        Album's cover (relative to album collection's root)

        Returns:
            {str} -- Cover file or None
        """
        return self.coverfile

    def load(self) -> None:
        self.loadtrackname()
        self.findcover()
        self.recalcmtimes()

    def gettracktime(self, number: int) -> float:
        """
        Track's modification time

        Arguments:
            number {int} -- Track index

        Returns:
            float -- Modification time
        """
        return self.tracktime[number]


class AlbumSplit(Album):
    """
    Album composed of distinct track files
    """
    def __init__(self, icache, key, albumdir: str) -> None:
        """
        Arguments:
            icache {ICache} -- ICache object
            key {str} -- Album set's key
            albumdir {str} -- Directory of the album
        """
        super(AlbumSplit, self).__init__()
        self.icache = icache
        self.key = key
        self.albumdir = albumdir
        self.tracktunes = []
        self.format = "FLAC"

    def export(self, tracknumber: int, wavfile: str) -> None:
        """
        Export track to PCM WAV file

        Arguments:
            tracknumber {int} -- Track number
            wavfile {str} -- WAV file
        """
        FNULL = open(os.devnull, 'w')
        tunefile = os.path.join(self.icache.getroot(), self.albumdir, self.tracktunes[tracknumber - 1])
        if self.format == 'DTS':
            # DTS
            subprocess.call(['ffmpeg', '-y', '-i', tunefile, '-vn', '-c:a', 'pcm_s24le', wavfile], stdout=FNULL, stderr=FNULL)
        else:
            # FLAC
            subprocess.call(['flac', '-f', '--totally-silent', '-d', '-o', wavfile, tunefile], stdout=FNULL, stderr=FNULL)
        FNULL.close()

    def loadtrackname(self) -> None:
        """
        Load track filenames

        Raises:
            Exception: When discrepancy in album
        """
        (dirs, files) = self.icache.get(self.albumdir)
        # count how many flacs/dts
        tuneno = 0
        tunes = []
        for i in range(0, len(files)):
            if PATTERN_FLAC.match(files[i]) or PATTERN_DTS.match(files[i]):
                tunes.append(files[i])
                tuneno += 1
        # load and validate
        if tuneno > 99:
            pl = 4
        else:
            pl = 3
        i = 0
        while i < tuneno:
            if tuneno > 99:
                ps = "{:03d} ".format(i + 1)
            else:
                ps = "{:02d} ".format(i + 1)
            if tunes[i][0:pl] == ps:
                if PATTERN_DTS.match(tunes[i]):
                    # DTS
                    self.trackname.append(tunes[i][pl:-4])
                    self.format = 'DTS'
                else:
                    # FLAC
                    self.trackname.append(tunes[i][pl:-5])
                self.tracktunes.append(tunes[i])
                self.tracktime.append(self.icache.getmtime(os.path.join(self.albumdir, tunes[i])))
            else:
                raise Exception("TUNE-CHAOS: %s" % self.albumdir)
            i += 1
        # set the number of tracks
        self.tracktotal = tuneno

    def findcoverindir(self, d: str) -> str:
        """
        Automatic probe for album cover (in a directory)

        Arguments:
            d {str} -- Key/directory relative to album collection

        Returns:
            {str} -- Cover file or None
        """
        (dirs, files) = self.icache.get(d)
        for base in COVER_BASES:
            for t in COVER_TYPES:
                prospect = "{}.{}".format(base, t)
                if prospect in files:
                    return prospect
        return None

    def findcover(self) -> str:
        """
        Automatic probe for album cover

        Returns:
            {str} -- Cover file or None
        """
        pd = self.albumdir
        prospect = self.findcoverindir(self.albumdir)
        if prospect is None:
            pd = self.key
            prospect = self.findcoverindir(self.key)
        if prospect:
            self.coverfile = os.path.join(pd, prospect)
            self.covertime = self.icache.getmtime(self.coverfile)
        return None

    def loadmeta(self) -> None:
        """
        Loads metadata of the album

        Raises:
            Exception: When discrepancy within the album
        """
        for i in range(0, self.tracktotal):
            if self.tracktotal > 99:
                ii = "{:03d}".format(i + 1)
            else:
                ii = "{:02d}".format(i + 1)
            self.trackmeta.append({})
            if self.format == 'DTS':
                # DTS
                f = os.path.join(self.icache.getroot(), self.albumdir, ii + " " + self.trackname[i] + ".dts")
                dts = APEv2(f)

                # guard
                if 'Track' in dts.keys():
                    tmp = dts['Track']
                    (tracknumber, tracktotal) = str(tmp).split('/')
                    numnumber = int(tracknumber, 10)
                    numtotal = int(tracktotal, 10)
                    if numtotal != self.tracktotal or numnumber != (i + 1):
                        raise Exception("TUNE-CHAOS: %s" % self.albumdir)
                else:
                    raise Exception("TUNE-CHAOS: %s" % self.albumdir)

                # album
                if 'Album' in dts.keys():
                    self.trackmeta[i]['album'] = [str(xx) for xx in dts['Album']]
                # artist
                if 'Artist' in dts.keys():
                    self.trackmeta[i]['artist'] = [str(xx) for xx in dts['Artist']]
                # year
                if 'Year' in dts.keys():
                    self.trackmeta[i]['date'] = [str(xx) for xx in dts['Year']]
                # title
                if 'Title' in dts.keys():
                    self.trackmeta[i]['title'] = [str(xx) for xx in dts['Title']]
            else:
                # FLAC
                f = os.path.join(self.icache.getroot(), self.albumdir, ii + " " + self.trackname[i] + ".flac")
                ff = FLAC(f)
                for t in ff.keys():
                    self.trackmeta[i][t.lower()] = ff[t]
                for t in SUPPRESS_TAGS:
                    if t in self.trackmeta[i].keys():
                        del self.trackmeta[i][t]

            if self.tracktotal > 99:
                self.trackmeta[i]['tracknumber'] = ["{:03d}".format(i + 1)]
                self.trackmeta[i]['tracktotal'] = ["{:03d}".format(self.tracktotal)]
            else:
                self.trackmeta[i]['tracknumber'] = ["{:02d}".format(i + 1)]
                self.trackmeta[i]['tracktotal'] = ["{:02d}".format(self.tracktotal)]
        return None


class AlbumCue(Album):
    """
    Album composed of single CUE+FLAC image

    (CUE not used)

    Other files required :
        <album>.meta.txt for metadata
        <album>.files.yml for track file names
    """
    def __init__(self, icache, reldir, key, cdroot) -> None:
        super(AlbumCue, self).__init__()
        self.icache = icache
        self.reldir = reldir
        self.key = key
        self.cdroot = cdroot

    def export(self, tracknumber: int, wavfile: str) -> None:
        """
        Export track to PCM WAV file

        Arguments:
            tracknumber {int} -- Track number
            wavfile {str} -- WAV file
        """
        FNULL = open(os.devnull, 'w')
        flacfile = os.path.join(self.icache.getroot(), self.reldir, self.cdroot + ".flac")
        subprocess.call(['flac', '-f', '--totally-silent', '-d', '-o', wavfile,
                         "--cue={:d}.1-{:d}.1".format(tracknumber, tracknumber + 1), flacfile], stdout=FNULL, stderr=FNULL)
        FNULL.close()

    def findcover(self) -> None:
        """
        Automatic probe for album's cover

        Returns:
            str -- Cover file or None
        """
        (dirs, files) = self.icache.get(self.reldir)
        for t in COVER_TYPES:
            prospect = self.cdroot + "." + t
            if prospect in files:
                self.coverfile = os.path.join(self.reldir, prospect)
                self.covertime = self.icache.getmtime(self.coverfile)
                return
        # check for multi-cd parent
        if self.key != os.path.join(self.reldir, self.cdroot):
            for t in COVER_TYPES:
                prospect = os.path.basename(self.key + "." + t)
                if prospect in files:
                    self.coverfile = os.path.join(self.reldir, prospect)
                    self.covertime = self.icache.getmtime(self.coverfile)
                    return
        # couldn't find cover
        return None

    def loadtrackname(self) -> None:
        """
        Load album's track file names from <album>.files.yml

        Raises:
            Exception: When discrepancy within the album
        """
        f = os.path.join(self.icache.getroot(), self.reldir, self.cdroot + ".files.yml")
        ff = os.path.join(self.reldir, self.cdroot + ".flac")
        fm = os.path.join(self.reldir, self.cdroot + ".meta.txt")
        globaltime = max(self.icache.getmtime(ff), self.icache.getmtime(fm))
        y = None
        with open(f, 'r') as stream:
            y = yaml.load(stream)
        i = 1
        ok = True
        while i < 100 and ok:
            try:
                self.trackname.append(y[i])
                self.tracktime.append(globaltime)
                i += 1
            except KeyError:
                ok = False
        # validate against embedded FLAC cuesheet
        tmp = FLAC(os.path.join(self.icache.getroot(), ff))
        cue = tmp.cuesheet
        if cue is None:
            raise Exception("CueSheet not present in %s" % os.path.join(self.icache.getroot(), ff))

        if len(cue.tracks) != i:
            raise Exception("CueSheet tracknumber mismatch %s i=%d cue=%d" %
                            (os.path.join(self.icache.getroot(), ff), i, len(cue.tracks)))
        # set the number of tracks
        self.tracktotal = len(self.trackname)

    def loadmeta(self) -> None:
        """
        Load album's metadata

        Raises:
            Exception: When discrepancy within the album
        """
        common = {}
        pertrack = []
        for i in range(0, self.tracktotal):
            pertrack.append({})
        f = os.path.join(self.icache.getroot(), self.reldir, self.cdroot + ".meta.txt")
        content = []
        with open(os.path.join(self.icache.getroot(), f), 'r', encoding='utf8') as stream:
            content = stream.readlines()
        content = [x.strip() for x in content]
        for line in content:
            # filter comments
            if not PATTERN_COMMENT.match(line):
                if PATTERN_META_PERTRACK.match(line):
                    no = int(PATTERN_META_PERTRACK.search(line).group(1), 10)
                    tag = PATTERN_META_PERTRACK.search(line).group(2).lower()
                    value = PATTERN_META_PERTRACK.search(line).group(3)
                    # push into dict
                    if tag in pertrack[no - 1].keys():
                        pertrack[no - 1][tag].append(value)
                    else:
                        pertrack[no - 1][tag] = [value]
                else:
                    tag = PATTERN_META_COMMON.search(line).group(1).lower()
                    value = PATTERN_META_COMMON.search(line).group(2)
                    # common tags
                    if tag in common.keys():
                        common[tag].append(value)
                    else:
                        common[tag] = [value]
        # post-processing
        for i in range(0, self.tracktotal):
            self.trackmeta.append({})
            for k in common.keys():
                self.trackmeta[i][k] = common[k]
            for k in pertrack[i].keys():
                self.trackmeta[i][k] = pertrack[i][k]
            for t in SUPPRESS_TAGS:
                if t in self.trackmeta[i].keys():
                    del self.trackmeta[i][t]
            self.trackmeta[i]['tracknumber'] = ["{:02d}".format(i + 1)]


class AlbumSet(object):
    """
    Album set (eg. single or multi-CD albums)
    """

    def __init__(self, root: str, key: str) -> None:
        """
        Arguments:
            root {str} -- Root directory of the album collection
            key {str} -- Key/directory
        """
        self.key = key
        self.albums = []
        self.disctotal = 0
        self.loaded = False
        self.root = root

    def getkey(self) -> str:
        """
        Album key/directory

        Returns:
            str -- Key/directory
        """
        return self.key

    def getroot(self) -> str:
        """
        Album collection's root

        Returns:
            str -- Directory
        """
        return self.root

    def dump(self) -> None:
        tracks = []
        if self.disctotal == 1:
            at = self.albums[0].dump()
            for j in range(0, len(at)):
                tracks.append((self.key, 1, j + 1, self.albums[0].gettracktime(j), at[j]))
        else:
            for i in range(0, self.disctotal):
                at = self.albums[i].dump()
                if self.disctotal > 99:
                    dn = "{:03d}.".format(i + 1)
                elif self.disctotal > 9:
                    dn = "{:02d}.".format(i + 1)
                else:
                    dn = "{:01d}.".format(i + 1)
                for j in range(0, len(at)):
                    tracks.append((self.key, i + 1, j + 1, self.albums[i].gettracktime(j), dn + at[j]))
        return tracks

    def addAlbum(self, album: Album, number: int) -> None:
        """
        Adds an album into the album set

        Arguments:
            album {Album} -- Album
            number {[type]} -- Disc number

        Raises:
            Exception: When discrepancy in album numbering
        """
        if number != len(self.albums) + 1:
            raise Exception(self.key + ": album number mismatch")
        self.albums.append(album)
        self.disctotal += 1

    def load(self) -> None:
        """
        Loads all albums in the album set

        (tracknames, metadata, modification times)
        """
        if not self.loaded:
            for a in self.albums:
                a.load()
            self.loaded = True

    def getcover(self) -> str:
        """
        Cover for the album set

        Returns:
            str -- File path or None
        """
        return self.albums[0].getcover()

    def export(self, discnumber: int, tracknumber: int, wavfile: str) -> Tuple[str, str]:
        """
        Export a track to PCM WAV file

        Arguments:
            discnumber {int} -- Disc number of the album set
            tracknumber {int} -- Track number of the album
            wavfile {str} -- WAV file

        Returns:
            (str, str) -- Cover, MetaData
        """
        self.albums[discnumber - 1].export(tracknumber, wavfile)
        self.albums[discnumber - 1].loadmeta()
        c = self.albums[discnumber - 1].getcover()
        m = self.albums[discnumber - 1].getmeta(tracknumber)
        return (c, m)

    def show(self) -> None:
        """
        Debug routine to print an album set
        """
        print("{} - {:02d}".format(self.key, self.disctotal))
        for i in range(0, self.disctotal):
            if self.albums[i].coverfile:
                print("  {:02d}-COVER: {}".format(i + 1, self.albums[i].coverfile))
            for j in range(0, self.albums[i].tracktotal):
                print("  {:02d}.{:02d}: {}".format(i + 1, j + 1, self.albums[i].trackname[j]))
                if len(self.albums[i].trackmeta) > 0:
                    for k in sorted(self.albums[i].trackmeta[j].keys()):
                        for l in range(0, len(self.albums[i].trackmeta[j][k])):
                            print("        {}={}".format(k, self.albums[i].trackmeta[j][k][l]))