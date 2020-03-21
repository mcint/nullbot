#!/bin/bash
# TODO(keur): We are saving 0000.schema.[up|down].sql to create a migrations
# table. Might not be necessary with 9.1 exists syntax, but just to be safe.
#
# Note: Before running this, the user should run `createdb nullbot`.

die() {
  echo >&2 "$@"
  exit 1
}

[[ "$#" -eq 2 ]] || die "Required arguments: dbname [up|down]"

migrations=$(find ./migrations/*)
case $2 in
  "up")
    migrations=$(grep -E 'up.sql$' <<< $migrations | sort)
    ;;
  "down")
    migrations=$(grep -E 'down.sql$' <<< $migrations | sort --reverse)
    ;;
  *)
    die "Invalid argument. Valid arguments are: [up|down]"
    ;;
esac

for m in $migrations; do
  psql -d $1 -f $m
  [[ $? -ne 0 ]] && die "Error applying migration: $m"
done
