import os
import subprocess
import shutil
import tempfile
import re

from tinaudio.album import AlbumSet


TMPFS = '/tmp'

# patterns
PATTERN_FLAC = re.compile('.*\\.flac$')
PATTERN_DTS = re.compile('.*\\.dts$')
PATTERN_CD = re.compile('^CD([0-9]{1,3})$')
PATTERN_SKIP = re.compile('^.*/CD([0-9]{1,3})$')
PATTERN_CUE_MULTI = re.compile('^(.*) - CD([0-9]{1,3})$')
PATTERN_META_PERTRACK = re.compile('^cue_track([0-9]{2})_([^=]+)=(.*)$')
PATTERN_META_COMMON = re.compile('^([^=]+)=(.*)$')
PATTERN_COMMENT = re.compile('^#.*$')

COVER_TYPES = ['jpg', 'png']
COVER_BASES = ['folder', 'cover']
COVER_FILE = 'folder.jpg'


class GenericJob(object):
    """
    Generic Job

    Ancestor for CoverJob and EncodeJob
    """

    def status(self, s1: str, s2: str) -> None:
        """
        Generic status output

        Arguments:
            s1 {str} -- Pass/Fail
            s2 {str} -- Job' filename
        """
        print("{}: {}".format(s1, s2))


class CoverJob(GenericJob):
    """
    Job for album' covers
    """
    def __init__(self, albumset, dstroot) -> None:
        self.albumset = albumset
        self.dstroot = dstroot

    def announce(self, failed: bool) -> None:
        """
        Generic status logging to console

        Arguments:
            failed {bool} -- Pass/Fail
        """
        f = os.path.join(self.dstroot, COVER_FILE)
        if failed:
            self.status('FAILED', f)
        else:
            self.status('COVER', f)

    def doit(self) -> None:
        """
        Business logic for 'album cover' job
        """
        cover = self.albumset.getcover()
        if not os.path.isdir(self.dstroot):
            os.makedirs(self.dstroot, exist_ok=True)
        if cover:
            cover = os.path.join(self.albumset.getroot(), cover)
            dst = os.path.join(self.dstroot, COVER_FILE)
            if os.path.isfile(dst):
                os.remove(dst)
            ext = COVER_FILE[-3:]
            tmpf = dst + '.tmp'
            if cover[-3:] == ext:
                shutil.copyfile(cover, tmpf)
            else:
                # png
                (no, tmpconvertext) = tempfile.mkstemp(suffix='.' + ext, dir=TMPFS)
                os.close(no)
                FNULL = open(os.devnull, 'w')
                subprocess.call(['convert', cover, tmpconvertext], stdout=FNULL, stderr=FNULL)
                FNULL.close()
                shutil.move(tmpconvertext, tmpf)
            shutil.move(tmpf, dst)


class EncodeJob(GenericJob):
    """
    Job encodes a track
    """

    def __init__(self, albumset: AlbumSet, discnumber: int, tracknumber: int, dstroot: str, dstfile: str, encoder: str) -> None:
        """
        Initializes track' encode job

        Arguments:
            albumset {AlbumSet} -- Album set
            discnumber {int} -- Disc number (in slbum set)
            tracknumber {int} -- Track number (in album)
            dstroot {str} -- Output directory root
            dstfile {str} -- Output file relative to directory root
            encoder {str} -- Encoder selector
        """
        self.albumset = albumset
        self.key = albumset.getkey()
        self.discnumber = discnumber
        self.tracknumber = tracknumber
        self.dstroot = dstroot
        self.dstfile = dstfile
        self.encoder = encoder
        self.albumset.load()

    def announce(self, failed: bool) -> None:
        """
        Generic status logging to console

        Arguments:
            failed {bool} -- Pass/Fail
        """
        if failed:
            self.status('FAILED', self.dstfile)
        else:
            self.status('ENCODE', self.dstfile)

    def doit(self) -> None:
        """
        Business logic for 'track encode' job
        """
        dst = os.path.join(self.dstroot, self.dstfile)
        dstdir = os.path.dirname(dst)

        # temp wav
        (no, tmpwav) = tempfile.mkstemp(suffix='.wav', dir=TMPFS)
        os.close(no)
        (cover, meta) = self.albumset.export(self.discnumber, self.tracknumber, tmpwav)
        # prefer generated COVER_FILE
        expectedcover = os.path.join(dstdir, COVER_FILE)
        if os.path.isfile(expectedcover):
            cover = expectedcover
        elif cover:
            cover = os.path.join(self.albumset.getroot(), cover)

        # temp dst
        no, tmp = tempfile.mkstemp(suffix='.' + self.encoder.suffix(), dir=TMPFS)
        os.close(no)
        os.remove(tmp)
        self.encoder.encode(tmpwav, tmp, cover, meta)

        # delete wav
        os.remove(tmpwav)

        # find if folder exists
        if not os.path.isdir(dstdir):
            os.makedirs(dstdir, exist_ok=True)
        # move the opus
        shutil.move(tmp, dst + ".tmp")
        shutil.move(dst + ".tmp", dst)