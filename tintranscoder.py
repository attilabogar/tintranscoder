#!/usr/bin/env python3
# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab:

#
# Copyright © 2019 Attila Bogár
#
# License: MIT
#

DESCRIPTION = "tintranscoder"
VERSION = "0.1"

# TODO: calculate disc-ids
# TODO: TMPFS from ENV
# TODO: failed logging w/ exception trace

import os
import sys
import re
import yaml
import tempfile
import shutil
import subprocess
import optparse
import wave
from mutagen.flac import FLAC, CueSheet
from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4, MP4Cover
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from mutagen.id3 import TIT2, TPE1, TALB, TPE2, TCM, TDRC, TRCK, TPOS, TXXX
from mutagen.apev2 import APEv2

# parallel
import queue, threading, multiprocessing

# patterns
PATTERN_FLAC = re.compile('.*\.flac$')
PATTERN_DTS = re.compile('.*\.dts$')
PATTERN_CD = re.compile('^CD([0-9]{1,3})$')
PATTERN_SKIP = re.compile('^.*/CD([0-9]{1,3})$')
PATTERN_CUE_MULTI = re.compile('^(.*) - CD([0-9]{1,3})$')
PATTERN_META_PERTRACK = re.compile('^cue_track([0-9]{2})_([^=]+)=(.*)$')
PATTERN_META_COMMON = re.compile('^([^=]+)=(.*)$')
PATTERN_COMMENT = re.compile('^#.*$')

COVER_TYPES = [ 'jpg', 'png' ]
COVER_BASES = [ 'folder', 'cover' ]
COVER_FILE = 'folder.jpg'

TMPFS = '/tmp'

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
  'genre' ]

# GLOBAL
encodeq = queue.Queue()
mylock = threading.Lock()


class ICache(object):
  """This class caches a directory subtree"""

  def __init__(self, path):
    if path[0]!='/':
      self.tracktunes = []
      raise Exception('path MUST be absolute')
    self.path = path
    while self.path[-1] == '/':
      self.path = self.path[:-1]
    self.index = []
    self.files = {}
    self.dirs = {}
    self.timecache = {}
    # walk, walk, walk
    for (xpath, xdirs, xfiles) in os.walk(self.path, topdown=True):
      relative_path=xpath[len(self.path)+1:]
      self.index.append(relative_path)
      # store files
      xfiles.sort()
      tmpfiles=[]
      # store dirs
      xdirs.sort()
      self.dirs[relative_path]=xdirs
      for f in xfiles:
        relative_file = os.path.join(relative_path, f)
        absolute_file = os.path.join(self.path, relative_file)
        if os.path.isfile(absolute_file):
          self.timecache[relative_file] = os.path.getmtime(absolute_file)
          tmpfiles.append(f)
      self.files[relative_path]=tmpfiles
    self.index.sort()

  def get(self, relative_path):
    return (self.dirs[relative_path], self.files[relative_path])

  def getmtime(self, relative_file):
    return self.timecache[relative_file]

  def getindex(self):
    return self.index

  def getroot(self):
    return self.path

  def flatten(self):
    flat = []
    for k in self.index:
      (dirs, files) = self.get(k)
      for i in range(0,len(files)):
        flat.append(os.path.join(k, files[i]))
    return flat

  def getleafs(self):
    leafs = []
    for k in self.index:
      (dirs, files) = self.get(k)
      if len(files)>0:
        leafs.append(k)
    leafs.sort()
    return leafs


class Album(object):
  def __init__(self):
    self.key = None
    self.coverfile = None
    self.covertime = 0
    self.trackname = []
    self.tracktime = []
    self.trackmeta = []
    self.tracktotal = 0

  def dump(self):
    tracks = []
    for i in range(0,self.tracktotal):
      if self.tracktotal>99:
        s = "{:03d} ".format(i+1)
      else:
        s = "{:02d} ".format(i+1)
      tracks.append(s + self.trackname[i])
    return tracks

  def getmeta(self, tracknumber):
    return self.trackmeta[tracknumber-1]

  def recalcmtimes(self):
    if self.coverfile:
      for i in range(0, self.tracktotal):
        self.tracktime[i]=max(self.tracktime[i],self.covertime)

  def getcover(self):
    return self.coverfile

  def load(self):
    self.loadtrackname()
    self.findcover()
    self.recalcmtimes()

  def gettracktime(self, no):
    return self.tracktime[no]


