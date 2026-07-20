[app]
title = Media Downloader
package.name = mediadownloader
package.domain = org.mediadownloader

source.dir = .
source.include_exts = py,kv,json,txt

version = 1.0

requirements = python3,kivy==2.3.1,kivymd==1.1.1,yt-dlp,certifi

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 29
android.minapi = 24

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
