#!/bin/bash

# Catch user interrupt (Ctrl+C)
trap keyboard_interrupt SIGINT

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Default Settings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Change verbosity of the script
# 0 for quiet, >= 1 for normal verbosity
declare verbosity=1

# Allowed values: yes, no, prompt
declare prompt_answer="prompt"

# Default download destination
declare save_path="."

# Keep individual video/audio streams
declare keep=false

# How often to loop the video
# If longer than audio duration -> audio decides length
declare -i repeat=1000

# What video/audio quality to download
#  0 -> worst quality
# -1 -> best quality
# Everything else can lead to undefined behavior
declare -i v_quality=-1
declare -i a_quality=-1

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

# Default sort order
declare sort_order="newest"

# Advanced settings
declare -ri page_limit=99           # used for tags; must be <= 99
declare -ri entries_per_page=25     # allowed: 1-25
declare -r json="temp.json"
declare -r concat_list="list.txt"
declare -r tag_separator="_"

# Error codes
# 1 -> missing required software
# 2 -> invalid user-specified option
# 3 -> misc. runtime error (missing function argument, unknown value in case, etc.)
# 4 -> not all input coubs exist after execution (i.e. some downloads failed)
# 5 -> termination was requested mid-way by the user (i.e. Ctrl+C)
declare -ri missing_dep=1
declare -ri err_option=2
declare -ri err_runtime=3
declare -ri err_download=4
declare -ri user_interrupt=5

# Don't touch these
declare -a input_links input_lists input_channels input_tags input_searches
declare -a coub_list

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Print to stderr
function err() {
    printf "$*\n" 1>&2
}

