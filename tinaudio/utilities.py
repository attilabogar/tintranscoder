from .shared import *
from .album import *
from .cache import ICache


def surveyor(albums: Dict[str, AlbumSet], path: str) -> None:
    """
    Maps the album collection' root directory recursively
    into an album set

    Arguments:
        albums {Dict[str, AlbumSet]} -- Album sets (returns)
        path {str} -- Album collection' root directory
    """
    c = ICache(path)
    for d in c.getindex():
        (dirs, files) = c.get(d)
        foundcue = False
        for fx in files:
            if PATTERN_FLAC.match(fx) or PATTERN_DTS.match(fx):
                # check for .cue
                if PATTERN_DTS.match(fx):
                    fbase = fx[:-4]
                else:
                    fbase = fx[:-5]
                cue = fbase + ".cue"
                # this is a flac+cue album(set)
                if cue in files:
                    foundcue = True
                    if PATTERN_CUE_MULTI.match(fbase):
                        # multi-CD
                        multisearch = PATTERN_CUE_MULTI.search(fbase)
                        multibase = multisearch.group(1)
                        multinumber = int(multisearch.group(2), 10)
                        # check for repeat
                        keyparts = d.split(os.sep)
                        if keyparts[len(keyparts) - 1] != multibase:
                            key = os.path.join(d, multibase)
                        else:
                            key = d
                        if key not in albums:
                            albums[key] = AlbumSet(c.getroot(), key)
                        albums[key].addAlbum(AlbumCue(c, d, key, fbase), multinumber)
                    else:
                        # single-cd
                        key = os.path.join(d, fbase)
                        albums[key] = AlbumSet(c.getroot(), os.path.join(d, fbase))
                        albums[key].addAlbum(AlbumCue(c, d, key, fbase), 1)
        if not (foundcue or PATTERN_SKIP.match(d)):
            i = 0
            while i < len(dirs) and not PATTERN_CD.match(dirs[i]):
                i += 1
            if i < len(dirs):
                # this a multi album
                albums[d] = AlbumSet(c.getroot(), d)
                for dx in dirs:
                    no = int(PATTERN_CD.search(dx).group(1), 10)
                    albums[d].addAlbum(AlbumSplit(c, d, d + "/" + dx), no)
            else:
                # double-check for flac files
                j = 0
                while j < len(files) and not (PATTERN_FLAC.match(files[j]) or PATTERN_DTS.match(files[j])):
                    j += 1
                if j < len(files):
                    albums[d] = AlbumSet(c.getroot(), d)
                    albums[d].addAlbum(AlbumSplit(c, d, d), 1)
