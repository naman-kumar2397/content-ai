#!/usr/bin/env bash
# demo_v2: Joey's lip-synced line + Hugsy's deadpan reaction, 6 s, 1080x1920 @ 30 fps.
#   1. voice:   Chatterbox preset "joey" (scripts/tts.py --voice joey)       -> ../timelines/demo_v2_joey.wav (committed)
#   2. visemes: Rhubarb Lip Sync 1.14 (MIT), dialog text given as a hint      -> ../timelines/demo_v2.json "cues"
#   3. render:  render2.mjs, Mesa llvmpipe under Xvfb, layered plate mode     -> out/demo_v2.mp4
# Set REGEN=1 to redo steps 1-2 (needs the .venv from scripts/setup_voice.sh and RHUBARB=/path/to/rhubarb).
set -euo pipefail
cd "$(dirname "$0")"
TL=../timelines; TEXT="Whoa! This robot just learned to make pancakes!"; START=0.45; DUR=6; FPS=${FPS:-30}
if [ "${REGEN:-0}" = 1 ]; then
  (cd ../.. && .venv/bin/python scripts/tts.py --voice joey --text "$TEXT" --out character/timelines/demo_v2_joey.wav)
  echo "$TEXT" > /tmp/demo_v2.txt
  "$RHUBARB" -f json -d /tmp/demo_v2.txt --extendedShapes GHX $TL/demo_v2_joey.wav -o /tmp/demo_v2.rhubarb.json
  python3 -c "import json,sys; r=json.load(open('/tmp/demo_v2.rhubarb.json')); json.dump({'duration':$DUR,'lineStart':$START,'audio':'demo_v2_joey.wav','text':sys.argv[1],'cues':r['mouthCues']},open('$TL/demo_v2.json','w'),indent=0)" "$TEXT"
fi
# soundtrack: line starts at lineStart, padded to the clip length
ffmpeg -loglevel error -y -f lavfi -t $START -i anullsrc=r=24000:cl=mono -i $TL/demo_v2_joey.wav \
  -filter_complex "[0][1]concat=n=2:v=0:a=1,apad=whole_dur=$DUR" -ar 48000 out/demo_v2_audio.wav
xvfb-run -a node render2.mjs --anim --backend llvmpipe --workers 1 --fps $FPS --seconds $DUR \
  --timeline $TL/demo_v2.json --audio out/demo_v2_audio.wav --out out/demo_v2.mp4
