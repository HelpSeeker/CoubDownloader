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
    echo " --limit-rate RATE     limit download rate (see wget's --limit-rate)"
    echo " --limit-num LIMIT     limit max. number of downloaded coubs"
    echo " --sleep TIME          pause the script for TIME seconds before each download"
    echo ""
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Get coub links from a channel
# $1 is the full channel URL
parse_input_channel() {
    channel_id="${1##*/}"
    
    curl -s "https://coub.com/api/v2/timeline/channel/$channel_id" > temp.json
    total_pages=$(jq -r .total_pages temp.json)
    echo "Downloading channel info (${1}):"

    for (( i=1; i<=total_pages; i++ ))
    do
        echo "$i out of ${total_pages}"
        curl -s "https://coub.com/api/v2/timeline/channel/${channel_id}?page=$i" > temp.json
        for (( j=0; j<=9; j++ ))
        do
            if [[ -n $limit_num ]] && (( ${#link_list[@]} >= limit_num )); then return; fi
            
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
            link_list+=("https://coub.com/view/$id")
        done
    done

    rm temp.json
    
    echo "###"
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse file with coub links
# $1 is path to the input list
parse_input_list() {
    if [[ ! -e "$1" ]]; then
        echo "Invalid input list! '$1' doesn't exist. Aborting..."
        exit
    else
        echo "Parsing input list (${1})"
    fi

    temp_list+=($(grep 'coub.com/view' "$1"))

    # temporary array as additional step to easily check download limit
    for link in ${temp_list[@]}
    do
        if [[ -n $limit_num ]] && (( ${#link_list[@]} >= limit_num )); then return; fi
        link_list+=("$link")
    done
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse directly provided coub links
# $1 is the full coub URL
parse_input_links() {
    if [[ -n $limit_num ]] && (( ${#link_list[@]} >= limit_num )); then return; fi
    link_list+=("$1")
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Check coub existence
existence() {
    if [[ ( -e "${coub_id}.mkv" && $audio_only = false && $video_only = false ) || \
          ( -e "${coub_id}.mp4" && $video_only = true ) || \
          ( -e "${coub_id}.mp3" && $audio_only = true ) ]]; then
          
        return 0
    else
        return 1
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Prompt user whether or not to overwrite coub
overwrite_prompt() {
    echo "Overwrite file?"
    select option in {yes,no}
    do
        case $option in
            yes) return 0;;
            no) return 1;;
        esac   
    done
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Decide to overwrite coub
# Prompt user if necessary
overwrite() {
    if [[ $prompt_answer = "-n" ]]; then
        return 1
    elif [[ $prompt_answer = "-y" ]]; then
        return 0
    else
        if overwrite_prompt; then
            return 0
        else
            return 1
        fi
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Download individual coub parts
download() {
    error_video=false
    error_audio=false
    
    curl -s "https://coub.com/api/v2/coubs/$coub_id" > temp.json

    # jq's default output for non-existent entries is null
    video="null"
    audio="null"
    # Loop through default qualities; use highest available
    for quality in {high,med}
    do
        if [[ $video == "null" ]]; then
            video="$(jq -r .file_versions.html5.video.${quality}.url temp.json)"
        fi
        if [[ $audio == "null" ]]; then
            audio="$(jq -r .file_versions.html5.audio.${quality}.url temp.json)"
        fi
    done
    
    # Video download
    if [[ $audio_only = false ]]; then
        if [[ $video == "null" ]]; then
            error_video=true
        else
            if ! wget $limit_rate -q "$video" -O "${coub_id}.mp4"; then
                error_video=true
            fi
        fi
    fi
    
    # Audio download
    if [[ $video_only = false ]]; then
        if [[ $audio == "null" ]]; then
            error_audio=true
        else
            if ! wget $limit_rate -q "$audio" -O "${coub_id}.mp3"; then
                error_audio=true
            fi
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
    ffmpeg -y -loglevel panic -f concat -safe 0 \
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
    -c | --channel) parse_input_channel "$2"; shift 2;;
    -r | --repeat) repeat="$2"; shift 2;;
    --recoubs) recoubs=true; shift;;
    --no-recoubs) recoubs=false; shift;;
    --only-recoubs) only_recoubs=true; shift;;
    --preview) preview=true; preview_command="$2"; shift 2;;
    --no-preview) preview=false; shift;;
    --audio-only) audio_only=true; shift;;
    --video-only) video_only=true; shift;;
    # TODO: implement value check
    --limit-rate) limit_rate="--limit-rate=$2"; shift 2;;
    # TODO: implement value check
    --limit-num) limit_num="$2"; shift 2;;
    # TODO: implement value check
    --sleep) sleep_dur="$2"; shift 2;;
    -*) echo -e "Unknown flag '$1'!\n"; usage; exit;;
    *coub.com/view/*) parse_input_links "$1"; shift;;
    *) echo "$1 is neither an option nor a coub link. Skipping..."; shift;;
    esac

    if [[ -n $limit_num ]] && (( ${#link_list[@]} >= limit_num )); then
        echo "Download limit reached."
        echo "###"
        break
    fi
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

for link in ${link_list[@]}
do
    (( counter += 1 ))
    echo "$counter out of ${#link_list[@]} (${link})"
    coub_id="${link##*/}"
    
    # Pass existing files to avoid unnecessary downloads 
    if existence && ! overwrite; then continue; fi
    # Wait for sleep_dur seconds
    sleep $sleep_dur &> /dev/null

    download
    
    # Skip coub if (audio) not available
    if [[ $error_video = true || ($error_audio = true && $only_audio = true) ]]; then continue; fi

    if [[ $audio_only = false ]]; then
        # Fix broken video stream
        printf '\x00\x00' | dd of="${coub_id}.mp4" bs=1 count=2 conv=notrunc &> /dev/null
    fi
    
    # Merge video and audio
    if [[ $video_only = false && $audio_only = false && $error_audio = false ]]; then merge; fi
    
    preview
done
