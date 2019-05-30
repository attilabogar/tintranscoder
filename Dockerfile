FROM archlinux/base
LABEL authors="Attila Bogár <attila.bogar@gmail.com>"

ENV USERID 1000

RUN echo -e '[multilib]\nInclude = /etc/pacman.d/mirrorlist' >> /etc/pacman.conf
RUN echo -e '[avb]\nServer = https://s3.eu-west-2.amazonaws.com/avb-repo/$repo/$arch\nSigLevel = Optional TrustAll' >> /etc/pacman.conf

RUN pacman --noconfirm -Syy && pacman --noconfirm -S \
  python python-mutagen python-yaml flac opus-tools lame neroaac ffmpeg imagemagick

RUN useradd \
  --shell /bin/bash  \
  --create-home \
  --uid $USERID \
  user

USER user
