import os
import subprocess
import re

import yaml
import wave

from mutagen.flac import FLAC  # type: ignore
from mutagen.apev2 import APEv2  # type: ignore
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TPE2, TCM, TDRC, TRCK, TPOS
from mutagen.mp3 import MP3
from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4, MP4Cover

from typing import Tuple, List, Dict


# patterns
PATTERN_FLAC = re.compile('.*\\.flac$')
PATTERN_DTS = re.compile('.*\\.dts$')
PATTERN_META_PERTRACK = re.compile('^cue_track([0-9]{2})_([^=]+)=(.*)$')
PATTERN_META_COMMON = re.compile('^([^=]+)=(.*)$')
PATTERN_COMMENT = re.compile('^#.*$')
PATTERN_FLAC = re.compile('.*\\.flac$')
PATTERN_CD = re.compile('^CD([0-9]{1,3})$')
PATTERN_CUE_MULTI = re.compile('^(.*) - CD([0-9]{1,3})$')
PATTERN_SKIP = re.compile('^.*/CD([0-9]{1,3})$')


COVER_TYPES = ['jpg', 'png']
COVER_BASES = ['folder', 'cover']

SUPPRESS_TAGS = [
    'tracknumber',
    'replaygain_track_gain',
    'replaygain_track_peak',
    'replaygain_album_gain',
    'replaygain_album_peak',
    'replaygain_reference_loudness',
    'rating',
    'accurateripresult',
    'encoded by',
    'encoder',
    'encoder settings',
    'source',
    'style',
    'genre'
]