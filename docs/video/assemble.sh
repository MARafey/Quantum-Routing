#!/usr/bin/env bash
# Assembles the narrated submission video from recorded picture clips and Pocket TTS narration.
# Narration audio and the TTS environment live outside the repo (BUILD dir) and are never committed.
# Usage: BUILD=/c/Users/Hp/qr_video_build bash docs/video/assemble.sh docs/media/submission_video.mp4
set -euo pipefail
BUILD="${BUILD:-/c/Users/Hp/qr_video_build}"
OUT="${1:-docs/media/submission_video.mp4}"
P="$BUILD/picture"; A="$BUILD/audio"; W="$BUILD/work"
mkdir -p "$W"
V="scale=1920:1080:flags=lanczos,fps=30,format=yuv420p,setsar=1"
sub() { awk -v a="$1" -v b="$2" 'BEGIN{printf "%.3f", a-b}'; }
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

# Scenes 1, 2, 3, 5: animation clip + narration starting 0.5 s in, padded with silence to the clip length.
for s in 1 2 3 5; do
  d=$(dur "$P/s$s.webm")
  ffmpeg -y -v error -i "$P/s$s.webm" -i "$A/scene$s.wav" \
    -filter_complex "[0:v]trim=start=0.15,setpts=PTS-STARTPTS,$V,fade=t=in:st=0:d=0.35,fade=t=out:st=$(sub $d 0.65):d=0.45[v];[1:a]adelay=500|500,apad,atrim=0:$(sub $d 0.15)[a]" \
    -map "[v]" -map "[a]" -c:v libx264 -crf 20 -preset medium -c:a aac -b:a 160k -ar 48000 -ac 2 "$W/seg$s.mp4"
done

# Scene 4: live demo with the narration split into four sentences, each placed at the matching on-screen action.
#   A 0.00-8.79  "Here is our planner. Press random stops ..."          at 0.4 s (stops appear)
#   B 8.96-12.33 "Press run. While the search runs ..."                  at 9.8 s (search flicker)
#   C 12.56-26.98 "The results are ranked ... hundreds of times less"    at 17.8 s (results shown)
#   D 27.09-33.36 "Switch to other regions ..."                          at 33.0 s (cross-border run)
d=$(dur "$P/demo.webm")
ffmpeg -y -v error -i "$P/demo.webm" -i "$A/scene4.wav" -filter_complex "\
[0:v]$V,fade=t=in:st=0:d=0.35,fade=t=out:st=$(sub $d 0.5):d=0.45[v];\
[1:a]asplit=4[a1][a2][a3][a4];\
[a1]atrim=0:8.79,asetpts=PTS-STARTPTS,adelay=400|400[x1];\
[a2]atrim=8.96:12.33,asetpts=PTS-STARTPTS,adelay=9800|9800[x2];\
[a3]atrim=12.56:26.98,asetpts=PTS-STARTPTS,adelay=17800|17800[x3];\
[a4]atrim=27.09:33.36,asetpts=PTS-STARTPTS,adelay=33000|33000[x4];\
[x1][x2][x3][x4]amix=inputs=4:normalize=0,apad,atrim=0:$d[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -crf 20 -preset medium -c:a aac -b:a 160k -ar 48000 -ac 2 "$W/seg4.mp4"

# Relative names: the native-Windows ffmpeg cannot resolve Git Bash style /c/... paths inside the list file.
printf "file '%s'\n" seg1.mp4 seg2.mp4 seg3.mp4 seg4.mp4 seg5.mp4 > "$W/list.txt"
ffmpeg -y -v error -f concat -safe 0 -i "$W/list.txt" -c copy -movflags +faststart "$OUT"
echo "wrote $OUT ($(dur "$OUT") s)"
