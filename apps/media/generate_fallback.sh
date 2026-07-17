#!/bin/sh
set -eu

output=/fallback/fallback.mp4
temporary=/fallback/fallback.tmp.mp4

if [ -s "$output" ]; then
  exit 0
fi

ffmpeg -nostdin -hide_banner -loglevel error \
  -f lavfi -i "color=c=0x111827:s=1280x720:r=30" \
  -f lavfi -i "anullsrc=r=48000:cl=stereo" \
  -t 5 -shortest \
  -c:v libx264 -preset veryfast -profile:v main -pix_fmt yuv420p -g 60 \
  -c:a aac -b:a 128k -ar 48000 -ac 2 \
  -movflags +faststart "$temporary"
mv "$temporary" "$output"