class AlbumSplit(Album):
  def __init__(self, icache, key, albumdir):
    super(AlbumSplit, self).__init__()
    self.icache = icache
    self.key = key
    self.albumdir = albumdir
    self.tracktunes = []
    self.format = "FLAC"

  def export(self, tracknumber, wavfile):
    FNULL=open(os.devnull, 'w')
    tunefile = os.path.join(self.icache.getroot(), self.albumdir, self.tracktunes[tracknumber-1])
    if self.format == 'DTS':
      # DTS
      subprocess.call(['ffmpeg', '-y', '-i', tunefile, '-vn', '-c:a', 'pcm_s24le', wavfile], stdout=FNULL, stderr=FNULL)
    else:
      # FLAC
      subprocess.call(['flac', '-f', '--totally-silent', '-d', '-o', wavfile, tunefile], stdout=FNULL, stderr=FNULL)
    FNULL.close()

  def loadtrackname(self):
    (dirs, files) = self.icache.get(self.albumdir)
    # count how many flacs/dts
    tuneno = 0
    tunes = []
    for i in range(0,len(files)):
      if PATTERN_FLAC.match(files[i]) or PATTERN_DTS.match(files[i]):
        tunes.append(files[i])
        tuneno += 1
    # load and validate
    if tuneno>99:
      pl = 4
    else:
      pl = 3
    i = 0
    while i<tuneno:
      if tuneno>99:
        ps = "{:03d} ".format(i+1)
      else:
        ps = "{:02d} ".format(i+1)
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
    self.tracktotal=tuneno

  def findcoverindir(self, d):
    (dirs, files) = self.icache.get(d)
    for base in COVER_BASES:
      for t in COVER_TYPES:
        prospect = "{}.{}".format(base, t)
        if prospect in files:
          return prospect
    return None

  def findcover(self):
    pd = self.albumdir
    prospect = self.findcoverindir(self.albumdir)
    if prospect == None:
      pd = self.key
      prospect = self.findcoverindir(self.key)
    if prospect:
      self.coverfile = os.path.join(pd, prospect)
      self.covertime = self.icache.getmtime(self.coverfile)
    return None

  def loadmeta(self):
    for i in range(0,self.tracktotal):
      if self.tracktotal>99:
        ii="{:03d}".format(i+1)
      else:
        ii="{:02d}".format(i+1)
      self.trackmeta.append({})
      if self.format == 'DTS':
        # DTS
        f=os.path.join(self.icache.getroot(), self.albumdir, ii + " " + self.trackname[i] + ".dts")
        dts = APEv2(f)

        # guard
        if 'Track' in dts.keys():
          tmp = dts['Track']
          (tracknumber, tracktotal) = str(tmp).split('/')
          numnumber = int(tracknumber, 10)
          numtotal = int(tracktotal, 10)
          if numtotal != self.tracktotal or numnumber != (i+1):
            raise Exception("TUNE-CHAOS: %s" % self.albumdir)
        else:
          raise Exception("TUNE-CHAOS: %s" % self.albumdir)

        # album
        if 'Album' in dts.keys():
          self.trackmeta[i]['album'] = [ str(xx) for xx in dts['Album'] ]
        # artist
        if 'Artist' in dts.keys():
          self.trackmeta[i]['artist'] = [ str(xx) for xx in dts['Artist'] ]
        # year
        if 'Year' in dts.keys():
          self.trackmeta[i]['date'] = [ str(xx) for xx in dts['Year'] ]
        # title
        if 'Title' in dts.keys():
          self.trackmeta[i]['title'] = [ str(xx) for xx in dts['Title'] ]
      else:
        # FLAC
        f=os.path.join(self.icache.getroot(), self.albumdir, ii + " " + self.trackname[i] + ".flac")
        ff = FLAC(f)
        for t in ff.keys():
          self.trackmeta[i][t.lower()]=ff[t]
        for t in SUPPRESS_TAGS:
          if t in self.trackmeta[i].keys():
            del self.trackmeta[i][t]

      if self.tracktotal>99:
        self.trackmeta[i]['tracknumber'] = [ "{:03d}".format(i+1) ]
        self.trackmeta[i]['tracktotal'] = [ "{:03d}".format(self.tracktotal) ]
      else:
        self.trackmeta[i]['tracknumber'] = [ "{:02d}".format(i+1) ]
        self.trackmeta[i]['tracktotal'] = [ "{:02d}".format(self.tracktotal) ]
    return None


