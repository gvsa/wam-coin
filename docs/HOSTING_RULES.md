# What the hosts forbid, and the rules we keep on top of it

Two accounts of this project have been suspended five weeks apart. This file
exists so that the third one is not lost to a rule nobody here had read.

**2026-09-24.** A step in `platform-build.yml` mined two regtest blocks on a
GitHub runner. The account was suspended within the hour, and with it went the
repository, every release download, `raw.githubusercontent.com` and
`wamcoin.org` — all 404 to the public, on a release day. The chain was
worthless and the intent was a correctness proof. Neither is visible to an
abuse detector.

**2026-10-29.** The replacement account was suspended. GitHub sent no message
and gave no reason — but the reason was watched happening. A workflow was
started, it failed, and it was started again. Once, twice, three times, with
nothing changed between the runs. That is the fourth item in their Actions
list, word for word: a burden *"disproportionate to the benefits provided to
users"*. Nothing new could come out of a repeated run, and a detector counts
runs and cannot see an intention.

And on **2026-10-31**, before that had been said aloud, the gap was filled
here with a different guess — that building on CI had caused it — a rule was
built on the guess, and the release pipeline was nearly deleted to honour it.

**Both answers were already held by somebody.** The first was in this
repository, in the comment above the step that caused it. The second was in
the founder's memory, and nobody asked him.

So: read what they forbid, ask what was seen, write both down, and stop
inventing.

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
7. **A failing job is read, not repeated.** The log is read, the failure is
   reproduced on a machine of ours — `build_linux.sh`, `build_windows.sh` and
   the test scripts all run without a runner — fixed, and run again once.
   A single retry for a genuine flake is a retry; the third run of one
   workflow against one commit is what was being done when the second account
   went. *Counted by `scripts/check_ci_reruns.py`, in the sweep. It cannot
   stop the click. It reads the count before the next release instead of
   after the next suspension.*

## The account itself

Measured 2026-10-31 against `wamcoin-Project`:

| | state | |
|---|---|---|
| organisation 2FA requirement | **off** | should be on |
| owners | **one** | one pair of hands — and no defence at all against the organisation itself being suspended |
| default repository permission | read | correct |
| Actions on our own repository | disabled | a setting, not a guarantee — rule 1 is the guarantee |

Two-factor authentication on the account itself cannot be read with the token
this project uses, which is correct: the token has `repo`, `workflow`,
`read:org` and `gist`, and `gist` is not used by anything here.

**An owner is not a way back, and the first draft of this file implied that
it was.** The failure that has happened twice is not "the person holding the
account was lost". It is the account, and everything under it, being
suspended in one motion. **An organisation with ten owners that is itself
suspended is suspended.** Nothing held inside a host defends against the
host.

What does defend against it is already built, and it has now worked twice:
the repository is published at three companies, and each suspension took one
of the three. GitLab and Gitea were untouched on both days, and the signed
`CHANNELS.txt` sends people to a domain rather than to any account.

So a second owner is worth having for two smaller and truer reasons. One: a
person can be unreachable, ill, or away, and a single pair of hands is a
single point of failure in time rather than in infrastructure. Two, and
larger: a project that says a coin must not sit in few hands cannot answer
for a repository that sits in one.

The founder's decision, 2026-10-31: **a second owner when a developer has
built something and proved himself**, and the wallet now being written is
that proof. Not a title handed out in advance.

## What was decided, and what is not known

**No appeal.** GitHub's reinstatement form exists and the founder's judgement
on 2026-10-31 was that it returns the same letter and reopens nothing. The
answer the appeal would have been asked for is already in this file, from
somebody who saw it. If they reopen an account unasked, that is their
business.

**A way back exists.** There is a second account, held separately. The rule
that matters is 5: a second account is never made to get around a suspension
— it is there so that a lost account does not end the project, and the signed
`CHANNELS.txt` is what says which name is ours.

**Still not known:** nothing that changes a rule here. GitHub never stated a
cause for 2026-10-29, and this file does not pretend their silence is
agreement — it records what was observed, says who observed it, and leaves
the two apart.
