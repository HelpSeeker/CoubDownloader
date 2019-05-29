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
# audio_only=true to permanently download ONLY audio
# video_only=true to permanently download ONLY video
audio_only=false
video_only=false
# keep=true to keep individual video/audio parts by default
keep=false 
# default number of times video gets looped
# if longer than audio duration -> audio decides length
repeat=1000

# Don't touch these
link_list=()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Help text
usage() {
    echo -e "CoubDownloader is a simple download script for coub.com"
    echo -e "Usage: new_coub.sh [OPTIONS] LINK [LINK]..."
    echo -e "  or   new_coub.sh [OPTIONS] -l LIST [-l LIST]..."
    echo -e "  or   new_coub.sh [OPTIONS] -c CHANNEL [-c CHANNEL]...\n"
    
    echo -e "Options:"
    echo -e " -h, --help            show this help"
    echo -e " -y, --yes             answer all prompts with yes"
    echo -e " -s, --short           disable video looping"
    echo -e " -p, --path <path>     set output destination (default: $HOME/coub)"
    echo -e " -k, --keep            keep the individual video/audio parts"
    echo -e " -l, --list <file>     read coub links from a text file"
    echo -e " -c, --channel <link>  download all coubs from a channel"
    echo -e " -r, repeat <n>        repeat video n times (default: until audio ends)"
    echo -e " --preview <command>   play finished coub via the given command"
    echo -e " --no-preview          explicitly disable coub preview" 
    echo -e " --audio-only          only download the audio"
    echo -e " --video-only          only download the video"
    echo -e ""
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

get_channel_list() {
    channel_id="${1##*/}"
    
    curl -s "https://coub.com/api/v2/timeline/channel/$channel_id" > temp.json
    total_pages=$(jq -r .total_pages temp.json)
    echo "Downloading channel info (${1}):"

    channel_list=()
    for (( i=1; i<=total_pages; i++ ))
    do
        curl -s "https://coub.com/api/v2/timeline/channel/${channel_id}?page=$i" > temp.json
        channel_list+=($(jq -r .coubs[].permalink temp.json))
        echo "$i out of ${total_pages}"
    done

    for id in ${channel_list[@]}
    do
        echo "https://coub.com/view/$id" >> "${channel_id}.txt"
    done

    parse_input_list "${channel_id}.txt"
    rm temp.json "${channel_id}.txt"
    echo "###"
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse file with coub links
# $1 is the coub_id of the list
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
    
    curl -s "https://coub.com/api/v2/coubs/$coub_id" > temp.json

    # jq's default output for non-existent entries is null
    video="null"
    audio="null"
    for quality in {high,med}
    do
        if [[ $video == "null" ]]; then
            video="$(jq -r .file_versions.html5.video.${quality}.url temp.json)"
        fi
        if [[ $audio == "null" ]]; then
            audio="$(jq -r .file_versions.html5.audio.${quality}.url temp.json)"
        fi
    done
    
    if [[ $audio_only = false ]]; then
        if [[ $video == "null" ]]; then
            error_video=true
        else
            if ! wget -q "$video" -O "${coub_id}.mp4"; then
                error_video=true
            fi
            downloaded+=("${coub_id}.mp4")
        fi
    fi
    
    if [[ $video_only = false ]]; then
        if [[ $audio == "null" ]]; then
            error_audio=true
        else
            if ! wget -q "$audio" -O "${coub_id}.mp3"; then
                error_audio=true
            fi
            downloaded+=("${coub_id}.mp3")
        fi
    fi
    
    if [[ $error_video = true ]]; then 
        echo "Error: Coub unavailable"
    elif [[ $error_audio = true && $audio_only = true ]]; then
        echo "Error: No audio present or coub unavailable"
    fi
    
    rm temp.json 2> /dev/null
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Combine video and audio
merge() {
    # Print .txt for ffmpeg's concat
    for (( i = 1; i <= repeat; i++ ))
    do 
        echo "file '${coub_id}.mp4'" >> list.txt
    done
    
    # Loop footage until shortest stream ends
    # Concatenated video (list.txt) counts as one long stream 
    ffmpeg -loglevel panic $prompt_answer -f concat -safe 0 \
        -i list.txt -i "${coub_id}.mp3" -c copy -shortest "${coub_id}.mkv"
    rm list.txt
        
    if [[ $keep = false ]]; then
        # Remove leftover files
        rm "${coub_id}.mp4" "${coub_id}.mp3" 2> /dev/null
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Show preview
preview() {
    if [[ $audio_only = true ]]; then 
        output="${coub_id}.mp3"
    elif [[ $video_only = true || $error_audio = true ]]; then 
        output="${coub_id}.mp4"
    else 
        output="${coub_id}.mkv"
    fi
    
    if [[ $preview = true && -e "$output" ]]; then
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
    -s | --short) repeat=1; shift;;
    -p | --path) save_path="$2"; shift 2;;
    -k | --keep) keep=true; shift;;
    -l | --list) parse_input_list "$2"; shift 2;;
    -c | --channel) get_channel_list "$2"; shift 2;;
    -r | --repeat) repeat="$2"; shift 2;;
    --preview) preview=true; preview_command="$2"; shift 2;;
    --no-preview) preview=false; shift;;
    --audio-only) audio_only=true; shift;;
    --video-only) video_only=true; shift;;
    -*) echo -e "Unknown flag '$1'!\n"; usage; exit;;
    *coub.com/view/*) link_list+=("$1"); shift;;
    *) echo "$1 is neither an option nor a coub link. Skipping..."; shift;;
    esac
done

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

mkdir -p "$save_path"
if ! cd "$save_path" 2> /dev/null; then
    echo "Error: Can't change into destination directory."
    exit
fi

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Check for requirements
if ! jq --version &> /dev/null; then
    echo "jq not found! Aborting..."
    exit
elif ! ffmpeg -version &> /dev/null; then
    echo "FFmpeg not found! Aborting..."
    exit
elif ! curl --version &> /dev/null; then
    echo "curl not found! Aborting..."
    exit
elif ! wget --version &> /dev/null; then
    echo "wget not found! Aborting..."
    exit
elif ! grep --version &> /dev/null; then
    echo "grep not found! Aborting..."
    exit
fi

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

# Check if repeat value makes sense (also throws error for non-integers)
if (( repeat <= 0 )); then
    echo "-r (--repeat) only accepts integers greater than zero."
    exit
fi

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

echo "Downloading coubs:"
counter=0

for link in "${link_list[@]}"
do
    (( counter += 1 ))
    echo "$counter out of ${#link_list[@]} (${link})"
    coub_id="${link##*/}"
    
    download
    
    # Skip coub if (audio) not available
    if [[ $error_video = true || ($error_audio = true && $only_audio = true) ]]; then continue; fi

    if [[ $audio_only = false ]]; then
        # Fix the broken video
        printf '\x00\x00' | dd of="${coub_id}.mp4" bs=1 count=2 conv=notrunc &> /dev/null
    fi
    
    # Merge video and audio
    if [[ $video_only = false && $audio_only = false && $error_audio = false ]]; then merge; fi
    
    preview
done
