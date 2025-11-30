#!/usr/bin/env bash

set -euo pipefail

DRYRUN=0
ROOT="."

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
    -d | --dry-run)
        DRYRUN=1
        shift
        ;;
    *)
        ROOT="$1"
        shift
        ;;
    esac
done

do_mv() {
    local src="$1"
    local dst="$2"

    if [[ "$DRYRUN" -eq 1 ]]; then
        echo "[DRY RUN] mv -i -- \"$src\" \"$dst\""
    else
        echo "mv -i -- \"$src\" \"$dst\""
        mv -i -- "$src" "$dst"
    fi
}

find "$ROOT" -type f \( -iname '*.mkv' -o -iname '*.mp4' \) | while IFS= read -r file; do
    codec_raw=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=codec_name \
        -of default=nw=1:nk=1 "$file" 2>/dev/null || true)

    height=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=height \
        -of default=nw=1:nk=1 "$file" 2>/dev/null || true)

    if [[ -z "$codec_raw" || -z "$height" ]]; then
        echo "Skipping (no video stream): $file"
        continue
    fi

    # shellcheck disable=SC2019
    # shellcheck disable=SC2018
    codec_raw_lc=$(echo "$codec_raw" | tr 'A-Z' 'a-z')
    case "$codec_raw_lc" in
    hevc | h265 | libx265) codec="hevc" ;;
    h264 | avc1 | libx264 | x264) codec="h264" ;;
    *) codec="$codec_raw_lc" ;;
    esac

    if [[ "$height" -ge 2160 ]]; then
        resolution="4k"
    else
        resolution="${height}p"
    fi

    dir_name=$(dirname "$file")
    base=$(basename "$file")
    ext="${base##*.}"
    name="${base%.*}"

    main="$name"
    tail=""
    # Match:
    #   group 1 = main (before the tail)
    #   group 2 = tail: " {something}" or " {something} - ptN"
    if [[ "$name" =~ (.*)(\ \{[^}]*\}( - pt[0-9]+)?)$ ]]; then
        main="${BASH_REMATCH[1]}"
        tail="${BASH_REMATCH[2]}"
    fi

    new_name="${main}.${resolution}.${codec}${tail}.${ext}"
    new_path="${dir_name}/${new_name}"

    # NEW CHECK: If filename already encodes resolution + codec, skip
    if [[ "$name" =~ \.${resolution}\.${codec}$ || "$name" =~ \.${resolution}\.${codec}\  ]]; then
        echo "Skipping (already correct resolution & codec): $file"
        continue
    fi

    if [[ "$file" == "$new_path" ]]; then
        echo "Skipping (already correct): $file"
        continue
    fi

    if [[ -e "$new_path" ]]; then
        echo "Skipping (target exists): $new_path"
        continue
    fi

    do_mv "$file" "$new_path"
done
