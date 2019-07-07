#!/bin/bash

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Default Settings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Change verbosity of the script
# 0 for quiet, >= 1 for normal verbosity
declare verbosity=1

# Allowed values: yes, no, prompt
declare prompt_answer="prompt"

# Default download destination
declare save_path="$HOME/coub"

# Keep individual video/audio streams
declare keep=false

# How often to loop the video
# If longer than audio duration -> audio decides length
declare -i repeat=1000

# Download reposts during channel downloads
declare recoubs=true

# ONLY download reposts during channel downloads
declare only_recoubs=false

# Show preview after each download with the given command
declare preview=false
declare preview_command="mpv"

# Only download video/audio stream
# Can't be both true!
declare a_only=false
declare v_only=false

# Advanced settings
declare -ri page_limit=99  # used for tags; must be <= 99
declare -r json="temp.json"
declare -r concat_list="list.txt"

# Error codes
# 1 -> missing required software
# 2 -> invalid user-specified option
# 3 -> misc. runtime error (missing function argument, unknown value in case, etc.)
# 4 -> not all input coubs exist after execution (i.e. some downloads failed)
declare -ri missing_dep=1
declare -ri err_option=2
declare -ri err_runtime=3
declare -ri err_download=4

# Don't touch these
declare -a input_links input_lists input_channels input_tags
declare -a coub_list

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Print to stderr
function err() {
    printf "$@\n" 1>&2
}

