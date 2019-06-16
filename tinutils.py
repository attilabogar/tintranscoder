import os

from typing import Dict, Tuple, List

from tinaudio.album import AlbumSet
from tinaudio.cache import ICache
from tinjob import CoverJob, EncodeJob

COVER_FILE = 'folder.jpg'


def checkdir(*args: List[str]) -> bool:
    """
    Guard for checking directories

    Returns:
        bool -- True if all arguments directories
    """
    for a in args:
        if a and not os.path.isdir(a):
            return False
        if a and a[0] != '/':
            return False
    return True


def jobsetup(albums: Dict[str, AlbumSet], dstcache: ICache, encoder: str, copycover: bool) -> Tuple[List[str], List[CoverJob], List[EncodeJob]]:
    """
    Generate jobs (unlink, covers, track-encodes)

    Arguments:
        albums {dict[str, AlbumSet]} -- album set to transcode
        dstcache {ICache} -- Output directory's cache
        encode {str} -- Output codec
        coverfile {bool} -- Generate folder.jpg's

    Returns:
        (List[str], List[CoverJob], List[EncodeJob]) -- Files to unlink, Covers to replicate, Tracks to encode
    """
    srckeys = sorted(list(albums.keys()))
    dstkeys = dstcache.getleafs()
    keydel = []
    keynew = []
    keycommon = []

    # loop source
    for k in srckeys:
        if k in dstkeys:
            keycommon.append(k)
        else:
            keynew.append(k)

    # loop dst
    for k in dstkeys:
        if k not in keycommon:
            keydel.append(k)

    # state
    unlink = []
    cvrjobs = []
    encjobs = []

    # delete
    for k in keydel:
        (xd, xf) = dstcache.get(k)
        for i in xf:
            unlink.append(os.path.join(k, i))

    # new
    for k in keynew:
        tmp = albums[k].dump()
        for i in range(0, len(tmp)):
            # add encode jobs
            (skey, sdiscnumber, stracknumber, smtime, sname) = tmp[i]
            sfile = os.path.join(skey, sname + "." + encoder.suffix())
            encjobs.append(EncodeJob(albums[skey], sdiscnumber, stracknumber, dstcache.getroot(), sfile, encoder))
        if copycover and albums[k].getcover() is not None:
            cvrjobs.append(CoverJob(albums[k], os.path.join(dstcache.getroot(), k)))

    # common
    for k in keycommon:
        src = []
        (xd, xf) = dstcache.get(k)
        dst = [os.path.join(k, x) for x in sorted(xf)]
        tmp = albums[k].dump()
        for i in range(0, len(tmp)):
            src.append(tmp[i])
        s = 0
        d = 0
        docover = copycover and (albums[k].getcover() is not None)
        while s < len(src) and d < len(dst):
            # get source details
            (skey, sdiscnumber, stracknumber, smtime, sname) = src[s]
            sfile = os.path.join(skey, sname + "." + encoder.suffix())
            # get destination details
            dfile = dst[d]
            dmtime = dstcache.getmtime(dfile)
            if copycover and (dfile == os.path.join(k, COVER_FILE)):
                docover = smtime > dmtime
                d += 1
            elif sfile == dfile:
                if smtime > dmtime:
                    unlink.append(dfile)
                    encjobs.append(EncodeJob(albums[skey], sdiscnumber, stracknumber, dstcache.getroot(), sfile, encoder))
                s += 1
                d += 1
            elif sfile < dfile:
                encjobs.append(EncodeJob(albums[skey], sdiscnumber, stracknumber, dstcache.getroot(), sfile, encoder))
                s += 1
            else:
                unlink.append(dfile)
                d += 1
        while s < len(src):
            (skey, sdiscnumber, stracknumber, smtime, sname) = src[s]
            sfile = os.path.join(skey, sname + "." + encoder.suffix())
            encjobs.append(EncodeJob(albums[skey], sdiscnumber, stracknumber, dstcache.getroot(), sfile, encoder))
            s += 1
        while d < len(dst):
            dfile = dst[d]
            if copycover and (dfile == os.path.join(k, COVER_FILE)):
                docover = smtime > dmtime
            else:
                unlink.append(dfile)
            d += 1
        if docover:
            cvrjobs.append(CoverJob(albums[k], os.path.join(dstcache.getroot(), k)))
        # we are ready
    return (unlink, cvrjobs, encjobs)