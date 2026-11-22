FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i "s/archive.ubuntu.com/de.archive.ubuntu.com/g" /etc/apt/sources.list.d/ubuntu.sources \
 && dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-pip xvfb psmisc procps \
      libfreetype6 libx11-6 libxext6 libxrandr2 libxrender1 libxi6 \
      libxcursor1 libxcomposite1 libasound2t64 libpulse0 libgl1 libvulkan1 \
      libnss3 libdbus-1-3 libstdc++6 \
      libc6:i386 libgcc-s1:i386 libstdc++6:i386 libfreetype6:i386 \
      libx11-6:i386 libxext6:i386 libxrandr2:i386 libxrender1:i386 libxi6:i386 \
      libxcursor1:i386 libxcomposite1:i386 libasound2t64:i386 libpulse0:i386 \
      libgl1:i386 libvulkan1:i386 libnss3:i386 libdbus-1-3:i386 \
 && python3 -m pip install --break-system-packages --no-cache-dir legendary-gl==0.21.1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/chiv-x64
