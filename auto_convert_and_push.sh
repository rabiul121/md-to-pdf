#!/bin/bash

# Change these variables to your actual repo path and filenames
REPO_DIR="/home/robi/Desktop/md-to-pdf/"
INPUT_MD="Mobile Servicing Training.md"
TEMPLATE="template.tex"
LUA_FILTER="bengali-escape-emoji-hrule.lua"

cd "$REPO_DIR" || { echo "Repo dir not found"; exit 1; }

OUTPUT_PDF="${INPUT_MD// /_}"
OUTPUT_PDF="${OUTPUT_PDF%.md}.pdf"

echo "Watching $INPUT_MD for changes in $REPO_DIR..."

while inotifywait -e close_write "$INPUT_MD"; do
    echo "Change detected. Converting $INPUT_MD to PDF..."
    pandoc "$INPUT_MD" -o "$OUTPUT_PDF" \
      --pdf-engine=xelatex \
      --template="$TEMPLATE" \
      --lua-filter="$LUA_FILTER" \
      --toc

    echo "Conversion complete: $OUTPUT_PDF"

    # Git add, commit, push
    git add "$INPUT_MD" "$OUTPUT_PDF"
    COMMIT_MSG="Auto update: $(date +"%Y-%m-%d %H:%M:%S")"
    git commit -m "$COMMIT_MSG"
    git push

    echo "Changes pushed to GitHub."
done