class AlbumCue(Album):
  def __init__(self, icache, reldir, key, cdroot):
    super(AlbumCue, self).__init__()
    self.icache = icache
    self.reldir = reldir
    self.key = key
    self.cdroot = cdroot

  def export(self, tracknumber, wavfile):
    FNULL=open(os.devnull, 'w')
    flacfile = os.path.join(self.icache.getroot(), self.reldir, self.cdroot + ".flac")
    subprocess.call(['flac', '-f', '--totally-silent', '-d', '-o', wavfile,
      "--cue={:d}.1-{:d}.1".format(tracknumber, tracknumber+1), flacfile], stdout=FNULL, stderr=FNULL)
    FNULL.close()

  def findcover(self):
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
    return

  def loadtrackname(self):
    f = os.path.join(self.icache.getroot(), self.reldir, self.cdroot + ".files.yml")
    ff = os.path.join(self.reldir, self.cdroot + ".flac")
    fm = os.path.join(self.reldir, self.cdroot + ".meta.txt")
    globaltime = max(self.icache.getmtime(ff), self.icache.getmtime(fm))
    y = None
    with open(f, 'r') as stream:
      y = yaml.load(stream)
    i=1
    ok=True
    while i<100 and ok:
      try:
        self.trackname.append(y[i])
        self.tracktime.append(globaltime)
        i+=1
      except KeyError as e:
        ok=False
    # validate against embedded FLAC cuesheet
    tmp = FLAC(os.path.join(self.icache.getroot(), ff))
    cue = tmp.cuesheet
    if cue == None:
      raise Exception("CueSheet not present in %s" % os.path.join(self.icache.getroot(), ff))
    
    if len(cue.tracks) != i:
      raise Exception("CueSheet tracknumber mismatch %s i=%d cue=%d" %
        (os.path.join(self.icache.getroot(), ff), i, len(cue.tracks)))
    # set the number of tracks
    self.tracktotal = len(self.trackname)

  def loadmeta(self):
    common = {}
    pertrack = []
    for i in range(0,self.tracktotal):
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
          if tag in pertrack[no-1].keys():
            pertrack[no-1][tag].append(value)
          else:
            pertrack[no-1][tag] = [ value ]
        else:
          tag = PATTERN_META_COMMON.search(line).group(1).lower()
          value = PATTERN_META_COMMON.search(line).group(2)
          # common tags
          if tag in common.keys():
            common[tag].append(value)
          else:
            common[tag] = [ value ]
    # post-processing
    for i in range(0,self.tracktotal):
      self.trackmeta.append({})
      for k in common.keys():
        self.trackmeta[i][k] = common[k]
      for k in pertrack[i].keys():
        self.trackmeta[i][k] = pertrack[i][k]
      for t in SUPPRESS_TAGS:
        if t in self.trackmeta[i].keys():
          del self.trackmeta[i][t]
      self.trackmeta[i]['tracknumber'] = [ "{:02d}".format(i+1) ]
    # DONE