# Print to stdout based on verbosity level
function msg() {
    (( verbosity >= 1 )) && printf "$*\n"
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Help text
function usage() {
cat << EOF
CoubDownloader is a simple download script for coub.com

Usage: ${0##*/} [OPTIONS] INPUT [INPUT]... [-o FORMAT]

Input:
  LINK                   download specified coubs
  -l, --list LIST        read coub links from a text file
  -c, --channel CHANNEL  download all coubs from a channel
  -t, --tag TAG          download all coubs with the specified tag
  -e, --search TERM      download all search results for the given term

Common options:
  -h, --help             show this help
  -q, --quiet            suppress all non-error/prompt messages
  -y, --yes              answer all prompts with yes
  -n, --no               answer all prompts with no
  -s, --short            disable video looping
  -p, --path PATH        set output destination (default: '$save_path')
  -k, --keep             keep the individual video/audio parts
  -r, --repeat N         repeat video N times (default: until audio ends)
  -d, --duration TIME    specify max. coub duration (FFmpeg syntax)

Download options:
  --sleep TIME           pause the script for TIME seconds before each download
  --limit-rate RATE      limit download rate (see curl's --limit-rate)
  --limit-num LIMIT      limit max. number of downloaded coubs
  --sort ORDER           specify download order for channels/tags
                         Allowed values:
                           newest (default)      likes_count
                           newest_popular        views_count
                           oldest (tags/search only)

Format selection:
  --bestvideo            Download best available video quality (default)
  --worstvideo           Download worst available video quality
  --bestaudio            Download best available audio quality (default)
  --worstaudio           Download worst available audio quality

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

Output:
  -o, --output FORMAT    save output with the specified name (default: %id%)

    Special strings:
      %id%        - coub ID (identifier in the URL)
      %title%     - coub title
      %creation%  - creation date/time
      %category%  - coub category
      %channel%   - channel title
      %tags%      - all tags (separated by '$tag_separator')

    Other strings will be interpreted literally.
    This option has no influence on the file extension.
EOF
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# check existence of required software
function check_requirements() {
    local -a dependencies=("jq" "ffmpeg" "curl" "grep")
    local dep

    for dep in "${dependencies[@]}"
    do
        if ! command -v "$dep" &> /dev/null; then
            err "Error: $dep not found!"
            exit $missing_dep
        fi
    done
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
        -e | --search)    input_searches+=("${2%/}"); shift 2;;
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
        --sort)           sort_order="$2"; shift 2;;
        # Format selection
        --bestvideo)      v_quality=-1; shift;;
        --worstvideo)     v_quality=0;  shift;;
        --bestaudio)      a_quality=-1; shift;;
        --worstaudio)     a_quality=0;  shift;;
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
        --write-list)     declare -gr out_file="$(readlink -f "$2")"; shift 2;;
        --use-archive)    declare -gr archive_file="$(readlink -f "$2")";
                          shift 2;;
        # Output
        -o | --output)    declare -gr out_format="$2"; shift 2;;
        # Unknown options
        -*) err "Unknown flag '$1'!"
            err "Try '${0##*/} --help' for more information."
            exit $err_option;;
        *)  err "'$1' is neither an option nor a coub link!"
            err "Try '${0##*/} --help' for more information."
            exit $err_option;;
        esac
    done
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Check validity of numerical values
# Shallow test as I don't want to include bc as requirement
# $1: To be checked option
function invalid_number() {
    [[ -z $1 ]] && \
        { err "Missing input in invalid_number!"; clean; exit $err_runtime; }
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
       ! ffmpeg -v quiet -f lavfi -i anullsrc \
            "${duration[@]}" -c copy -f null -; then
        err "Invalid duration! For the supported syntax see:"
        err "https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax"
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

    case "$sort_order" in
    newest | oldest | newest_popular | likes_count | views_count);;
    *) err "Invalid sort order ('$sort_order')!"; exit $err_option;;
    esac
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
            break
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
    [[ -z "$1" ]] && \
        { err "Missing list path in parse_input_list!"; clean;
          exit $err_runtime; }
    local file="$1"

    msg "Reading input list ($file):"

    # temporary array as additional step to easily check download limit
    local -a temp_list=()
    temp_list+=($(grep 'coub.com/view' "$1"))

    local temp
    for temp in "${temp_list[@]}"
    do
        if [[ -n $max_coubs ]] && (( ${#coub_list[@]} >= max_coubs )); then
            break
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
    [[ -z "$1" ]] && \
        { err "Missing input type in parse_input_timeline!"; \
          clean; exit $err_runtime; }
    [[ -z "$2" ]] && \
        { err "Missing input timeline in parse_input_timeline!"; \
          clean; exit $err_runtime; }
    local url_type="$1"
    local url="$2"

    case "$url_type" in
    channel)
        local channel_id="${url##*/}"
        local api_call="https://coub.com/api/v2/timeline/channel/$channel_id"
        api_call+="?"
        ;;
    tag)
        local tag_id="${url##*/}"
        local api_call="https://coub.com/api/v2/timeline/tag/$tag_id"
        api_call+="?"
        ;;
    search)
        local search_term="${url##*=}"
        local api_call="https://coub.com/api/v2/search/coubs?q=$search_term"
        api_call+="&"
        ;;
    *)
        err "Error: Unknown input type in parse_input_timeline!"
        clean; exit $err_runtime
        ;;
    esac
    api_call+="per_page=$entries_per_page"

    case "$sort_order" in
    newest);;
    oldest) if [[ $url_type == "tag" || $url_type == "search" ]]; then
                api_call+="&order_by=oldest"
            fi;;
    newest_popular | \
    likes_count | \
    views_count) api_call+="&order_by=$sort_order";;
    *) err "Wrong sort order in parse_input_timeline!"; exit $err_runtime;;
    esac

    curl -s "$api_call" > "$json"
    local -i total_pages=$(jq -r .total_pages "$json")

    msg "Downloading $url_type info ($url):"

    local -i page entry
    local coub_id
    for (( page=1; page <= total_pages; page++ ))
    do
        # tag timeline redirects pages >99 to page 1
        # channel timelines work like intended
        if [[ $url_type == "tag" ]] && (( page > page_limit )); then
            msg "  Max. page limit reached!"
            return
        fi

        msg "  $page out of $total_pages pages"
        curl -s "$api_call&page=$page" > "$json"
        for (( entry=0; entry < entries_per_page; entry++ ))
        do
            if [[ -n $max_coubs ]] && (( ${#coub_list[@]} >= max_coubs )); then
                return
            fi

            # Tag timelines / search queries should only list simple coubs
            # Only one jq call per page necessary
            if [[ $url_type == "tag" || $url_type == "search" ]]; then
                if [[ -z $max_coubs ]] || \
                   (( max_coubs >= ${#coub_list[@]}+entries_per_page )); then
                    coub_list+=($(jq -r '.coubs[] | "https://coub.com/view/" + .permalink' "$json"))
                    break
                fi
            fi

            # Channels list coubs and recoubs randomly
            # Each coub must be checked
            # Old approach: 2 jq calls per coub (type + link)
            # New approach: 1 jq call (recoub), 2 jq calls (coub)
            coub_id=$(jq -r .coubs[$entry].recoub_to.permalink "$json")
            [[ $coub_id != "null" && $recoubs == false ]] && continue
            [[ $coub_id == "null" && $only_recoubs == true ]] && continue
            [[ $coub_id == "null" ]] && \
                coub_id=$(jq -r .coubs[$entry].permalink "$json")

            [[ $coub_id != "null" ]] && \
                coub_list+=("https://coub.com/view/$coub_id")
        done
    done
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function parse_input() {
    local list channel tag

    parse_input_links
    for list in "${input_lists[@]}"; do \
        parse_input_list "$list"; done
    for channel in "${input_channels[@]}"; do \
        parse_input_timeline "channel" "$channel"; done
    for tag in "${input_tags[@]}"; do \
        parse_input_timeline "tag" "$tag"; done
    for search in "${input_searches[@]}"; do \
        parse_input_timeline "search" "$search"; done

    (( ${#coub_list[@]} == 0 )) && \
        { err "Error: No coub links specified!"; clean; exit $err_option; }

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

# $1: Coub id
function get_out_name() {
    [[ -z "$1" ]] && \
        { err "Missing coub id in get_out_name!"; clean; exit $err_runtime; }
    local id="$1"

    [[ -z "$out_format" ]] && { echo "$id"; return; }

    local out_name="$out_format"
    local substitution
    local tag
    local -a tags=()
    while true
    do
        case "$out_name" in
        *%id%*)       out_name="${out_name//%id%/$id}"
                      ;;
        *%title%*)    substitution="$(jq -r .title "$json")"
                      out_name="${out_name//%title%/$substitution}"
                      ;;
        *%creation%*) substitution="$(jq -r .created_at "$json")"
                      out_name="${out_name//%creation%/$substitution}"
                      ;;
        *%channel%*)  substitution="$(jq -r .channel.title "$json")"
                      out_name="${out_name//%channel%/$substitution}"
                      ;;
        *%category%*) substitution="$(jq -r .categories[0].permalink "$json")"
                      # Coubs don't necessarily have a category
                      [[ $substitution == "null" ]] && \
                        { out_name="${out_name//%category%/}"; continue; }
                      out_name="${out_name//%category%/$substitution}"
                      ;;
        *%tags%*)     # Necessary to only split at newlines
                      IFS_BACKUP=$IFS
                      IFS=$'\n'
                      tags=($(jq -r .tags[].title "$json"))
                      IFS=$IFS_BACKUP

                      substitution=""
                      for tag in "${tags[@]}"
                      do
                          substitution+="$tag$tag_separator"
                      done
                      out_name="${out_name//%tags%/$substitution}"
                      ;;
        *) break;;
        esac
    done

    # Strip/replace special characters that can lead to script failure (ffmpeg concat)
    # ' common among coub titles
    # Newlines can be occasionally found as well
    out_name="${out_name//[$'\'']}"
    out_name="${out_name//[$'\n']/ }"

    # Using all tags as filename can quickly explode its size
    # If it's too long, use the default name (id) instead
    # Also handles otherwise invalid filenames
    if ! touch "$out_name.mkv" 2> /dev/null; then
        err "Error: Filename invalid or too long! Falling back to '$id'."
        out_name="$id"
    fi
    rm "$out_name.mkv" 2> /dev/null

    echo "$out_name"
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Check coub existence
# $1: Output name
function existence() {
    [[ -z "$1" ]] && \
        { err "Missing output name in existence!"; clean; exit $err_runtime; }
    local name="$1"

    if [[ ( -e "$name.mkv" && $a_only == false && $v_only == false ) || \
          ( -e "$name.mp4" && $v_only == true ) || \
          ( -e "$name.mp3" && $a_only == true ) ]]; then
        return 0
    fi

    return 1
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
    *)      err "Error: Unknown prompt_answer in overwrite!";
            clean; exit $err_runtime;;
    esac
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Handles all actions regarding archive files
# $1 is the to-be-performed action
# $2 is the specific coub link
function use_archive() {
    [[ -z "$1" ]] && \
        { err "Missing action in use_archive!"; clean; exit $err_runtime; }
    [[ -z "$2" ]] && \
        { err "Missing coub id in use_archive!"; clean; exit $err_runtime;  }
    local action="$1"
    local id="$2"

    case "$action" in
    read)
        if grep -qsw "$id" "$archive_file"; then
            return 0;
        else
            return 1;
        fi
        ;;
    write) echo "$id" >> "$archive_file";;
    *) err "Error: Unknown action in use_archive!"; clean; exit $err_runtime;;
    esac
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Download individual coub parts
# $1: json
# $2: Output name
function download() {
    [[ -z "$1" ]] && \
        { err "Missing output name in download!"; clean; exit $err_runtime; }
    local name="$1"

    # jq's default output for non-existent entries is null
    local -a video=() audio=()
    local -i v_size a_size
    local quality
    # Loop through default qualities; use highest available
    for quality in {low,med,high}
    do
        v_size=$(jq -r .file_versions.html5.video.$quality.size "$json")
        a_size=$(jq -r .file_versions.html5.audio.$quality.size "$json")
        (( v_size > 0 )) && \
            video+=("$(jq -r .file_versions.html5.video.$quality.url "$json")")
        (( a_size > 0 )) && \
            audio+=("$(jq -r .file_versions.html5.audio.$quality.url "$json")")
    done

    # Video download
    if [[ $a_only == false ]] && \
       ! curl -s "${limit_rate[@]}" "${video[$v_quality]}" -o "$name.mp4"; then
        v_error=true
    fi

    # Audio download
    if [[ $v_only == false ]] && \
       ! curl -s "${limit_rate[@]}" "${audio[$a_quality]}" -o "$name.mp3"; then
        a_error=true
    fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Combine video and audio
# $1: Output name
function merge() {
    [[ -z "$1" ]] && \
        { err "Missing output name in merge!"; clean; exit $err_runtime; }
    local name="$1"

    # Print .txt for ffmpeg's concat
    for (( i=1; i <= repeat; i++ ))
    do
        echo "file '$name.mp4'" >> "$concat_list"
    done

    # Loop footage until shortest stream ends
    # Concatenated video (via list) counts as one long stream
    ffmpeg -y -v error -f concat -safe 0 \
            -i "$concat_list" -i "$name.mp3" "${duration[@]}" \
            -c copy -shortest "$name.mkv"

    # Removal not in clean, as it should only happen when merging was performed
    [[ $keep == false ]] && rm "$name.mp4" "$name.mp3"
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Show preview
# $1: Output name
function show_preview() {
    [[ -z "$1" ]] && \
        { err "Missing output name in preview!"; clean; exit $err_runtime; }
    local name="$1"

    local file="$name.mkv"
    [[ $a_only == true ]] && file="$name.mp3"
    [[ $v_only == true || $a_error == true ]] && file="$name.mp4"

    # This check is likely superfluous
    [[ ! -e "$file" ]] && \
        { err "Error: Missing file in show_preview!"; return; }

    # Necessary workaround for mpv (and perhaps CLI music players)
    # No window + redirected stdout = keyboard shortcuts not responding
    script -c "$preview_command '$file'" /dev/null > /dev/null
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function clean() {
    rm "$json" "$concat_list" 2> /dev/null
    unset v_error a_error
    unset coub_id
    unset output
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function keyboard_interrupt() {
    err "User Interrupt!"
    clean
    exit $user_interrupt
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
        (( counter++ ))
        msg "  $counter out of ${#coub_list[@]} ($coub)"

        local v_error=false a_error=false
        local coub_id="${coub##*/}"

        # Pass existing files to avoid unnecessary downloads
        # This check handles archive file search and default output formatting
        # Avoids curl usage (slow!) just to skip files anyway
        if ([[ -n $archive_file ]] && use_archive "read" "$coub_id") ||
           ([[ -z $out_format ]] && existence "$coub_id" && ! overwrite); then
            msg "Already downloaded!"
            clean
            (( downloads++ ))
            continue
        fi

        curl -s "https://coub.com/api/v2/coubs/$coub_id" > "$json"
        local output
        output="$(get_out_name "$coub_id")"
        (( $? == err_runtime )) && exit $err_runtime

        # Another check for custom output formatting
        # Far slower to skip existing files (archive usage is recommended)
        if [[ -n $out_format ]] && existence "$output" && ! overwrite; then
            msg "Already downloaded!"
            clean
            (( downloads++ ))
            continue
        fi

        # Sleep before each coub but the first one
        if [[ -n $sleep_dur ]] && (( counter > 1 )); then
            sleep $sleep_dur
        fi
        # Download video/audio streams
        download "$output"

        # Skip if the requested media couldn't be downloaded
        [[ $v_error == true ]] && \
            { err "Error: Coub unavailable!"; clean; continue; }
        [[ $a_error == true && $a_only == true ]] && \
            { err "Error: Audio or coub unavailable!"; clean; continue; }

        # Fix broken video stream
        [[ $a_only == false ]] && \
            printf '\x00\x00' | \
            dd of="$output.mp4" bs=1 count=2 conv=notrunc &> /dev/null

        # Merge video and audio
        [[ $v_only == false && $a_only == false && $a_error == false ]] && \
            merge "$output"

        # Write downloaded coub to archive
        [[ -n $archive_file ]] && use_archive "write" "$coub_id"

        # Preview downloaded coub
        [[ $preview == true ]] && show_preview "$output"

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
