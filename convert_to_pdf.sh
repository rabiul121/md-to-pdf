#!/bin/bash


# Variables
INPUT_MD="input.md"
# Use absolute path for template.tex
TEMPLATE="/media/robi/Robi/Linux/md-to-pdf/template.tex"
LUA_FILTER="multi-lang-font-filter.lua"
OUTPUT_DIR="./output"
OUTPUT_PDF="$OUTPUT_DIR/output.pdf"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

echo "Converting $INPUT_MD to PDF..."
pandoc "$INPUT_MD" -o "$OUTPUT_PDF" \
  --pdf-engine=xelatex \
  --template="$TEMPLATE" \
  --lua-filter="$LUA_FILTER" \
  --toc

echo "Conversion complete: $OUTPUT_PDF"