# Print to stdout based on verbosity level
function msg() {
    (( verbosity >= 1 )) && printf "$@\n"
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Help text
function usage() {
cat << EOF
CoubDownloader is a simple download script for coub.com

Usage: ${0##*/} [OPTIONS] INPUT [INPUT]...

Input:
  LINK                   download specified coubs
  -l, --list LIST        read coub links from a text file
  -c, --channel CHANNEL  download all coubs from a channel
  -t, --tag TAG          download all coubs with the specified tag

Common options:
  -h, --help             show this help
  -q, --quiet            suppress all non-error/prompt messages
  -y, --yes              answer all prompts with yes
  -n, --no               answer all prompts with no
  -s, --short            disable video looping
  -p, --path PATH        set output destination (default: $HOME/coub)
  -k, --keep             keep the individual video/audio parts
  -r, --repeat N         repeat video N times (default: until audio ends)
  -d, --duration TIME    specify max. coub duration (FFmpeg syntax)

Download options:
  --sleep TIME           pause the script for TIME seconds before each download
  --limit-rate RATE      limit download rate (see curl's --limit-rate)
  --limit-num LIMIT      limit max. number of downloaded coubs

Channel options:
  --recoubs              include recoubs during channel downloads (default)
  --no-recoubs           exclude recoubs during channel downloads
  --only-recoubs         only download recoubs during channel downloads

Preview options:
  --preview COMMAND      play finished coub via the given command
  --no-preview           explicitly disable coub preview

Misc. options:
  --audio-only           only download audio streams
  --video-only           only download video streams
  --write-list FILE      write all parsed coub links to FILE
  --use-archive FILE     use FILE to keep track of already downloaded coubs
EOF
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# check existence of required software
function check_requirements() {
    if ! jq --version &> /dev/null; then
        err "Error: jq not found!"
        exit $missing_dep
    elif ! ffmpeg -version &> /dev/null; then
        err "Error: FFmpeg not found!"
        exit $missing_dep
    elif ! curl --version &> /dev/null; then
        err "Error: curl not found!"
        exit $missing_dep
    elif ! grep --version &> /dev/null; then
        err "Error: grep not found!"
        exit $missing_dep
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function parse_options() {
    while [[ "$1" ]]
    do
        case "$1" in
        # Input
        # Strip trailing backslashes to avoid parsing issues and curl failure
        *coub.com/view/*) input_links+=("${1%/}"); shift;;
        -l | --list)      if [[ -f "$2" ]]; then
                              input_lists+=("$(readlink -f "$2")")
                          else
                              err "'$2' is no valid list."
                          fi;
                          shift 2;;
        -c | --channel)   input_channels+=("${2%/}"); shift 2;;
        -t | --tag)       input_tags+=("${2%/}"); shift 2;;
        # Common options
        -h | --help)      usage; exit 0;;
        -q | --quiet)     verbosity=0; shift;;
        -y | --yes)       prompt_answer="yes"; shift;;
        -n | --no)        prompt_answer="no"; shift;;
        -s | --short)     repeat=1; shift;;
        -p | --path)      save_path="$2"; shift 2;;
        -k | --keep)      keep=true; shift;;
        -r | --repeat)    repeat="$2"; shift 2;;
        -d | --duration)  declare -gra duration=("-t" "$2"); shift 2;;
        # Download options
        --sleep)          declare -gr sleep_dur="$2"; shift 2;;
        --limit-rate)     declare -gr max_rate="$2"
                          declare -gra limit_rate=("--limit-rate" "$max_rate")
                          shift 2;;
        --limit-num)      declare -gri max_coubs="$2"; shift 2;;
        # Channel options
        --recoubs)        recoubs=true; shift;;
        --no-recoubs)     recoubs=false; shift;;
        --only-recoubs)   only_recoubs=true; shift;;
        # Preview options
        --preview)        preview=true; preview_command="$2"; shift 2;;
        --no-preview)     preview=false; shift;;
        # Misc options
        --audio-only)     a_only=true; shift;;
        --video-only)     v_only=true; shift;;
        --write-list)     declare -gr out_file="$2"; shift 2;;
        --use-archive)    declare -gr archive_file="$(readlink -f "$2")"; shift 2;;
        # Unknown options
        -*) err "Unknown flag '$1'!"; usage; exit $err_option;;
        *) err "'$1' is not an option or a coub link!"; usage; exit $err_option;;
        esac
    done
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Check validity of numerical values
# Shallow test as I don't want to include bc as requirement
# $1: To be checked option
function invalid_number() {
    [[ -z $1 ]] && { err "Missing input option in invalid_number!"; exit $err_runtime; }
    local var=$1

    # check if var starts with a number
    case $var in
    0 | 0?) return 0;;  # to weed out 0, 0K, 0M, 0., ...
    [0-9]*) return 1;;
    *)      return 0;;
    esac
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function check_options() {
    # General float value check
    # Integer checking done by the arithmetic evaluation during assignment
    if [[ -n $max_rate ]] && invalid_number $max_rate; then
        err "Invalid download limit ('$max_rate')!"
        exit $err_option
    elif [[ -n $sleep_dur ]] && invalid_number $sleep_dur; then
        err "Invalid sleep duration ('$sleep_dur')!"
        exit $err_option
    fi

    # Special integer checks
    if (( repeat <= 0 )); then
        err "-r/--repeat must be greater than 0!"
        exit $err_option
    elif [[ -n $max_coubs ]] && (( max_coubs <= 0 )); then
        err "--limit-num must be greater than zero!"
        exit $err_option
    fi

    # Check duration validity
    # Easiest way to just test it with ffmpeg
    # Reasonable fast even for >1h durations
    if (( ${#duration[@]} != 0 )) && \
       ! ffmpeg -v quiet -f lavfi -i anullsrc "${duration[@]}" -c copy -f null -; then
        err "Invalid duration! For the supported syntax see:"
        err "https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax"
        exit $err_option
    fi

    # Check for preview command validity
    if [[ $preview == true ]] && ! command -v "$preview_command" > /dev/null; then
        err "Invalid preview command ('$preview_command')!"
        exit $err_option
    fi

    # Check for flag compatibility
    # Some flags simply overwrite each other (e.g. --yes/--no)
    if [[ $a_only == true && $v_only == true ]]; then
        err "--audio-only and --video-only are mutually exclusive!"
        exit $err_option
    elif [[ $recoubs == false && $only_recoubs == true ]]; then
        err "--no-recoubs and --only-recoubs are mutually exclusive!"
        exit $err_option
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function resolve_paths() {
    mkdir -p "$save_path"
    if ! cd "$save_path" 2> /dev/null; then
        err "Error: Can't change into destination directory!"
        exit $err_runtime
    fi

    # check if reserved filenames exist in output dir
    if [[ -e "$json" ]]; then
        err "Error: Reserved filename ('$json') exists in '$save_path'!"
        exit $err_runtime
    elif [[ -e "$concat_list" ]]; then
        err "Error: Reserved filename ('$concat_list') exists in '$save_path'!"
        exit $err_runtime
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse directly provided coub links
function parse_input_links() {
    local link
    for link in "${input_links[@]}"
    do
        if [[ -n $max_coubs ]] && (( ${#coub_list[@]} >= max_coubs )); then
            return
        fi
        coub_list+=("$link")
    done

    if (( ${#input_links[@]} != 0 )); then
        msg "Reading command line:"
        msg "  ${#input_links[@]} link(s) found"
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse file with coub links
# $1 is path to the input list
function parse_input_list() {
    [[ -z "$1" ]] && { err "Missing list path in parse_input_list!"; exit $err_runtime; }
    local file="$1"

    if [[ ! -e "$file" ]]; then
        err "Invalid input list! '$file' doesn't exist."
    else
        msg "Reading input list ($file):"
    fi

    # temporary array as additional step to easily check download limit
    local -a temp_list=()
    temp_list+=($(grep 'coub.com/view' "$1"))

    local temp
    for temp in "${temp_list[@]}"
    do
        if [[ -n $max_coubs ]] && (( ${#coub_list[@]} >= max_coubs )); then
            return
        fi
        coub_list+=("$temp")
    done

    msg "  ${#temp_list[@]} link(s) found"
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse various Coub timelines (channels, tags, etc.)
# $1 specifies the type of timeline
# $2 is the channel URL, tag, etc.
function parse_input_timeline() {
    [[ -z "$1" ]] && { err "Missing input type in parse_input_timeline!"; exit $err_runtime; }
    [[ -z "$2" ]] && { err "Missing input timeline in parse_input_timeline!"; exit $err_runtime; }
    local url_type="$1"
    local url="$2"

    case "$url_type" in
    channel)
        local channel_id="${url##*/}"
        local api_call="https://coub.com/api/v2/timeline/channel/$channel_id"
        ;;
    tag)
        local tag_id="${url##*/}"
        local api_call="https://coub.com/api/v2/timeline/tag/$tag_id"
        ;;
    *)
        err "Error: Unknown input type in parse_input_timeline!"
        exit $err_runtime
        ;;
    esac

    curl -s "$api_call" > "$json"
    local -i total_pages=$(jq -r .total_pages "$json")

    msg "Downloading $url_type info ($url):"

    local -i page entry
    local coub_type coub_id
    for (( page=1; page <= total_pages; page++ ))
    do
        # tag timeline redirects pages >99 to page 1
        # channel timelines work like intended
        if [[ $url_type == "tag" ]] && (( page > page_limit )); then
            msg "  Max. page limit reached!"
            return
        fi

        msg "  $page out of $total_pages pages"
        curl -s "$api_call?page=$page" > "$json"
        for (( entry=0; entry <= 9; entry++ ))
        do
            if [[ -n $max_coubs ]] && (( ${#coub_list[@]} >= max_coubs )); then
                return
            fi

            coub_type=$(jq -r .coubs[$entry].type "$json")
            # Coub::Simple -> normal coub
            # Coub::Recoub -> recoub
            if [[ $coub_type == "Coub::Recoub" && $recoubs == true ]]; then
                coub_id=$(jq -r .coubs[$entry].recoub_to.permalink "$json")
            elif [[ $coub_type == "Coub::Simple" && $only_recoubs == false ]]; then
                coub_id=$(jq -r .coubs[$entry].permalink "$json")
            else
                continue
            fi

            coub_list+=("https://coub.com/view/$coub_id")
        done
    done
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function parse_input() {
    local list channel tag

    parse_input_links
    for list in "${input_lists[@]}"; do parse_input_list "$list"; done
    for channel in "${input_channels[@]}"; do parse_input_timeline "channel" "$channel"; done
    for tag in "${input_tags[@]}"; do parse_input_timeline "tag" "$tag"; done

    (( ${#coub_list[@]} == 0 )) && \
        { err "No coub links specified!"; clean; usage; exit $err_option; }

    if [[ -n $max_coubs ]] && (( ${#coub_list[@]} >= max_coubs )); then
        msg "\nDownload limit ($max_coubs) reached!"
    fi

    # Write all parsed coub links to out_file
    if [[ -n $out_file ]]; then
        printf "%s\n" "${coub_list[@]}" > "$out_file"
        msg "\nParsed coubs written to '$out_file'!"
        clean
        exit 0
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Check coub existence
# $1: Coub id
function existence() {
    [[ -z "$1" ]] && { err "Missing coub id in existence!"; exit $err_runtime; }
    local id="$1"

    if [[ ( -e "$id.mkv" && $a_only == false && $v_only == false ) || \
          ( -e "$id.mp4" && $v_only == true ) || \
          ( -e "$id.mp3" && $a_only == true ) ]]; then
        return 0
    else
        return 1
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Decide to overwrite coub
# Prompt user if necessary
function overwrite() {
    case $prompt_answer in
    yes)    return 0;;
    no)     return 1;;
    prompt) echo "Overwrite file?"
            local option
            select option in {yes,no}
            do
                case $option in
                yes) return 0;;
                no)  return 1;;
                esac
            done;;
    *)      err "Error: Unknown prompt_answer in overwrite!"; exit $err_runtime;;
    esac
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Handles all actions regarding archive files
# $1 is the to-be-performed action
# $2 is the specific coub link
function use_archive() {
    [[ -z "$1" ]] && { err "Missing action in use_archive!"; exit $err_runtime; }
    [[ -z "$2" ]] && { err "Missing link in use_archive!"; exit $err_runtime;  }
    local action="$1"
    local link="$2"

    case "$action" in
    read)
        if grep -qsw "$link" "$archive_file"; then
            return 0;
        else
            return 1;
        fi
        ;;
    write) echo "$link" >> "$archive_file";;
    *) err "Error: Unknown action in use_archive!"; exit $err_runtime;;
    esac
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Download individual coub parts
# $1: Coub id
function download() {
    [[ -z "$1" ]] && { err "Missing coub id in download!"; exit $err_runtime; }
    local id="$1"

    curl -s "https://coub.com/api/v2/coubs/$id" > "$json"

    # jq's default output for non-existent entries is null
    local video="null" audio="null"
    local -i v_size a_size
    local quality
    # Loop through default qualities; use highest available
    for quality in {high,med}
    do
        v_size=$(jq -r .file_versions.html5.video.$quality.size "$json")
        a_size=$(jq -r .file_versions.html5.audio.$quality.size "$json")
        if [[ $video == "null" ]] && (( v_size > 0 )); then
            video="$(jq -r .file_versions.html5.video.$quality.url "$json")"
        fi
        if [[ $audio == "null" ]] && (( a_size > 0 )); then
            audio="$(jq -r .file_versions.html5.audio.$quality.url "$json")"
        fi
    done

    # Video download
    if [[ $a_only == false ]] && \
       ( [[ $video == "null" ]] || \
         ! curl -s "${limit_rate[@]}" "$video" -o "$id.mp4" ); then
        v_error=true
    fi

    # Audio download
    if [[ $v_only == false ]] && \
       ( [[ $audio == "null" ]] || \
         ! curl -s "${limit_rate[@]}" "$audio" -o "$id.mp3" ); then
        a_error=true
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Combine video and audio
# $1: Coub id
function merge() {
    [[ -z "$1" ]] && { err "Missing coub id in merge!"; exit $err_runtime; }
    local id="$1"

    # Print .txt for ffmpeg's concat
    for (( i=1; i <= repeat; i++ ))
    do
        echo "file '$id.mp4'" >> "$concat_list"
    done

    # Loop footage until shortest stream ends
    # Concatenated video (via list) counts as one long stream
    ffmpeg -y -v error -f concat -safe 0 \
            -i "$concat_list" -i "$id.mp3" "${duration[@]}" \
            -c copy -shortest "$id.mkv"

    # Removal not in clean, as it should only happen when merging was performed
    [[ $keep == false ]] && rm "$id.mp4" "$id.mp3" 2> /dev/null
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Show preview
function preview() {
    [[ -z "$1" ]] && { err "Missing coub id in preview!"; exit $err_runtime; }
    local id="$1"

    local output="$id.mkv"
    [[ $a_only == true ]] && output="$id.mp3"
    [[ $v_only == true || $a_error == true ]] && output="$id.mp4"

    # This check is likely superfluous
    [[ ! -e "$output" ]] && \
        { err "Error: Missing output in preview!"; exit $err_runtime; }

    # Necessary workaround for mpv (and perhaps CLI music players)
    # No window + redirected stdout = keyboard shortcuts not responding
    script -c "$preview_command $output" /dev/null > /dev/null
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function clean() {
    rm "$json" "$concat_list" 2> /dev/null
    unset v_error a_error
    unset coub_id
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main Function
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function main() {
    check_requirements
    parse_options "$@"
    check_options

    resolve_paths

    msg "\n### Parse Input ###\n"
    parse_input

    # Download coubs
    msg "\n### Download Coubs ###\n"
    local -i counter=0 downloads=0
    local coub
    for coub in "${coub_list[@]}"
    do
        local v_error=false a_error=false
        local coub_id="${coub##*/}"

        (( counter++ ))
        msg "  $counter out of ${#coub_list[@]} ($coub)"

        # Pass existing files to avoid unnecessary downloads
        if ( [[ -n $archive_file ]] && use_archive "read" "$coub") ||
           ( existence "$coub_id" && ! overwrite); then
            msg "Already downloaded!"
            clean
            (( downloads++ ))
            continue
        fi

        # Download video/audio streams
        [[ -n $sleep_dur ]] && sleep $sleep_dur
        download "$coub_id"

        # Skip if the requested media couldn't be downloaded
        [[ $v_error == true ]] && \
            { err "Error: Coub unavailable!"; clean; continue; }
        [[ $a_error == true && $a_only == true ]] && \
            { err "Error: Audio or coub unavailable!"; clean; continue; }

        # Fix broken video stream
        [[ $a_only == false ]] && \
            printf '\x00\x00' | \
            dd of="$coub_id.mp4" bs=1 count=2 conv=notrunc &> /dev/null

        # Merge video and audio
        [[ $v_only == false && $a_only == false && $a_error == false ]] && \
            merge "$coub_id"

        # Write downloaded coub to archive
        [[ -n $archive_file ]] && use_archive "write" "$coub"

        # Preview downloaded coub
        [[ $preview == true ]] && preview "$coub_id"

        # Clean workspace
        clean

        # Record successful download
        (( downloads++ ))
    done

    msg "\n### Finished ###\n"

    # Indicate failure, if not all input coubs exist after execution
    (( downloads < counter )) && exit $err_download
}

# Execute main function
(( $# == 0 )) && { usage; exit 0; }
main "$@"
exit 0
