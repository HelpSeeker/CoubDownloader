#!/bin/bash

# Help text
usage () {
	echo "Usage: sh $0 -c coub_code [-h] [-s]"
	echo -e "\\t-c coub_code: The unique identifier of the coub from its URL"
	echo -e "\\t-h: Show help"
	echo -e "\\t-s: Toggles shortmode. During shortmode the length of the coub is determined by the video and not the audio. Don't use for perfect loops."
}

# Assign input parameters, if specfied
while getopts ":c:hs" ARG;
do case "$ARG" in
c) coub="$OPTARG";;
h) usage && exit;;
s) short_mode=true;;
\?) echo "Unknown flag. Use $0 -h to show all available input parameters." && exit;;
esac;
done

# Make directory "Done" to save coubs to
mkdir Done 2> /dev/null

# Assign default parameters, if not otherwise specified
[[ -z $coub ]] && { echo -e "A coub code is required!\\nEnter a coub code now:" && read -r coub; }
[[ -z $short_mode ]] && short_mode=false

# Download video and audio
youtube-dl -o "$coub.%(ext)s" https://coub.com/view/"$coub"
youtube-dl -f bestaudio -o "$coub.%(ext)s" https://coub.com/view/"$coub"

# Fix the broken video
printf '\x00\x00' | dd of="$coub".mp4 bs=1 count=2 conv=notrunc

# Combinging video and audio
if [[ "$short_mode" = true ]]; then
	ffmpeg -i "$coub".mp4 -i "$coub".mp3 -shortest -c:v copy -c:a copy Done/"$coub".mkv
else
	# Get video + audio length and calculate how many times the audio is longer than the video
	video_length=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "$coub.mp4")
	audio_length=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "$coub.mp3")
	repeat=$(bc <<< "$audio_length/$video_length+1")

	# Print txt file with repeat entries for concat
	for (( i = 1; i <= repeat; i++ )); do printf "file '%s'\\n" "$coub".mp4 >> list.txt; done

	ffmpeg -f concat -i list.txt -i "$coub".mp3 -t "$audio_length" -c:v copy -c:a copy Done/"$coub".mkv
	rm list.txt
fi

# Remove left over files
rm "$coub".mp4 "$coub".mp3