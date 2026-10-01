# Cutting a release

Four commands from a tag to a signed, public release. The order matters and
the reason for each is below it.

## 1. Move every documented version

```
python3 scripts/set_version.py 0.1.7 --dry-run
python3 scripts/set_version.py 0.1.7
git add -A && git commit
```

It finds the documents rather than keeping a list of them: any tracked
markdown carrying a download instruction. The list it used to keep was three
names long, and on 5 September it could not see `docs/MINE.md` — eight
download commands — nor `deploy/systemd/laptop/README.md`, which had been
telling readers to fetch v0.1.4 for two releases after those files were
withdrawn.

It rebuilds every site page whose source moved. `check_docs_version.py` will
fail until the release exists; that is the correct order, because the
documents name the tag and the tag is built from the documents.

## 2. Tag, and say if it is mandatory

```
git tag -a v0.1.10 -F posts/v0.1.10/TAG_MESSAGE.txt
git push origin main && git push origin v0.1.10
```

The annotated tag message becomes the release notes.

**Write it in `posts/<version>/TAG_MESSAGE.txt` and read what the bot would
send before tagging.** `bots/announce.js` posts the first whole paragraphs
that fit in twelve lines to Telegram and Discord the moment the release is
published, with nobody reviewing it in between — so the first two paragraphs
have to stand alone to a reader who sees nothing else. Render it rather than
imagining it:

```
node -e "
const A = require('./bots/announce.js');
const { toDiscord } = require('./bots/lib/markup.js');
const txt = require('fs').readFileSync('posts/v0.1.10/TAG_MESSAGE.txt','utf8');
const body = txt.split('-'.repeat(78))[1].replace(/^\n+/, '');
console.log(toDiscord(A.releaseMessage({ tag:'v0.1.10', name:'WAM Coin v0.1.10',
  url:'https://wamcoin.org/downloads/',
  body, prerelease:true })));
"
```

Until v0.1.10 the bot cut the notes at line twelve wherever that fell, and
every release this project published was announced mid-sentence — twice
mid-word. It now stops at a paragraph and says when it left some behind, but
the first paragraphs are still the whole message most people will read.

**Then check that those paragraphs name everything new, which is a different
question from whether they read well:**

```
python3 scripts/test/test_announcement_covers_release.py posts/v0.1.12/TAG_MESSAGE.txt
```

v0.1.11 shipped the first graphical wallet this project ever built. The tag
message described it, with its three file names — below the twelve lines the
bot sends. So the channels were told about a mining fix and nothing else, and
a community member filled the silence by building a wallet of his own and
posting a download link in the chat, which had to be stopped and publicly
disowned.

The render above was run before that tag, and read for shape: whole
paragraphs, no sentence cut in half. It was not read for coverage. That is why
the coverage question is a command and not a sentence in this document.

**If the release changes a consensus rule, the tag message must contain a
line beginning `MANDATORY:`.** The workflow copies it to the top of the
notes, where the announcer finds it and posts the release as UPDATE REQUIRED
rather than as news. v0.1.5 moved the mainnet treasury address; a node left
on v0.1.4 rejects every valid block on launch day and forks itself off at
height 1, silently, still running and still mining, alone.

Nothing checks whether you should have written that line. It is the one
judgement in this document.

## 3. The workflow builds — and publishes a DRAFT

`.github/workflows/release.yml` runs on a clean ubuntu-22.04 runner, applies
`patch_upstream.py`, builds node, RandomX and miner, packages, verifies the
tarball's own checksums, and creates the release **as a draft**.

**The runner cannot sign anything.** The signing key is offline, on a USB
stick. `package_release.sh` signs only when that key is on the machine, and
on a GitHub runner it never is.

Before this was a draft, every release went public unsigned and stayed that
way until somebody noticed. For that whole window, anyone following our own
instructions saw:

```
FAIL  SHA256SUMS.asc is not here -- that file IS the proof.
      A release without it cannot be checked. Do not run the binaries.
```

Which is correct, and is the exact thing we spent 5 September making sure a
stranger would never see about a good release. How long that window lasted
for v0.1.6 is unknown, because nothing measured it.

A draft is not downloadable and does not appear on the releases page.

## 3b. The Windows and macOS archives, which the tag does not build

From v0.1.8 a release carries Windows as well as Linux, and `release.yml`
builds neither Windows nor macOS. They come from `platform-build`, which is
run by hand:

* Actions → **platform-build** → **Run workflow**, with `Version` set to the
  same version as the tag

**Both jobs now gate on `--solo` as well as on consensus.** Each starts a
regtest node with the platform's own `wamd`, runs `wam-miner --check` against
it, and mines two blocks with `--solo` that the node must accept with the
reward arriving at the address given. If that fails on Windows or macOS, the
artifact does not exist and there is nothing to attach — which is the point:
before v0.1.10 both options were proved on one Linux laptop and shipped to
the other two platforms untested.
* when it is green, download **both** artifacts from the bottom of the run
  page — `wam-windows-x86_64` and `wam-macos-arm64`. Each holds finished
  archives, not loose binaries
* unzip them into the same directory as the Linux files

