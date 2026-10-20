#!/bin/bash
# Upscale frames, burn captions, mux normalized audio. Run from repo root.
set -e
C=output/clips; A=$C/audio
J=$(ffmpeg -hide_banner -i $A/mix_raw.wav -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
g() { echo "$J" | python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
ffmpeg -y -hide_banner -loglevel error -i $A/mix_raw.wav -af "loudnorm=I=-15.2:TP=-1.0:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true,aresample=48000" -ar 48000 $A/mix.wav
python3 - <<'P' > $A/filter.txt
import json
T = json.load(open('output/clips/joey_origin_timing.json'))
f = "[0:v]scale=1080:1920:flags=lanczos,format=yuv420p[v0];"
prev = 'v0'
for i, c in enumerate(T['captions']):
    a, b = c['t']
    f += f"[{prev}][{i+2}:v]overlay=enable='between(t,{a:.3f},{b:.3f})':format=auto[v{i+1}];"
    prev = f'v{i+1}'
print(f.rstrip(';'))
P
DUR=$(python3 -c "import json;print(json.load(open('$C/joey_origin_timing.json'))['duration'])")
ffmpeg -y -hide_banner -loglevel error -framerate 24 -i ${FRAMES:-$C/origin_frames}/f_%04d.png -i $A/mix.wav \
  -loop 1 -i $A/cap0.png -loop 1 -i $A/cap1.png -loop 1 -i $A/cap2.png -loop 1 -i $A/cap3.png \
  -filter_complex_script $A/filter.txt -map "[v4]" -map 1:a -t $DUR \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -r 24 -c:a aac -b:a 192k -movflags +faststart ${OUT:-$C/joey_origin.mp4}
ffmpeg -hide_banner -i ${OUT:-$C/joey_origin.mp4} -af ebur128 -f null - 2>&1 | grep -A1 "Integrated" | tail -2
