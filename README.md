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

  * [Download](#download)
  * [Configuration](#configuration)
  * [Usage](#usage)
  * [Supported Hardware](#supported-hardware)
  * [Building](#building)

Download
========
### Stable binaries
* **Debian** or **Ubuntu** 24.04+
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
The command-line parameters are:

Parameter | Description | Default Value
------ | ---------- | ---------- 
--quiet | Print errors only | False (True when running as systemd service) 
--conf | Path to MPD config | /etc/mpd.conf

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

Debian / Ubuntu Linux
---
This section shows how to compile MpdCast DAB on Debian or Ubuntu (tested with Ubuntu 24.04).

1. Install the base requirements

```
sudo apt install git build-essential cmake
```

2. Install the following packages

```
sudo apt install python3-dev libfftw3-dev libfaad-dev librtlsdr-dev
```

3. Clone MpdCast DAB

```
git clone https://github.com/Lamarqe/mpdcast-dab.git
```

4. Build MpdCast DAB (using cmake)

```
mkdir build
cd build
cmake ..
make -j3
cd ..
cp build/libwelle_py.so mpdcast_dab/welle_python
```

5. Run MpdCast DAB and enjoy it

```
sudo ./mpdcast_dab/cast_sender/__main__.py
```
