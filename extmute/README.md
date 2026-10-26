# docker-controller-bot — extmute

This is [dgongut/docker-controller-bot](https://github.com/dgongut/docker-controller-bot) with one patch added back: you can mute the bot from the command line, the way you could in 4.x. The image is published as `xorguy/docker-controller-bot-cli`.

## Muting from a script

A script writes the epoch second the mute should end at into `/app/config/.muted_until`:

```sh
docker exec docker-controller-bot sh -c 'echo $(( $(date +%s) + 3600 )) > /app/config/.muted_until'   # mute for 1 h
docker exec docker-controller-bot sh -c 'echo 0 > /app/config/.muted_until'                           # unmute
```

- Every 2 seconds the bot checks for the file, applies it through the same code as `/mute` (rounded up to the minute) and deletes it.
- `/mute` in Telegram works as usual. The script and Telegram share one mute: **the latest change wins**, whichever side it comes from, longer or shorter. `0` (or any past time) unmutes.
- The time is capped at the same limit `/mute` has.
- If extended messages are on, the bot confirms the mute in Telegram.
- If your install still uses the 4.x `/app/schedule` volume, write the file there instead.
- If the bot is stopped when the file is written, it is read once at the next start. In that one case, it does not replace a mute that is already in force.

The patch is in `src/core.py`, right after `check_mute()` (`check_external_mute()`, `_external_mute_loop()`), plus the thread started in `main()`. Its tests are in `tests/test_extmute.py`. It is also proposed upstream as a pull request, from branch `extmute-pr`.

## Branches and tags in the fork

| ref | content |
|---|---|
| `main` | an exact mirror of `upstream/main`, with nothing of ours |
| `extmute` | the latest upstream release plus the patch commit and the tooling commit (`extmute/`) |
| `extmute-pr` | `main` plus the patch commit only: the upstream pull request |
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
