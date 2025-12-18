#!/bin/bash
# Start Metabase BI Tool
# Access at http://localhost:3000

cd "$(dirname "$0")"
export PATH="/opt/homebrew/opt/openjdk@21/bin:$PATH"
java -jar metabase/metabase.jar
