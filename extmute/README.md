# docker-controller-bot — extmute

This is [dgongut/docker-controller-bot](https://github.com/dgongut/docker-controller-bot) with one patch added back: you can mute the bot from the command line, the way you could in 4.x. The image is published as `xorguy/docker-controller-bot-cli`.

## Muting from a script

A script writes the epoch second the mute should end at into `/app/config/.muted_until`:

```sh
docker exec docker-controller-bot sh -c 'echo $(( $(date +%s) + 3600 )) > /app/config/.muted_until'   # mute for 1 h
docker exec docker-controller-bot sh -c 'echo 0 > /app/config/.muted_until'                           # unmute
```

- Every 5 seconds the bot checks for the file, applies it and deletes it.
- **The file always wins.** It replaces any mute already in force, whether that mute is longer or shorter. A time in the past, or `0`, unmutes the bot.
- The time is capped at the same limit `/mute` has.
- If extended messages are on, the bot confirms the mute in Telegram.
- If your install still uses the 4.x `/app/schedule` volume, the bot also accepts the file there.
- If the bot is stopped when the file is written, it is read once at the next start. In that one case, it does not replace a mute that is already in force.

The patch lives in `core.py`, between the `# --- extmute` markers, plus the call to `start_external_mute_watcher()`. Its tests are in `tests/test_extmute.py`.

## Branches and tags in the fork

| ref | content |
|---|---|
| `main` | an exact mirror of `upstream/main`, with nothing of ours |
| `extmute` | the latest upstream release plus the patch commit, and nothing else |
| `vX.Y.Z-extmute` | the tag the image is built from |

Remotes on the development machine:

```
origin    https://github.com/xorguy/docker-controller-bot-extmute.git
upstream  https://github.com/dgongut/docker-controller-bot.git   (push disabled)
```

## When upstream publishes a release

On the development machine, in this repository:

```sh
PYTHON=/path/to/venv/bin/python extmute/sync-upstream.sh          # rebase onto the newest upstream release
PYTHON=/path/to/venv/bin/python extmute/sync-upstream.sh 5.3.0    # or onto a specific one
```

The script:
1. Fast-forwards `main` to match upstream.
2. Rebases `extmute` onto the new release tag.
3. Runs the tests.
4. Pushes `extmute` and the `vX.Y.Z-extmute` tag.

If the rebase stops with a conflict, fix the files and run `git add` on them, then `git rebase --continue`. After that, run the script again with the version. `rerere` is on, so git replays a conflict resolution you have already done once.

## Building the image (on the build host)

What the build host needs:
- git
- Docker with buildx
- `docker login` done for `xorguy`
- QEMU, to build the other architecture: `docker run --privileged --rm tonistiigi/binfmt --install all`

Then:

```sh
curl -fsSLO https://raw.githubusercontent.com/xorguy/docker-controller-bot-extmute/extmute/extmute/build.sh
chmod +x build.sh
./build.sh            # newest v*-extmute tag → :X.Y.Z and :latest, for linux/amd64 and linux/arm64
./build.sh 5.2.0      # a specific one
./build.sh 5.2.0 --no-latest
```

`build.sh` clones the fork into `~/.cache/docker-controller-bot-extmute` and checks out the exact tag. It refuses to build if the code's `VERSION` doesn't match the tag, or if the patch is missing. You can override any of these with environment variables: `IMAGE`, `PLATFORMS`, `REPO_URL`, `WORKDIR`, `BUILDER`.

## Using the image

In your compose, swap `dgongut/docker-controller-bot` for `xorguy/docker-controller-bot-cli:latest` and map the `/app/config` volume:

```yaml
services:
  docker-controller-bot:
    image: xorguy/docker-controller-bot-cli:latest
    container_name: docker-controller-bot
    env_file: .env
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./config:/app/config
    restart: unless-stopped
```