class AlbumSet(object):

  def __init__(self, root, key):
    self.key = key
    self.albums = []
    self.disctotal = 0
    self.loaded = False
    self.root = root

  def getkey(self):
    return self.key

  def getroot(self):
    return self.root

  def dump(self):
    tracks = []
    if self.disctotal == 1:
      at = self.albums[0].dump()
      for j in range(0,len(at)):
        tracks.append( (self.key, 1, j+1, self.albums[0].gettracktime(j), at[j]) )
    else:
      for i in range(0,self.disctotal):
        at = self.albums[i].dump()
        if self.disctotal > 99:
          dn = "{:03d}.".format(i+1)
        elif self.disctotal > 9:
          dn = "{:02d}.".format(i+1)
        else:
          dn = "{:01d}.".format(i+1)
        for j in range(0,len(at)):
          tracks.append( (self.key, i+1, j+1, self.albums[i].gettracktime(j), dn+at[j]) )
    return tracks

  def addAlbum(self, a, no):
    if no != len(self.albums)+1:
      raise Exception(self.key + ": album number mismatch")
    self.albums.append(a)
    self.disctotal += 1

  def load(self):
    if not self.loaded:
      for a in self.albums:
        a.load()
      self.loaded = True

  def getcover(self):
    return self.albums[0].getcover()

  def export(self, discnumber, tracknumber, wavfile):
    self.albums[discnumber-1].export(tracknumber, wavfile)
    self.albums[discnumber-1].loadmeta()
    c = self.albums[discnumber-1].getcover()
    m = self.albums[discnumber-1].getmeta(tracknumber)
    return (c, m)

  def show(self):
    print("{} - {:02d}".format(self.key, self.disctotal))
    for  i in range(0,self.disctotal):
      if self.albums[i].coverfile:
        print("  {:02d}-COVER: {}".format(i+1, self.albums[i].coverfile))
      for j in range(0,self.albums[i].tracktotal):
        print("  {:02d}.{:02d}: {}".format(i+1, j+1, self.albums[i].trackname[j]))
        if len(self.albums[i].trackmeta)>0:
          for k in sorted(self.albums[i].trackmeta[j].keys()):
            for l in range(0,len(self.albums[i].trackmeta[j][k])):
              print("        {}={}".format(k, self.albums[i].trackmeta[j][k][l]))

def surveyor(albums, path):
  c = ICache(path)
  for d in c.getindex():
    (dirs, files) = c.get(d)
    foundcue=False
    for fx in files:
      if PATTERN_FLAC.match(fx) or PATTERN_DTS.match(fx):
        # check for .cue
        if PATTERN_DTS.match(fx):
          fbase=fx[:-4]
        else:
          fbase=fx[:-5]
        cue=fbase+".cue"
        # this is a flac+cue album(set)
        if cue in files:
          foundcue=True
          if PATTERN_CUE_MULTI.match(fbase):
            # multi-CD
            multisearch=PATTERN_CUE_MULTI.search(fbase)
            multibase=multisearch.group(1)
            multinumber=int(multisearch.group(2),10)
            # check for repeat
            keyparts = d.split(os.sep)
            if keyparts[len(keyparts)-1] != multibase:
              key = os.path.join(d,multibase)
            else:
              key = d
            if not key in albums:
              albums[key] = AlbumSet(c.getroot(), key)
            albums[key].addAlbum(AlbumCue(c, d, key, fbase), multinumber)
          else:
            # single-cd
            key = os.path.join(d,fbase)
            albums[key] = AlbumSet(c.getroot(), os.path.join(d,fbase))
            albums[key].addAlbum(AlbumCue(c, d, key, fbase), 1)
    if not ( foundcue or PATTERN_SKIP.match(d) ):
      i=0
      while i<len(dirs) and not PATTERN_CD.match(dirs[i]):
        i+=1
      if i<len(dirs):
        # this a multi album
        albums[d] = AlbumSet(c.getroot(), d)
        for dx in dirs:
          no = int(PATTERN_CD.search(dx).group(1), 10)
          albums[d].addAlbum(AlbumSplit(c, d, d+"/"+dx), no)
      else:
        # double-check for flac files
        j=0
        while j<len(files) and not (PATTERN_FLAC.match(files[j]) or PATTERN_DTS.match(files[j])):
          j+=1
        if j<len(files):
          albums[d] = AlbumSet(c.getroot(), d)
          albums[d].addAlbum(AlbumSplit(c, d, d), 1)


