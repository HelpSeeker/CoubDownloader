#!/bin/bash

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Settings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Change this to your preferred destination
save_path="$HOME/coub"
# preview=true for default preview
# Change preview_command to whatever you use
preview=false
preview_command="mpv"
# short_mode=true to permanently disable video looping
short_mode=false
# audio_only=true to permanently download ONLY audio
# video_only=true to permanently download ONLY video
audio_only=false
video_only=false
# keep=true to keep individual video/audio parts by default
keep=false 

# Don't touch these
link_list=()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Help text
usage() {
	echo -e "CoubDownloader is a simple download script for coub.com"
	echo -e "Usage: coub.sh [OPTIONS] LINK [LINK]..."
	echo -e "  or   coub.sh [OPTIONS] -l LIST [-l LIST]...\n"
	
	echo -e "Options:"
	echo -e " -h, --help\t\tshow this help"
	echo -e " -y, --yes\t\tanswer all prompts with yes"
	echo -e " -s, --short\t\tdisable video looping"
	echo -e " -p, --path <path>\tset output destination (default: $HOME/coub)"
	echo -e " -k, --keep\t\tkeep the individual video/audio parts"
	echo -e " -l, --list <file>\tread coub links from a text file"
	echo -e " --preview <command>\tplay finished coub via the given command"
	echo -e " --audio-only\t\tonly download the audio"
	echo -e " --video-only\t\tonly download the video"
	echo -e ""
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse file with coub links
# $1 is the filename of the list
parse_input_list() {
	if [[ ! -e "$1" ]]; then
		echo "Invalid input list! '$1' doesn't exist. Aborting..."
		exit
	fi
	
	link_list+=($(grep 'coub.com/view' "$1"))
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~


# Download individual coub parts
download() {
	downloaded=()
	error_video=false
	error_audio=false
	
	echo "Downloading..."
	if [[ $audio_only = false ]]; then 
		youtube-dl -o "${filename}.mp4" "$link" &> /dev/null && \
			downloaded+=("${filename}.mp4") || error_video=true
	fi
	if [[ $video_only = false ]]; then 
		youtube-dl -f bestaudio -o "${filename}.mp3" "$link" &> /dev/null && \
			downloaded+=("${filename}.mp3") || error_audio=true
	fi
	
	if [[ $error_video = true ]]; then 
		echo "Error: Coub unavailable"
	elif [[ $error_audio = true && $audio_only = true ]]; then
		echo "Error: No audio present or coub unavailable"
	else
		echo "Downloaded: ${downloaded[@]}"
	fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Combine video and audio
merge() {
	echo "Creating final video..."
	if [[ $short_mode = true ]]; then
		# Doesn't loop video
		ffmpeg -loglevel panic $prompt_answer -i "${filename}.mp4" -i "${filename}.mp3" -shortest -c copy "${filename}.mkv"
	else
		# Get audio length
		audio_length=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "${filename}.mp3")

		# Print txt file for ffmpeg's concat
		for (( i = 1; i <= 100; i++ ))
		do 
			echo "file '${filename}.mp4'" >> list.txt
		done
	
		# Loop video until audio end
		ffmpeg -loglevel panic $prompt_answer -f concat -safe 0 -i list.txt -i "${filename}.mp3" -t $audio_length -c copy "${filename}.mkv"
		rm list.txt
	fi
	echo "Created: ${filename}.mkv"
	
	if [[ $keep = false ]]; then
		# Remove leftover files
		echo "Cleaning up..."
		rm -v "${filename}.mp4" "${filename}.mp3" 2> /dev/null
	fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Show preview
preview() {
	if [[ $audio_only = true ]]; then 
		output="${filename}.mp3"
	elif [[ $video_only = true || $error_audio = true ]]; then 
		output="${filename}.mp4"
	else 
		output="${filename}.mkv"
	fi
	
	if [[ $preview = true && -e "$output" ]]; then
		echo "Playing finished coub..."
		# Necessary workaround for mpv (and perhaps CLI music players)
		# No window + redirected stdout = keyboard shortcuts not responding
		script -c "$preview_command $output" /dev/null > /dev/null
	fi
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
	-k | --keep) keep=true; shift;;
	-l | --list) parse_input_list "$2"; shift 2;;
	--preview) preview=true; preview_command="$2"; shift 2;;
	--audio-only) audio_only=true; shift;;
	--video-only) video_only=true; shift;;
	-*) echo -e "Unknown flag '$1'!\n"; usage; exit;;
	*coub.com/view/*) link_list+=("$1"); shift;;
	*) echo "$1 is neither an option nor a coub link. Skipping..."; shift;;
	esac
done

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

mkdir -p "$save_path"
cd "$save_path" 2> /dev/null || \
	{ echo "Error: Can't change into destination directory."; exit; }

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
	echo "###"
	echo "Current link: $link"
	filename="${link##*/}"
	
	# Create subshell to be able to skip files if necessary
	(
	download
	if [[ $error_video = true || ($error_audio = true && $only_audio = true) ]]; then exit; fi

	if [[ $audio_only = false ]]; then
		echo "Fixing broken video stream..."
		# Fix the broken video
		printf '\x00\x00' | dd of="${filename}.mp4" bs=1 count=2 conv=notrunc &> /dev/null
	fi
	
	# Merge video and audio
	if [[ $video_only = false && $audio_only = false && $error_audio = false ]]; then merge; fi	
	
	echo "Done!" 
	
	preview
	)
done
