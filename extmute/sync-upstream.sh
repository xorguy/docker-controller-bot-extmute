#!/usr/bin/env bash
# Moves the extmute patch onto a new upstream release and publishes it to the fork.
# Run on the development machine, in this repository. No image is built here.
#
#   extmute/sync-upstream.sh            rebase onto the newest upstream v* tag
#   extmute/sync-upstream.sh 5.3.0      rebase onto v5.3.0
#
# Remotes expected: origin = the fork, upstream = dgongut/docker-controller-bot.
# Tests run with $PYTHON (default python3), which needs requirements.txt installed.
# Afterwards, on the build host: ./build.sh <version>
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

[ -z "$(git status --porcelain)" ] || { echo "Working tree not clean" >&2; exit 1; }

git fetch upstream --tags --force
git fetch origin

if [ $# -ge 1 ]; then
	new_tag="v$1"
else
	# Releases only: no release candidates (v5.0.0_RC9c) nor our own -extmute tags.
	new_tag="$(git tag --list 'v[0-9]*' --sort=-v:refname | grep -Ev '_RC|-extmute' | head -n1)"
fi
git rev-parse -q --verify "refs/tags/$new_tag" >/dev/null || { echo "No tag $new_tag" >&2; exit 1; }

if git rev-parse -q --verify "refs/tags/${new_tag}-extmute" >/dev/null; then
	echo "${new_tag}-extmute already exists: nothing to do"
	exit 0
fi

# The upstream release the patch sits on now: the newest release tag that is
# an ancestor of extmute.
old_tag=""
for t in $(git tag --list 'v[0-9]*' --sort=-v:refname | grep -Ev '_RC|-extmute'); do
	if git merge-base --is-ancestor "$t" extmute; then old_tag="$t"; break; fi
done
[ -n "$old_tag" ] || { echo "Cannot tell which release extmute is based on" >&2; exit 1; }

echo "Moving extmute from $old_tag to $new_tag"

# main mirrors upstream, nothing else.
git switch main
git merge --ff-only upstream/main
git push origin main

git switch extmute
# rerere replays conflict resolutions already done once.
git config rerere.enabled true
if ! git rebase --onto "$new_tag" "$old_tag" extmute; then
	echo
	echo "Conflict. Fix the files, then: git add <files> && git rebase --continue"
	echo "and run this script again with: $0 ${new_tag#v}"
	exit 1
fi

"${PYTHON:-python3}" tests/run_all.py

git push --force-with-lease origin extmute
git tag -a "${new_tag}-extmute" -m "${new_tag} with the command-line mute"
git push origin "${new_tag}-extmute"

echo
echo "Done. On the build host: ./build.sh ${new_tag#v}"
