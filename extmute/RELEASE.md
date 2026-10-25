# Releasing extmute for a new dgongut release

Follow these steps each time [dgongut/docker-controller-bot](https://github.com/dgongut/docker-controller-bot/releases) publishes a release.

The patch is one commit at the tip of the `extmute` branch. Releasing it means three things:
1. Move that commit onto the new upstream tag.
2. Tag the result `vX.Y.Z-extmute`.
3. Build `xorguy/docker-controller-bot-cli:X.Y.Z` and `:latest` from that tag.

In the steps below, `X.Y.Z` is the new upstream version, for example `5.3.0`.

## 0. One-time setup

**Development machine** (this repository):

```sh
git remote -v
# origin    https://github.com/xorguy/docker-controller-bot-extmute.git
# upstream  https://github.com/dgongut/docker-controller-bot.git  (push: DISABLED)

# Only if they don't look like that:
git remote add upstream https://github.com/dgongut/docker-controller-bot.git
git remote set-url --push upstream DISABLED
git config rerere.enabled true          # git replays conflict resolutions it has seen before

# Python for the tests
python3 -m venv ~/.venvs/dcb && ~/.venvs/dcb/bin/pip install -r requirements.txt
```

**Build host** (`pi@172.26.30.167`), already set up:
- Docker 29 with buildx
- QEMU for arm64 (`/proc/sys/fs/binfmt_misc/qemu-aarch64`)
- `docker login` done

If you ever rebuild that host, set it up again with:

```sh
docker run --privileged --rm tonistiigi/binfmt --install arm64
docker login -u xorguy
```

## 1. Move the patch onto the new release (automatic)

```sh
PYTHON=~/.venvs/dcb/bin/python extmute/sync-upstream.sh X.Y.Z
```

Leave out `X.Y.Z` to use the newest upstream release. The script:
1. Fetches upstream and fast-forwards `main` to match it, then pushes `main`.
2. Runs `git rebase --onto vX.Y.Z <previous release> extmute`.
3. Runs the full test suite.
4. Pushes `extmute` and the tag `vX.Y.Z-extmute`.

If it ends with `Done.`, go to step 3.

## 2. If the rebase stops with a conflict

The conflict is almost always in `core.py`, because upstream changed the code around one of the patch's two places:
- **The block** between `# --- extmute: mute from the command line` and `# --- end extmute`. It sits right after `def check_mute():`.
- **The line** `start_external_mute_watcher()  # extmute`. It sits right after `check_mute()` in the startup code at the bottom of the file.

To resolve it:

```sh
git status                         # lists the conflicted files
# edit each one: keep upstream's version of their code, plus the extmute block and line
git add core.py
git rebase --continue
PYTHON=~/.venvs/dcb/bin/python extmute/sync-upstream.sh X.Y.Z   # finishes: runs tests, pushes, tags
```

If the rebase is a mess, you can start over:

```sh
git rebase --abort
```

Then apply the patch by hand on top of the new release:

```sh
git switch -c extmute-new vX.Y.Z
git cherry-pick extmute            # or: git show extmute | git apply -3
# resolve, run the tests, then replace the branch:
git branch -f extmute extmute-new && git switch extmute && git branch -D extmute-new
PYTHON=~/.venvs/dcb/bin/python extmute/sync-upstream.sh X.Y.Z
```

Check these things whenever upstream changes:
- The names the patch uses still exist in `core.py`: `_mute_until`, `is_muted`, `unmute`, `_mute_lock`, `_unmute_timer`, `send_message`, `get_text("muted"…)`, `MUTE_MAX_MINUTES`, `store.root()`, `store.CONFIG_ROOT` and `store.state_set("mute_until", …)`. The tests in `tests/test_extmute.py` fail if any of them changed.
- `test_extmute` is still listed in `MODULES` in `tests/run_all.py`.
- `extmute/Dockerfile`, compared with upstream's `Dockerfile`. Upstream may change the base image (`BASE_IMAGE`), the `apk` packages, the `HEALTHCHECK` or the ssh config. Copy those changes over. Diff it with:
  ```sh
  git diff vPREV..vX.Y.Z -- Dockerfile
  ```

## 3. Build and publish the image

From the development machine:

```sh
ssh pi@172.26.30.167 'curl -fsSL https://raw.githubusercontent.com/xorguy/docker-controller-bot-extmute/extmute/extmute/build.sh | bash -s -- X.Y.Z'
```

Or log in to the build host and run it there:

```sh
ssh pi@172.26.30.167
curl -fsSLO https://raw.githubusercontent.com/xorguy/docker-controller-bot-extmute/extmute/extmute/build.sh && chmod +x build.sh
./build.sh X.Y.Z               # pushes :X.Y.Z and :latest for linux/amd64 + linux/arm64
./build.sh X.Y.Z --no-latest   # leaves :latest where it is
```

`build.sh` clones or updates the fork in `~/.cache/docker-controller-bot-extmute` and checks out `vX.Y.Z-extmute`. It refuses to build if:
- `VERSION` in `core.py` is not `X.Y.Z`, or
- the patch is missing.

Building arm64 under QEMU takes a few minutes.

## 4. Check the image

```sh
docker buildx imagetools inspect xorguy/docker-controller-bot-cli:X.Y.Z   # shows linux/amd64 and linux/arm64
```

Then, on the host running the bot:

```sh
docker compose pull && docker compose up -d
docker exec docker-controller-bot sh -c 'echo $(( $(date +%s) + 120 )) > /app/config/.muted_until'
sleep 7; docker exec docker-controller-bot ls /app/config/.muted_until   # should be gone: consumed
docker logs docker-controller-bot 2>&1 | grep -i "muted from the command line"
```

To unmute:

```sh
docker exec docker-controller-bot sh -c 'echo 0 > /app/config/.muted_until'
```

## Fixing the patch itself (no new upstream release)

Change the patch in place, so it stays a single commit:

```sh
git switch extmute
# edit, then run the tests:
~/.venvs/dcb/bin/python tests/run_all.py
git commit -a --amend --no-edit
git tag -fa vX.Y.Z-extmute -m "vX.Y.Z with the command-line mute"
git push --force-with-lease origin extmute && git push --force origin vX.Y.Z-extmute
```

Then build as in step 3. `build.sh` uses `fetch --force --tags`, so it picks up the moved tag.