class TrackMeta(object):

  def __init__(self, meta):
    self.meta = meta

  def multitag(self, field, separator):
    first = True
    out = u''
    for t in self.meta[field]:
      if not first:
          out += separator
      out += t
      first = False
    return out

  # title
  def title(self):
    title = self.multitag('title', ' · ')
    return title

  # artist
  def artist(self):
    artist = self.multitag('artist', '/')
    return artist

  # album
  def album(self):
    album = self.multitag('album', ' - ')
    return album

  # album artist
  def albumartist(self):
    albumartist = ''
    if 'albumartist' in self.meta:
      albumartist = self.multitag('albumartist', '/')
    else:
      albumartist = self.multitag('artist', '/')
    return albumartist

  # composer
  def composer(self):
    composer = None
    if 'composer' in self.meta:
      composer = self.multitag('composer', ' & ')
    return composer

  # date
  def date(self):
    date = None
    if 'date' in self.meta:
      date = self.meta['date'][0]
    return date

  def tracknumber(self):
    return self.meta['tracknumber'][0]

  # tracktotal
  def tracktotal(self):
    return self.meta['tracktotal'][0]

  # discnumber
  def discnumber(self):
    discnumber = '1'
    if 'discnumber' in self.meta:
      discnumber = self.meta['discnumber'][0]
    return discnumber

  # disctotal
  def disctotal(self):
    disctotal = '1'
    if 'disctotal' in self.meta:
      disctotal = self.meta['disctotal'][0]
    return disctotal


class Encoder(object):

  def __init__(self, codec, downmix):
    self.codec = codec
    self.downmix = downmix

  def suffix(self):
    if self.codec == 'aac':
      return "m4a"
    else:
      return self.codec

  def downmixWAV(self, wavf):
    # HACK: https://github.com/jiaaro/pydub/issues/129
    # FIXME: a reliable method to get number of wav channels
    multichannel=True
    try:
      w = wave.open(wavf, 'rb')
      if w.getnchannels() < 3:
        multichannel=False
      w.close()
    except Exception as e:
      pass
    if multichannel:
      newwavf=wavf[:-4]+"-stereo.wav"
      FNULL = open(os.devnull, 'w')
      subprocess.call(['ffmpeg', '-y', '-i', wavf, '-c:a', 'pcm_s24le', '-ac', '2', newwavf], stdout=FNULL, stderr=FNULL)
      FNULL.close()
      os.remove(wavf)
      os.rename(newwavf,wavf)


  def encode(self, wavf, dstf, cover, meta):
    if self.downmix:
      self.downmixWAV(wavf)
    if self.codec == 'opus':
      self.encodeOpus(wavf, dstf, cover, meta)
    elif self.codec == 'flac':
      self.encodeFLAC(wavf, dstf, cover, meta)
    elif self.codec == 'aac':
      self.encodeAAC(wavf, dstf, cover, meta)
    elif self.codec == 'mp3':
      self.encodeMP3(wavf, dstf, cover, meta)
    else:
      raise Exception('Unsupported encoder: '+self.codec)


  def encodeOpus(self, wavf, dstf, cover, meta):
    # TODO: bitrate 160/128
    FNULL=open(os.devnull, 'w')
    args = ['opusenc', '--bitrate', '192', '--quiet' ]
    if cover:
      args.append('--picture')
      args.append(cover)
    args.append(wavf)
    args.append(dstf)
    subprocess.call(args, stdout=FNULL, stderr=FNULL)
    FNULL.close()
    # tag the file
    opus = OggOpus(dstf)
    # no need to save r128_track_gain
    for c in sorted(meta.keys()):
      opus[c] = meta[c]
    opus.save()

  def encodeFLAC(self, wavf, dstf, cover, meta):
    FNULL=open(os.devnull, 'w')
    args = [ 'flac', '-f', '--totally-silent', '--best' ]
    if cover:
      args.append('--picture')
      args.append(cover)
    args.append('-o')
    args.append(dstf)
    args.append(wavf)
    subprocess.call(args, stdout=FNULL, stderr=FNULL)
    FNULL.close()
    # tag the file
    f = FLAC(dstf)
    for c in sorted(meta.keys()):
      f[c] = meta[c]
    f.save()


  def encodeAAC(self, wavf, dstf, cover, meta):
    FNULL = open(os.devnull, 'w')
    subprocess.call(['neroAacEnc', '-q', '0.5',
      '-if', wavf, '-of', dstf ], stdout=FNULL, stderr=FNULL)
    FNULL.close()
    # tag AAC
    mm = TrackMeta(meta)
    aac = MP4(dstf)
    aac['\xa9nam'] = mm.title()
    aac['\xa9ART'] = mm.artist()
    aac['\xa9alb'] = mm.album()
    aac['aART'] = mm.albumartist()
    if mm.date():
      aac['\xa9day'] = mm.date()

    # calculating tracknumbers
    t = mm.tracknumber()
    tt = mm.tracktotal()
    aac["trkn"] = [ ( int(t), int(tt) ) ]

    # calculating discnumber
    d = mm.discnumber()
    dd = mm.disctotal()
    aac["disk"] = [ ( int(d), int(dd) ) ]

    # composer
    if mm.composer():
      aac['\xa9wrt'] = mm.composer()

    # cover
    if cover:
      data = open(cover, 'rb').read()
      covr = []
      if cover.endswith('png'):
        covr.append(MP4Cover(data, MP4Cover.FORMAT_PNG))
      else:
        covr.append(MP4Cover(data, MP4Cover.FORMAT_JPEG))
      aac['covr'] = covr

    # save AAC tags
    aac.save()

  def encodeMP3(self, wavf, dstf, cover, meta):
    FNULL = open(os.devnull, 'w')
    subprocess.call(['lame', '-V2', wavf, dstf], stdout=FNULL, stderr=FNULL)
    FNULL.close()
    # tag MP3
    mm = TrackMeta(meta)
    mp3 = MP3(dstf, ID3=ID3)
    mp3["TIT2"] = TIT2(encoding=3, text=mm.title())
    mp3["TPE1"] = TPE1(encoding=3, text=mm.artist())
    mp3["TALB"] = TALB(encoding=3, text=mm.album())
    mp3["TPE2"] = TPE2(encoding=3, text=mm.albumartist())
    if mm.date():
      mp3["TDRC"] = TDRC(encoding=3, text=mm.date())
    mp3["TRCK"] = TRCK(encoding=3,
                       text=mm.tracknumber()+"/"+mm.tracktotal())
    mp3["TPOS"] = TPOS(encoding=3,
                       text=mm.discnumber()+"/"+mm.disctotal())

    # composer
    if mm.composer():
      mp3["TCM"] = TCM(encoding=3, text=mm.composer())

    # cover
    if cover:
      data = open(cover, 'rb').read()
      covr = []
      if cover.endswith('png'):
        mime = 'image/png'
      else:
        mime = 'image/jpeg'
      mp3.tags.add(APIC(encoding=3, mime=mime, type=3, desc=u'Cover', data=data))

    # save
    mp3.save()


