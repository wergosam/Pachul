#!/bin/bash
BASE=3f74087248271f283293eab9ace538b1170c3c50
git ls-tree -r --name-only $BASE | while read -r f; do
  if [ ! -f "$f" ]; then echo "0 0 $f (gelöscht/umbenannt)"; continue; fi
  orig=$(git show "$BASE:$f" | wc -l)
  del=$(git diff --numstat $BASE HEAD -- "$f" | cut -f2)
  [[ "$del" =~ ^[0-9]+$ ]] || continue
  echo "$((orig-del)) $orig $f"
done | tee /tmp/rest.txt
awk '{u+=$1; o+=$2} END {printf "Unverändert: %d von %d Originalzeilen (%d %%)\n", u, o, 100*u/o}' /tmp/rest.txt
