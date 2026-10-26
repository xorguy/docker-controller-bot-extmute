#!/usr/bin/env bash
# Builds and pushes the extmute image (linux/amd64 + linux/arm64) to Docker Hub.
# Meant for the build host; needs git, docker with buildx, and `docker login`.
#
#   ./build.sh                 build the newest v*-extmute tag
#   ./build.sh 5.2.0           build v5.2.0-extmute
#   ./build.sh 5.2.0 --no-latest   do not move :latest
#   ./build.sh --local         build the working tree it sits in, as is
#
# Run from anywhere: without --local it clones (or updates) the fork into
# $WORKDIR and builds the exact tag, so the build host needs nothing else.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/xorguy/docker-controller-bot-extmute.git}"
IMAGE="${IMAGE:-xorguy/docker-controller-bot-cli}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
WORKDIR="${WORKDIR:-$HOME/.cache/docker-controller-bot-extmute}"
BUILDER="${BUILDER:-dcb-multiarch}"

version=""
latest=1
local_tree=0
for arg in "$@"; do
	case "$arg" in
		--no-latest) latest=0 ;;
		--local) local_tree=1 ;;
		-h|--help) sed -n '2,12p' "$0"; exit 0 ;;
		*) version="$arg" ;;
	esac
done

if [ "$local_tree" -eq 1 ]; then
	src="$(cd "$(dirname "$0")/.." && pwd)"
else
	if [ -d "$WORKDIR/.git" ]; then
		git -C "$WORKDIR" fetch --force --tags --prune origin
	else
		git clone "$REPO_URL" "$WORKDIR"
	fi
	src="$WORKDIR"
	if [ -z "$version" ]; then
		tag="$(git -C "$src" tag --list 'v*-extmute' --sort=-v:refname | head -n1)"
		[ -n "$tag" ] || { echo "No v*-extmute tag in $REPO_URL" >&2; exit 1; }
	else
		tag="v${version}-extmute"
	fi
	git -C "$src" -c advice.detachedHead=false checkout --force "$tag"
fi

# The version the code says it is, so the image tag cannot disagree with it.
core="$src/src/core.py"
code_version="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$core")"
[ -n "$code_version" ] || { echo "Could not read VERSION from $core" >&2; exit 1; }
if [ -n "$version" ] && [ "$version" != "$code_version" ]; then
	echo "Asked for $version but $core says $code_version" >&2
	exit 1
fi
version="$code_version"

grep -q "target=_external_mute_loop" "$core" \
	|| { echo "The extmute patch is not in $core: refusing to build" >&2; exit 1; }

# A docker-container builder is what can build for several platforms at once.
# Emulating arm64 on an amd64 host (or the other way) also needs QEMU:
#   docker run --privileged --rm tonistiigi/binfmt --install all
if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
	docker buildx create --name "$BUILDER" --driver docker-container >/dev/null
fi

names=("$IMAGE:$version")
[ "$latest" -eq 1 ] && names+=("$IMAGE:latest")
tags=()
for name in "${names[@]}"; do tags+=(-t "$name"); done

echo "Building $IMAGE:$version for $PLATFORMS from $src ($(git -C "$src" rev-parse --short HEAD))"
docker buildx build \
	--builder "$BUILDER" \
	--platform "$PLATFORMS" \
	-f "$src/extmute/Dockerfile" \
	--build-arg VERSION="$version" \
	--build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
	--build-arg VCS_REF="$(git -C "$src" rev-parse HEAD)" \
	"${tags[@]}" \
	--push \
	"$src"

echo "Pushed: ${names[*]}"
