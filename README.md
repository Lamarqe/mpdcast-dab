# MpdCast DAB
=====================

MpdCast DAB combines two major functionalitities: 
* DAB+ streaming server with support for radio text and live pictures
* MPD to Google cast streaming application, including song / program details (text and pictures) for
    * MPD local database
    * TvHeadend
    * The included DAB+ streaming server itself

MpdCast DAB uses the DAB+ implementation of welle.io (https://github.com/AlbrechtL/welle.io).

Table of contents
====

  * [Installation](#installation)
  * [Configuration](#configuration)
  * [Usage](#usage)
    * [Command-line parameters](#command-line-parameters) 
    * [DAB+ Server](#dab-server)
  * [Supported Hardware](#supported-hardware)
  * [Building](#building)

Installation
========
### Pre-built packages for **Debian** or **Ubuntu** 24.04+ 
(commands to be executed with root permissions)
  * `add-apt-repository ppa:lamarqe/ppa`
  * `apt update`
  * `apt install mpdcast-dab`

Configuration
=====
MpdCast DAB reads mpd.conf and requires / reads the following properties in it:
  * `audio_output` of type `"httpd"` must be enabled
  * the `name` property must be set to your chromecast device name, eg: `"Nest Hub"`

example config:

```
audio_output {
        type            "httpd"
        name            "Nest Hub"
        encoder         "lame"          # optional, vorbis or lame
        port            "8000"
        bind_to_address "0.0.0.0"               # optional, IPv4 or IPv6
        quality         "7.0"                   # do not define if bitrate is defined
        bitrate         "192"                   # do not define if quality is defined
        format          "48000:16:2"
        max_clients     "0"                     # optional 0=no limit
}
```

  
Usage
=====
### Command-line parameters

Parameter | Description | Default Value
------ | ---------- | ---------- 
-p PORT, --port PORT | Communication port to use | 8864
-c CONF, --conf CONF | MPD config file to use | /etc/mpd.conf
--disable-dabserver | Disable DAB server functionality | False
--disable-mpdcast | Disable MPD Cast functionality | False
--verbose | Enable verbose output | False

### DAB+ Server
The DAB+ server comes with a simplistic UI, accessible via the configured port.

![Screenshot](https://github.com/Lamarqe/mpdcast-dab/raw/main/scanner.jpg)

The scan will generate a .m3u8 playlist looking similar to the example below.
The playlist can be used with any audio player like VLC or MPD. 
```
#EXTINF:-1,gong fm
http://192.168.2.48:8864/stream/6C/gong%20fm
#EXTINF:-1,GONG NUERNBERG
http://192.168.2.48:8864/stream/10C/GONG%20NUERNBERG
#EXTINF:-1,HIT RADIO N1
http://192.168.2.48:8864/stream/10C/HIT%20RADIO%20N1
#EXTINF:-1,KLASSIK RADIO
http://192.168.2.48:8864/stream/5C/KLASSIK%20RADIO
#EXTINF:-1,LIEBLINGSRADIO
http://192.168.2.48:8864/stream/10C/LIEBLINGSRADIO
#EXTINF:-1,max neo
http://192.168.2.48:8864/stream/10C/max%20neo
```

Supported Hardware
====================
MpdCast DAB is intended to be used with an RTL-SDR device (https://www.rtl-sdr.com/)

Building
====================

General Information
---
The following libraries and their development files are needed:
* Python >= 3.11 
* FFTW3f
* libfaad
* librtlsdr
* pybind11

Debian / Ubuntu Linux
---
This section shows how to compile MpdCast DAB on Debian or Ubuntu (tested with Ubuntu 24.04).

1. Install the base requirements

```
sudo apt install git build-essential cmake
```

2. Install the following packages

```
sudo apt install python3-dev libfftw3-dev libfaad-dev librtlsdr-dev pybind11-dev
```

3. Clone MpdCast DAB

```
git clone https://github.com/Lamarqe/mpdcast-dab.git
```

4. Build MpdCast DAB (using cmake)

```
cmake -B build
make -C build -j3
```

5. Run MpdCast DAB and enjoy it

```
export PYTHONPATH=$PWD
./mpdcast_dab/__main__.py
```
