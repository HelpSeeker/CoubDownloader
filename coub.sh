#!/bin/bash

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Default Settings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# -y to overwrite existing coubs
# -n to skip existing coubs
# empty to be prompted
#prompt_answer="-y"

# Default download destination
save_path="$HOME/coub"

# Keep individual video/audio streams
keep=false 

# How often to loop the video
# If longer than audio duration -> audio decides length
repeat=1000

# Use fixed (max) duration
#duration="-t 00:01:00.000"

# Download reposts during channel downloads
recoubs=true

# ONLY download reposts during channel downloads
only_recoubs=false

# Show preview after each download with the given command
preview=false
preview_command="mpv"

# Only download video/audio stream
# Either both false or ONE true
audio_only=false
video_only=false

# Restrict the download rate
#limit_rate="--limit-rate=100K"

# Restrict max. number of downloads
#limit_num=50

# Wait for X seconds before each download
#sleep_dur=10

# Don't touch these
input_links=()
input_lists=()
input_channels=()
coub_list=()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Help text
usage() {
    echo "CoubDownloader is a simple download script for coub.com"
    echo "Usage: coub.sh [OPTIONS] INPUT [INPUT]..."
    echo ""
    echo "Input:"
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
    echo " -r, --repeat N        repeat video N times (default: until audio ends)"
    echo " -d, --duration TIME   specify max. coub duration (FFmpeg syntax)"
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
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

check_requirements() {
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
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

parse_options() {
    while [[ "$1" ]]
    do
        case "$1" in
        -h | --help) usage; exit;;
        -y | --yes) prompt_answer="-y"; shift;;
        -n | --no) prompt_answer="-n"; shift;;
        -s | --short) repeat=1; shift;;
        -p | --path) save_path="$2"; shift 2;;
        -k | --keep) keep=true; shift;;
        -l | --list) input_lists+=("$2"); shift 2;;
        -c | --channel) input_channels+=("$2"); shift 2;;
        -r | --repeat) repeat="$2"; shift 2;;
        -d | --duration) duration="-t $2"; shift 2;;
        --recoubs) recoubs=true; shift;;
        --no-recoubs) recoubs=false; shift;;
        --only-recoubs) only_recoubs=true; shift;;
        --preview) preview=true; preview_command="$2"; shift 2;;
        --no-preview) preview=false; shift;;
        --audio-only) audio_only=true; shift;;
        --video-only) video_only=true; shift;;
        # TODO: implement value check
        --limit-rate) limit_rate="--limit-rate=$2"; shift 2;;
        --limit-num) limit_num="$2"; shift 2;;
        --sleep) sleep_dur="$2"; shift 2;;
        -*) echo -e "Unknown flag '$1'!\n"; usage; exit;;
        *coub.com/view/*) input_links+=("$1"); shift;;
        *) echo -e "$1 is neither an option nor a coub link!\n"; usage; exit;;
        esac
    done
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

check_options() {
    # Check for preview command validity
    if [[ $preview = true && -z "$(command -v $preview_command)" ]]; then
        echo "'$preview_command' not valid as preview command! Aborting..."
        exit
    fi

    # Check options with numerical values
    # Throw errors for non-integers and other nonsensical values
    if (( repeat <= 0 )); then
        echo "--repeat (-r) only accepts integers greater than zero."
        exit
    elif [[ -n $limit_num ]] && (( limit_num <= 0 )); then
        echo "--limit-num only accepts integers greater than zero."
        exit
    elif [[ -n $sleep_dur ]] && (( sleep_dur <= 0 )); then
        echo "--sleep only accepts integers greater than zero."
        exit
    fi
    
    # Check duration validity
    # Easiest to just test it with ffmpeg (reasonable fast even for >1h durations)
    if [[ -n $duration ]] && \
       ! ffmpeg -v quiet -f lavfi -i anullsrc $duration -c copy -f null -; then
        echo "Invalid duration! For the supported syntax see:"
        echo "https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax"
        exit
    fi

    # Check for flag compatibility
    # Some flags simply overwrite each other (e.g. --yes/--no)
    if [[ $audio_only = true && $video_only = true ]]; then
        echo "--audio-only and --video-only are mutually exclusive!"
        exit
    elif [[ $recoubs = false && $only_recoubs = true ]]; then
        echo "--no-recoubs and --only-recoubs are mutually exclusive!"
        exit
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse directly provided coub links
# $1 is the full coub URL
parse_input_link() {
    if [[ -n $limit_num ]] && (( ${#coub_list[@]} >= limit_num )); then return; fi
    coub_list+=("$1")
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse file with coub links
# $1 is path to the input list
parse_input_list() {
    if [[ ! -e "$1" ]]; then
        echo "Invalid input list! '$1' doesn't exist."
    else
        echo "Reading input list (${1}):"
    fi

    # temporary array as additional step to easily check download limit
    temp_list=()
    temp_list+=($(grep 'coub.com/view' "$1"))

    for temp in ${temp_list[@]}
    do
        if [[ -n $limit_num ]] && (( ${#coub_list[@]} >= limit_num )); then return; fi
        coub_list+=("$temp")
    done
    
    echo "  ${#temp_list[@]} link(s) found"
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
        echo "  $i out of ${total_pages} pages"
        curl -s "https://coub.com/api/v2/timeline/channel/${channel_id}?page=$i" > temp.json
        for (( j=0; j<=9; j++ ))
        do
            if [[ -n $limit_num ]] && (( ${#coub_list[@]} >= limit_num )); then 
                rm temp.json
                return
            fi
            
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
            coub_list+=("https://coub.com/view/$id")
        done
    done

    rm temp.json
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

parse_input() {
    echo "Reading command line:"
    for link in ${input_links[@]}; do parse_input_link "$link"; done
    echo "  ${#input_links[@]} link(s) found"
    for list in ${input_lists[@]}; do parse_input_list "$list"; done
    for channel in ${input_channels[@]}; do parse_input_channel "$channel"; done

    if [[ -z "${coub_list[@]}" ]]; then
        echo -e "No coub links specified!\n"
        usage
        exit
    elif [[ -n $limit_num ]] && (( ${#coub_list[@]} >= limit_num )); then
        echo -e "\nDownload limit (${limit_num}) reached!"
        return
    fi
    
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
    ffmpeg -y -v quiet -f concat -safe 0 \
        -i list.txt -i "${coub_id}.mp3" $duration -c copy -shortest "${coub_id}.mkv"
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

main() {
    check_requirements
    parse_options "$@"
    check_options
    echo -e "\n### Parse Input ###\n"
    parse_input

    mkdir -p "$save_path"
    if ! cd "$save_path" 2> /dev/null; then
        echo "Error: Can't change into destination directory."
        exit
    fi
    
    echo -e "\n### Download Coubs ###\n"
    counter=0
    for coub in ${coub_list[@]}
    do
        (( counter += 1 ))
        echo "  $counter out of ${#coub_list[@]} (${coub})"
        coub_id="${coub##*/}"
        
        # Pass existing files to avoid unnecessary downloads 
        if existence && ! overwrite; then continue; fi
        # Wait for sleep_dur seconds
        sleep $sleep_dur &> /dev/null

        download
        
        # Skip coub if (audio) not available
        if [[ $error_video = true || \
             ($error_audio = true && $only_audio = true) ]]; then continue; fi

        if [[ $audio_only = false ]]; then
            # Fix broken video stream
            printf '\x00\x00' | \
            dd of="${coub_id}.mp4" bs=1 count=2 conv=notrunc &> /dev/null
        fi
        
        # Merge video and audio
        if [[ $video_only = false && \
              $audio_only = false && \
              $error_audio = false ]]; then merge; fi
        
        preview
    done
    echo -e "\n### Finished ###\n"
}

# Execute main script
main "$@"