**Tick `Also build the graphical wallet` if this release carries one**, or
push to a branch named `platform/gui-…` which means the same thing. Without
it the run produces a node and a miner and no `wam-qt-…` archive at all, and
the omission is silent: the release simply ships without a wallet on the two
platforms that have no other way to get one.

**Then add them to the list before signing, and compute the lines rather than
typing them:**

```
cd ~/Downloads/wam-v0.1.11
sha256sum wam-*-v0.1.11-x86_64-w64-mingw32.zip \
          wam-*-v0.1.11-arm64-apple-darwin.tar.gz >> SHA256SUMS
```

The glob is deliberate and replaced two typed file names. Those two were
written when a platform shipped a node and a miner; from v0.1.11 it also
ships `wam-qt-…`, and a list of names typed out by hand goes stale every
time the set grows — which is the same failure this whole section exists to
prevent, one level up. `wam-*` takes whatever the platform build actually
produced.

Check what it appended before going further:

```
tail -6 SHA256SUMS
```

Six lines: a node, a miner and a wallet for each of Windows and macOS. If a
wallet line is missing, the platform build ran without the GUI switch and
the wallet has to be built before the release is signed, not after.

This is the step that would be easiest to skip and the one whose absence does
the most damage. `SHA256SUMS.asc` is a signature over `SHA256SUMS` and nothing
else, so a Windows archive that is not named in that file has **no signed
proof at all** — a Windows user running `verify_release.sh` would be told
`OK` about two Linux tarballs he did not download, while the `.zip` he did
download is covered by nothing. A release nobody can verify is the one thing
this project has said repeatedly it will not publish, and it would be
published to the platform most people are on.

Nothing here trusts the hashes in `package_platform.sh`'s output either. They
are printed for reading; the line above recomputes them from the files on
disk, and `sign_release.sh` then verifies every line in the list against
every file before it will sign. A typo cannot survive that, and a swapped
file cannot either.

## 4. Sign it, then publish it

On the machine with the USB stick. **Git Bash, not PowerShell** — PowerShell
has no `gpg` on PATH; the one that works is
`C:\Program Files\Git\usr\bin\gpg.exe`, which is what Git Bash runs.

From the draft release page, download `SHA256SUMS` and **every package** into
one empty directory — the Linux archives, plus the Windows and macOS ones
from §3b. From v0.1.11 that is a node, a miner and a wallet for each of the
three platforms: nine files, and `sign_release.sh` refuses to sign until
every one of them is present and hashes to the line written beside it. Then,
after the `sha256sum … >> SHA256SUMS` line in §3b has been run:

```
bash scripts/sign_release.sh ~/Downloads/wam-v0.1.7
```

It refuses to sign until every file named in `SHA256SUMS` is present and
hashes to the value written beside it, checks that the version in the names
is the version this checkout builds, imports the key into a keyring created
on the USB and destroyed on exit, and verifies its own signature in a
throwaway keyring against the published fingerprint before it says it is
done.

Upload the `SHA256SUMS.asc` it writes, and take the release out of draft, from
the release page in a browser: **Edit release** → drag the file into the
attachments → **Publish release**.

### Why not `gh`

This document used to say:

```
gh release download v0.1.7 -p SHA256SUMS
gpg --detach-sign --armor SHA256SUMS
gh release upload v0.1.7 SHA256SUMS.asc
gh release edit v0.1.7 --draft=false
```

`gh` is not installed on the machine that holds the key, so the procedure
stopped at its first line — discovered while cutting v0.1.7, with the draft
already built and waiting.

The second line is the worse one. `SHA256SUMS` is not the release; it is a
list of promises about the release, arriving over the network from a service
this project does not own. Signing it unread converts *GitHub handed me this
list* into *the founder personally vouches for these bytes*, which is the
exact sentence every reader of `verify_release.sh` is trusting. The key's
whole value is that it says something the network cannot say.

Installing `gh` would have fixed the first line and left the second one
standing.

Then check it as a stranger would — clean directory, empty keyring, nothing
but what the announcement says to fetch:

```
curl -LO https://wamcoin.org/downloads/v0.1.11/SHA256SUMS
curl -LO https://wamcoin.org/downloads/v0.1.11/SHA256SUMS.asc
curl -LO https://wamcoin.org/verify_release.sh
curl -LO https://wamcoin.org/SIGNING-KEY.asc
bash verify_release.sh .
```

It must print `ok` twice and exit 0. If it does not, the release is public and
broken: **Edit release → Save as draft** puts it back out of reach while you
find out why.

## 5. Afterwards

```
bash scripts/sweep.sh --nodes "169.58.159.165 5.223.52.200"
```

`published download is this network` and `the published release is signed`
both read the release page directly. They are the check that step 4 actually
happened, and they are why the sweep is worth running after a release rather
than before.

---

## Why the version is set before the tag, not after

`patch_upstream.py` carries `WAM_CLIENT_VERSION`, which is what the built
binary reports. The workflow refuses to publish if that string and the tag
disagree — so the documents, the source and the tag either all say v0.1.7 or
nothing ships. Setting the version afterwards would mean a binary that
reports one number sitting on a page that names another.