class GenericJob(object):

  def status(self, s1, s2):
    print("{}: {}".format(s1,s2))


class CoverJob(GenericJob):
  def __init__(self, albumset, dstroot):
    self.albumset = albumset
    self.dstroot = dstroot
    
  def announce(self, failed):
    f = os.path.join(self.dstroot, COVER_FILE)
    if failed:
      self.status('FAILED', f)
    else:
      self.status('COVER', f)

  def doit(self):
    cover = self.albumset.getcover()
    if not os.path.isdir(self.dstroot):
      os.makedirs(self.dstroot, exist_ok=True)
    if cover:
      cover = os.path.join(self.albumset.getroot(), cover)
      dst = os.path.join(self.dstroot, COVER_FILE)
      if os.path.isfile(dst):
        os.remove(dst)
      ext = COVER_FILE[-3:]
      tmpf = dst+'.tmp'
      if cover[-3:] == ext:
        shutil.copyfile(cover, tmpf)
      else:
        # png
        (no, tmpconvertext) = tempfile.mkstemp(suffix='.'+ext, dir=TMPFS)
        os.close(no)
        FNULL=open(os.devnull, 'w')
        subprocess.call(['convert', cover, tmpconvertext], stdout=FNULL, stderr=FNULL)
        FNULL.close()
        shutil.move(tmpconvertext, tmpf)
      shutil.move(tmpf, dst)

