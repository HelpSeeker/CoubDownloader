#!/bin/bash

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Settings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

save_path="$HOME/coub"
link_list=()
short_mode=false
preview=false

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Help text
usage () {
	echo -e "CoubDownloader is a simple download script for coub.com"
	echo -e "Usage: coub.sh [OPTIONS] LINK [LINK]...\n"
	echo -e "Options:"
	echo -e " -h, --help\t\tshow this help"
	echo -e " -y, --yes\t\tanswer all prompts with yes"
	echo -e " -s, --short\t\tdisable video looping"
	echo -e " -p, --path <path>\tset output destination (default: $HOME/coub)"
	echo -e " --preview <command>\tplay finished coub via the given command"
	echo -e ""
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main script
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse input flags / links
while [[ "$1" ]]
do
	case "$1" in
	-h | --help) usage; exit;;
	-y | --yes) prompt_answer="-y"; shift;;
	-s | --short) short_mode=true; shift;;
	-p | --path) save_path="$2"; shift 2;;
	--preview) preview=true; preview_command="$2"; shift 2;;
	-*) echo "Unknown flag '$1'! Aborting..."; exit;;
	*coub.com/view/*) link_list+=("$1"); shift;;
	*) echo "$1 is neither an option nor a coub link. Skipping..."; shift;;
	esac
done

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

mkdir "$save_path" 2> /dev/null
cd "$save_path" || { echo "Error: Can't change into destination directory."; exit; }

# Check for input links
if [[ -z "${link_list[@]}" ]]; then
	echo -e "No coub links specified!\n"
	usage
	exit
fi

# Check for preview command validity
if [[ $preview = true && -z "$(command -v $preview_command)" ]]; then
	echo "'$preview_command' not valid as preview command! Aborting..."
	exit
fi

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

for link in "${link_list[@]}"
do
	filename="${link##*/}"
	# Download video and audio
	youtube-dl -o "${filename}.mp4" "$link"
	youtube-dl -f bestaudio -o "${filename}.mp3" "$link"

	# Fix the broken video
	printf '\x00\x00' | dd of="${filename}.mp4" bs=1 count=2 conv=notrunc

	# Combinging video and audio
	if [[ $short_mode = true ]]; then
		ffmpeg -loglevel panic $prompt_answer -i "${filename}.mp4" -i "${filename}.mp3" -shortest -c copy "${filename}.mkv"
	else
		# Get audio length
		audio_length=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "${filename}.mp3")

		# Print txt file with repeat entries for concat
		for (( i = 1; i <= 100; i++ ))
		do 
			echo "file '${filename}.mp4'" >> list.txt
		done

		ffmpeg -loglevel panic $prompt_answer -f concat -safe 0 -i list.txt -i "${filename}.mp3" -t $audio_length -c copy "${filename}.mkv"
		rm list.txt
	fi
	
	# Remove leftover files
	rm -v "${filename}.mp4" "${filename}.mp3"
	
	if [[ $preview = true ]]; then $preview_command "${filename}.mkv" >> /dev/null; fi
done
