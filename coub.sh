#!/bin/bash

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Settings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Change this to your preferred destination
save_path="$HOME/coub"
# recoubs=true to download reposts during channel downloads
recoubs=true
# only_recoubs=true to only download reposts during channel downloads
only_recoubs=false
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
    echo "CoubDownloader is a simple download script for coub.com"
    echo "Usage: coub.sh [OPTIONS] LINK [LINK]..."
    echo "  or   coub.sh [OPTIONS] -l LIST [-l LIST]..."
    echo "  or   coub.sh [OPTIONS] -c CHANNEL [-c CHANNEL]..."
    echo ""
    echo "Supported input:"
    echo " LINK                  download specified coubs"
    echo " -l, --list LIST       read coub links from a text file"
    echo " -c, --channel CHANNEL download all coubs from a channel"
    echo ""   
    echo "Options:"
    echo " -h, --help            show this help"
    echo " -y, --yes             answer all prompts with yes"
    echo " -n, --no              answer all prompts with no"
    echo " -s, --short           disable video looping"
    echo " -p, --path PATH       set output destination (default: $HOME/coub)"
    echo " -k, --keep            keep the individual video/audio parts"
    echo " -r, repeat N          repeat video N times (default: until audio ends)"
    echo " --recoubs             include recoubs during channel downloads (default)"
    echo " --no-recoubs          exclude recoubs during channel downloads"
    echo " --only-recoubs        only download recoubs during channel downloads"
    echo " --preview COMMAND     play finished coub via the given command"
    echo " --no-preview          explicitly disable coub preview" 
    echo " --audio-only          only download the audio"
    echo " --video-only          only download the video"
    echo ""
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Get coub links from a channel
get_channel_list() {
    channel_id="${1##*/}"
    
    curl -s "https://coub.com/api/v2/timeline/channel/$channel_id" > temp.json
    total_pages=$(jq -r .total_pages temp.json)
    echo "Downloading channel info (${1}):"

    for (( i=1; i<=total_pages; i++ ))
    do
        curl -s "https://coub.com/api/v2/timeline/channel/${channel_id}?page=$i" > temp.json
        for (( j=0; j<=9; j++ ))
        do
            type=$(jq -r .coubs[${j}].type temp.json)
            # Coub::Simple -> normal coub
            # Coub::Recoub -> recoub
            if [[ $type == "Coub::Recoub" ]]; then
                if [[ $recoubs = true ]]; then
                    id=$(jq -r .coubs[${j}].recoub_to.permalink temp.json)
                else
                    id="null"
                fi
            else
                if [[ $only_recoubs = false ]]; then
                    id=$(jq -r .coubs[${j}].permalink temp.json)
                else
                    id="null"
                fi
            fi
            if [[ $id == "null" ]]; then continue; fi
            echo "https://coub.com/view/$id" >> "${channel_id}.txt"
        done
        echo "$i out of ${total_pages}"
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
    -n | --no) prompt_answer="-n"; shift;;
    -s | --short) repeat=1; shift;;
    -p | --path) save_path="$2"; shift 2;;
    -k | --keep) keep=true; shift;;
    -l | --list) parse_input_list "$2"; shift 2;;
    -c | --channel) get_channel_list "$2"; shift 2;;
    -r | --repeat) repeat="$2"; shift 2;;
    --recoubs) recoubs=true; shift;;
    --no-recoubs) recoubs=false; shift;;
    --only-recoubs) only_recoubs=true; shift;;
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

# Check for flag compatibility
# Some flags simply overwrite each other (e.g. --yes/--no)
if [[ $audio_only = true && $video_only = true ]]; then
    echo "--audio-only and --video-only are mutually exclusive!"
    exit
elif [[ $recoubs = false && $only_coubs = true ]]; then
    echo "--no-recoubs and --only-recoubs are mutually exclusive!"
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