class EncodeJob(GenericJob):
  def __init__(self, albumset, discnumber, tracknumber, dstroot, dstfile, encoder):
    self.albumset = albumset
    self.key = albumset.getkey()
    self.discnumber = discnumber
    self.tracknumber = tracknumber
    self.dstroot = dstroot
    self.dstfile = dstfile
    self.encoder = encoder
    self.albumset.load()

  def announce(self, failed):
    if failed:
      self.status('FAILED', self.dstfile)
    else:
      self.status('ENCODE', self.dstfile)

  def doit(self):
    dst = os.path.join(self.dstroot, self.dstfile)
    dstdir=os.path.dirname(dst)

    # temp wav
    (no, tmpwav) = tempfile.mkstemp(suffix='.wav', dir=TMPFS)
    os.close(no)
    (cover, meta) = self.albumset.export(self.discnumber,self.tracknumber,tmpwav)
    # prefer generated COVER_FILE
    expectedcover = os.path.join(dstdir, COVER_FILE)
    if os.path.isfile(expectedcover):
      cover = expectedcover
    elif cover:
      cover = os.path.join(self.albumset.getroot(), cover)

    # temp dst
    no, tmp = tempfile.mkstemp(suffix='.'+self.encoder.suffix(), dir=TMPFS)
    os.close(no)
    os.remove(tmp)
    self.encoder.encode(tmpwav, tmp, cover, meta)

    # delete wav
    os.remove(tmpwav)

    # find if folder exists
    if not os.path.isdir(dstdir):
      os.makedirs(dstdir, exist_ok=True)
    # move the opus
    shutil.move(tmp, dst+".tmp")
    shutil.move(dst+".tmp", dst)

def jobsetup(albums, dstcache, encoder, coverfile):
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
    if not k in keycommon:
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
    for i in range(0,len(tmp)):
      # add encode jobs
      (skey, sdiscnumber, stracknumber, smtime, sname) = tmp[i]
      sfile = os.path.join(skey, sname + "." + encoder.suffix())
      encjobs.append(EncodeJob(albums[skey], sdiscnumber, stracknumber, dstcache.getroot(), sfile, encoder))
    if coverfile and (albums[k].getcover() != None):
      cvrjobs.append(CoverJob(albums[k], os.path.join(dstcache.getroot(), k)))

  # common
  for k in keycommon:
    src = []
    (xd, xf) = dstcache.get(k)
    dst = [ os.path.join(k, x) for x in sorted(xf) ]
    tmp = albums[k].dump()
    for i in range(0,len(tmp)):
      src.append(tmp[i])
    s = 0
    d = 0
    docover = coverfile and (albums[k].getcover() != None)
    while s<len(src) and d<len(dst):
      # get source details
      (skey, sdiscnumber, stracknumber, smtime, sname) = src[s]
      sfile = os.path.join(skey, sname + "." + encoder.suffix())
      # get destination details
      dfile = dst[d]
      dmtime = dstcache.getmtime(dfile)
      if coverfile and (dfile == os.path.join(k,COVER_FILE)):
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
    while s<len(src):
      (skey, sdiscnumber, stracknumber, smtime, sname) = src[s]
      sfile = os.path.join(skey, sname + "." + encoder.suffix())
      encjobs.append(EncodeJob(albums[skey], sdiscnumber, stracknumber, dstcache.getroot(), sfile, encoder))
      s += 1
    while d<len(dst):
      dfile = dst[d]
      if coverfile and (dfile == os.path.join(k,COVER_FILE)):
        docover = smtime > dmtime
      else: 
        unlink.append(dfile)
      d += 1
    if docover:
      cvrjobs.append(CoverJob(albums[k], os.path.join(dstcache.getroot(), k)))
    # we are ready
  return (unlink, cvrjobs, encjobs)

def encodeworker():
  while not encodeq.empty():
    j = encodeq.get()
    with mylock:
      j.announce(False)
    try:
      j.doit()
    except Exception as e:
      with mylock:
        j.announce(True)
    encodeq.task_done()

def perform(codec, options, *args):

  downmix = not (options.downmix is None)
  coverfile = not (options.coverfile is None)
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
  keys=sorted(list(albums.keys()))
  for k in keys:
   albums[k].load()
   # albums[k].dump()

  # get hands dirty
  encoder = Encoder(codec, downmix)
  (unlink, coverjobs, encodejobs) = jobsetup(albums, dstcache, encoder, coverfile)

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

def checkdir(*args):
  for a in args:
    if a and not os.path.isdir(a):
      return False
    if a and a[0]!='/':
      return False
  return True

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

  parser.add_option("--coverfile", action="store_true", dest="coverfile",
    help="Add extra cover files as "+COVER_FILE)

  (options, args) = parser.parse_args()

  # check if correctly called
  guard1 = options.flac == None and options.aac == None and options.mp3 == None and options.opus == None
  guard2 = len(args)==0
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
