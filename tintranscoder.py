#!/usr/bin/env python3
# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab:

#
# Copyright © 2019 Attila Bogár
#
# License: MIT
#

import os
import sys
import subprocess
import optparse  # change to argsparse
import queue
import threading
import multiprocessing  # parallel

from typing import List

from tinaudio.encoder import Encoder
from tinaudio.cache import ICache
from tinaudio.utilities import surveyor

from tinutils import checkdir, jobsetup


DESCRIPTION = "tintranscoder"
VERSION = "0.1"

# TODO: calculate disc-ids
# TODO: TMPFS from ENV
# TODO: failed logging w/ exception trace

# GLOBAL
encodeq = queue.Queue()
mylock = threading.Lock()


def encodeworker() -> None:
    """
    Thread worker to process job queues
    """
    while not encodeq.empty():
        j = encodeq.get()
        with mylock:
            j.announce(False)
        try:
            j.doit()
        except Exception:
            with mylock:
                j.announce(True)
        encodeq.task_done()


def perform(codec: str, options, *args: List[str]) -> None:
    """
    Busines logic for the transcoding

    Arguments:
        codec {str} -- Output codec
        options {Object} -- OptParse' options
    """

    downmix = not (options.downmix is None)
    copycover = not (options.copycover is None)
    if codec == 'flac':
        dstdir = options.flac
    if codec == 'opus':
        dstdir = options.opus
    if codec == 'aac':
        dstdir = options.aac
    if codec == 'mp3':
        dstdir = options.mp3
        downmix = True

    dstcache = ICache(dstdir)

    albums = {}
    for stree in args:
        surveyor(albums, stree)

    # init albums
    keys = sorted(list(albums.keys()))
    for k in keys:
        albums[k].load()
        # albums[k].dump()

    # get hands dirty
    encoder = Encoder(codec, downmix)
    (unlink, coverjobs, encodejobs) = jobsetup(albums, dstcache, encoder, copycover)

    # delete unnecessary files
    for u in unlink:
        print("UNLINK: {}".format(u))
        os.remove(os.path.join(dstcache.getroot(), u))
    # hack
    subprocess.call(["find", dstcache.getroot(), "-xdev", "-depth", "-mindepth", "1",
                     "-type", "d", "-empty", "-exec", "rmdir", "-v", "{}", ";"])
    # cover queue
    for j in coverjobs:
        encodeq.put(j)

    # parallel
    for i in range(multiprocessing.cpu_count()):
        t = threading.Thread(target=encodeworker)
        t.daemon = True
        t.start()
    encodeq.join()

    # encode queue
    for j in encodejobs:
        encodeq.put(j)

    # parallel
    for i in range(multiprocessing.cpu_count()):
        t = threading.Thread(target=encodeworker)
        t.daemon = True
        t.start()
    encodeq.join()


if __name__ == "__main__":
    parser = optparse.OptionParser(version="%prog version " + VERSION,
                                   description=DESCRIPTION,
                                   usage="""%prog --dst-flac=<dir>|--dst-opus=<dir>|--dst-aac=<dir>|--dst-mp3=<dir> <srcdir>*""")

    parser.add_option("--dst-flac", action="store", type="string", dest="flac", metavar="DIR",
                      help="Destination FLAC directory")

    parser.add_option("--dst-aac", action="store", type="string", dest="aac", metavar="DIR",
                      help="Destination AAC directory")

    parser.add_option("--dst-mp3", action="store", type="string", dest="mp3", metavar="DIR",
                      help="Destination MP3 directory")

    parser.add_option("--dst-opus", action="store", type="string", dest="opus", metavar="DIR",
                      help="Destination Opus directory")

    parser.add_option("--downmix", action="store_true", dest="downmix",
                      help="Downmix multi-channel")

    parser.add_option("--copycover", action="store_true", dest="copycover",
                      help="Add extra cover file")

    (options, args) = parser.parse_args()

    # check if correctly called
    guard1 = options.flac is None and options.aac is None and options.mp3 is None and options.opus is None
    guard2 = len(args) == 0
    guard3 = not checkdir(options.flac, options.aac, options.mp3, options.opus, *args)

    if guard1 or guard2 or guard3:
        parser.print_help()
        sys.exit(1)

    # process dirs
    if options.flac:
        perform('flac', options, *args)
    if options.opus:
        perform('opus', options, *args)
    if options.aac:
        perform('aac', options, *args)
    if options.mp3:
        perform('mp3', options, *args)

    # all done
    sys.exit(0)
