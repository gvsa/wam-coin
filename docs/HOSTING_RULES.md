# What the hosts forbid, and the rules we keep on top of it

Two accounts of this project have been suspended five weeks apart. This file
exists so that the third one is not lost to a rule nobody here had read.

**2026-09-24.** A step in `platform-build.yml` mined two regtest blocks on a
GitHub runner. The account was suspended within the hour, and with it went the
repository, every release download, `raw.githubusercontent.com` and
`wamcoin.org` — all 404 to the public, on a release day. The chain was
worthless and the intent was a correctness proof. Neither is visible to an
abuse detector.

**2026-10-29.** The replacement account was suspended. **No reason was given
and no message was sent.** That is still true.

And on **2026-10-31** the gap where the second reason should be was filled
with a guess — that building on CI had caused it — a rule was built on the
guess, and the release pipeline was nearly deleted to honour it. The answer to
the first suspension had been sitting in this repository the whole time, in
the comment above the step that caused it.

So: read what they actually forbid, write it down, and stop inventing.

## What GitHub forbids in Actions

Read from
<https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features>
on 2026-10-31. The first four apply **whether or not the runner is
self-hosted**:

> * Cryptomining
> * Disrupting, gaining, or attempting to gain unauthorized access to, any
>   service, device, data, account, or network
> * The provision of a stand-alone or integrated application or service
>   offering the Actions product or service
> * Any activity that places a burden on our servers, where that burden is
>   disproportionate to the benefits provided to users

And on GitHub-hosted runners only:

> * any other activity unrelated to the production, testing, deployment, or
>   publication of the software project

**Read that last line the other way round and it is a permission.** Production,
testing, deployment and publication of the software project is what hosted
runners are *for*, and it is exactly and only what this project asks of them.
Building a release on CI was never the fault and is not one now. The line is
not between our machines and theirs. It is between work and **proof of work**.

## What GitHub forbids on the account

From <https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies>,
read the same day. The headings that could plausibly touch a project like this
one, with the operative words:

| Section | The words |
|---|---|
| Spam and Inauthentic Activity | "automated excessive bulk activity and coordinated inauthentic activity"; "rank abuse, such as automated starring or following" |
| Information Usage Restrictions | data from the Service must not be used "for spamming purposes, including for the purposes of sending unsolicited emails to users" |
| Advertising | a repository "should not be advertising or promotional marketing" |
| Excessive Bandwidth Use | GitHub "reserve[s] the right to suspend your Account, throttle your file hosting, or otherwise limit your activity" |
| Site Access and Safety | nothing that "uses our servers to disrupt or to attempt to disrupt" |
| Intellectual Property, Authenticity | nothing that "impersonates any person or entity" |

**Enforcement:** "GitHub retains full discretion to take action in response to
a violation of these policies, including account suspension." No advance
notice is promised, except before deleting a repository for bandwidth. There
is a **reinstatement and appeal** process, and it is the only way to be told a
reason.

## The rules, then

1. **No proof of work on anybody's hosted runner.** `wam-miner --check` builds
   a block and hashes nothing, and that is what CI gets. `--solo` mines, and
   runs only on hardware this project controls, through
   `scripts/test/test_platform_solo.sh`. *Enforced by `scripts/check_ci_mining.py`,
   in the sweep, over every vendor's CI definition and not only GitHub's.*
2. **CI does only what builds, tests, packages or publishes this project.** No
   errand that would run just as well on a laptop, no job kept alive to hold a
   machine, nothing unrelated to the software in this repository.
3. **Nothing automated is ever pointed at anyone else's account or
   repository.** Every listing request this project has opened was opened by
   hand, one venue at a time, and that is not a style — it is this rule. No
   scripted stars, follows, issues or comments, anywhere, for any reason.
4. **No bulk mail, and no contact list built from the platform.** Anybody who
   writes to us is answered; nobody is written to because their address was
   scraped.
5. **One identity.** A second account is never created to get around a limit,
   a suspension, or a rate. When an account is lost, the work moves to a named
   successor and the signed channel list says so.
6. **The heavy or the long job runs on our machines.** Not because the hosts
   forbid it, but because a burden "disproportionate to the benefits provided
   to users" is judged by them and not by us, and that is a judgement not
   worth standing under.
7. **If an account is suspended, appeal, and write the answer here.** Both
   suspensions were survived by guessing. A guess is how a rule gets invented
   that costs more than the fault did.

## The account itself

Measured 2026-10-31 against `wamcoin-Project`:

| | state | |
|---|---|---|
| organisation 2FA requirement | **off** | should be on |
| owners | **one** | if that account goes, the organisation goes with it |
| default repository permission | read | correct |
| Actions on our own repository | disabled | a setting, not a guarantee — rule 1 is the guarantee |

Two-factor authentication on the account itself cannot be read with the token
this project uses, which is correct: the token has `repo`, `workflow`,
`read:org` and `gist`, and `gist` is not used by anything here.

**The single owner is the same shape of fault as the single source
repository was before revision 4 of `CHANNELS.txt`, and as the single domain
was before revision 5.** It has not been fixed here because adding an owner is
a decision about a person, not about infrastructure.

## What is still not known

Why the second account was suspended. GitHub sent nothing, and the
reinstatement and appeal form is the only thing that can answer it. Until it
does, **nothing in this file claims to explain 2026-10-29**, and no rule here
is justified by it.
