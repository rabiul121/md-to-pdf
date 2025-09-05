#!/bin/bash


# Variables (match convert_to_pdf.sh)
INPUT_MD="input.md"
TEMPLATE="/media/robi/Robi/Linux/md-to-pdf/template.tex"
LUA_FILTER="multi-lang-font-filter.lua"
OUTPUT_DIR="./output"
OUTPUT_PDF="$OUTPUT_DIR/output.pdf"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

echo "Watching $INPUT_MD for changes..."

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
