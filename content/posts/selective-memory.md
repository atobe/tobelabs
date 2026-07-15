---
title: "Learning what to keep: selective memory in a streaming transformer"
date: "May 2026"
date_sort: "2026-05-01"
summary: "A bounded scratchpad and a learned commit policy. It matches an oracle's recall and is sharply selective — but only once the backbone's representation can express relevance, and only generalizes when the training distribution makes memorization too expensive."
tags: [memory, representations, training distribution]
author: "tobelabs research"
---
A streaming language model with a fixed attention window forgets by construction. Tokens fall off the back; whatever wasn't carried forward is gone. The usual response is to grow the window or bolt on a retrieval index. The other response — the one this note is about — is to give the model a small, bounded scratchpad and make *what to write into it* a learned decision. The interesting question is not whether such a policy can be expressed, but whether it can be learned, and what exactly gets learned when it is.

The short answer: a learned commit policy reaches the same recall as a hand-built oracle (1.00) and is sharply selective about what it keeps — but only after you let the backbone's representation change, and only learns a *reusable* policy when the training distribution makes memorization more expensive than the underlying skill.

## Setup

The substrate is an 18M-parameter decoder with sliding-window attention (window 256, 8 layers). The window is a hard causal mask: position `t` attends to `[t-255, t]` and nothing earlier. On top of it sits a bounded buffer of `K` slots and a per-token commit head. As the sequence streams, each position produces a hidden `h_t`; the commit head emits `c_t ∈ {0,1}`; on `c_t = 1` the hidden is written into a FIFO ring of the last `K` committed hiddens. At a query position the buffer is read by cross-attention and a small head classifies the answer.

The task is recall after forced eviction. Each episode states a topic, then streams one *on-topic* fact and several *off-topic* facts of identical surface form, separated by enough filler that every fact leaves the window before the query:

```
Topic: security.
... filler ... The security code is 47. ... filler ...
The shipping weight is 31. ... The reactor pressure is 88. ... (~400 tokens) ...
Question: what is the security code? Answer: 47
```

By the time the query arrives, "47" is ~390 tokens back — outside the window. The query hidden cannot see it. The only path from fact to answer is the buffer. So recall measures exactly one thing: did the policy commit the right token and protect it from eviction?

*Two choices matter here and are easy to get wrong. Values are single tokens (0–99), so recall is a clean 100-way readout rather than a string-reconstruction problem. And the buffer stores per-token hiddens, not pooled spans: a fact's value token is linearly decodable from its own hidden, but mean-pooling it with neighbors buries the signal. The "commit everything" baseline is not an oracle — under FIFO it keeps the most recent `K` tokens, which are filler, and recalls at chance. The oracle commits only the on-topic fact.*

## The wall: a frozen backbone has no relevance signal

Freeze the backbone and train only the memory machinery. An oracle that commits the on-topic fact recalls at 0.99. Every *learned* policy — gradient through the commit head, with or without RL — sits at chance (~0.01).

A linear probe on the frozen hidden says why. Two properties, two outcomes:

| probe target | what kind of property | linear decodability |
|---|---|---|
| the value ("47") | local, token identity | **1.00** |
| on-topic-ness (matches the cued topic?) | relational, fact ↔ earlier cue | **0.53** (chance) |

The value is fully present in the representation. Whether a fact is *relevant to a topic stated a few hundred tokens earlier* is not — that is a relational computation the generic language model was never trained to expose. A per-token commit head reading that hidden has nothing to be selective on. The bottleneck is representational, and it sits upstream of any policy-learning method. No reward shaping fixes a feature that isn't there.

## Fixing the representation

Let the representation learn. Insert LoRA adapters (rank 16, ~424K parameters) on the attention and MLP projections; keep the base weights frozen; train the whole pipeline — adapters, commit head, buffer read, answer head — end to end.

The wall comes down. The learned policy now recalls at 1.00 and is genuinely selective: it commits on-topic tokens at rate 1.00 and off-topic tokens at 0.13, a 7.7× ratio. Re-running the relevance probe on the *adapted* hiddens: 0.53 → 1.00. The adapters moved relevance from absent to linearly present, and that is precisely what lets the policy discriminate.

Two controls keep this honest.

**Cue-dependence.** Remove the topic line and retrain. Selectivity collapses to exactly 1.0 — with no observable cue, on-topic and off-topic facts are indistinguishable at commit time, so the policy commits them equally. (Recall holds at 0.26 rather than chance: without the cue the policy still learns the weaker fact-versus-filler distinction, keeps the last few fact tokens, and the on-topic one survives by luck. It can keep *facts*; it just can't pick *which*.)

**No smuggling.** Stacked sliding-window attention has a receptive field of `layers × window` = 2048 tokens — wider than the fact-to-query gap. Adapters could in principle learn to walk the fact forward through that depth and bypass the buffer entirely. To rule it out: zero the buffer at read time. Recall drops to 0.011 (chance). The value reaches the query only through the buffer; the comparison is clean.

*The commit head is trained by imitation: an oracle that commits the on-topic tokens supplies the target, and the head and adapters fit it jointly. Imitation sidesteps a sparse signal — a policy initialized blind almost never commits the ~6 relevant tokens out of ~400, so a pure reward is ~0 and carries no gradient. What this establishes is narrow and exact: selectivity is learnable once the representation can express relevance. Discovering the same policy from reward, without oracle labels, is a different problem and not the one answered here.*

## Skill or lookup?

Recall 1.00 and 7.7× selectivity admit two readings. The adapters could have learned the general operation — *commit the fact whose topic matches the cue* — or memorized a detector per training topic. The first transfers to any topic; the second transfers to nothing.

Separate them with held-out topics: train on one set of topic words, evaluate zero-shot on a disjoint set that never appeared in training, not even as distractors.

| training set | in-distribution | held-out (zero-shot) |
|---|---|---|
| 8 topics | 6.9× | **1.08×** |
| 60 topics | 12× | **4.9×** (recall 0.83) |

With eight topics, memorizing eight detectors is the cheaper solution, and gradient takes it: on unseen words the policy is indiscriminate (1.08×). With sixty procedurally-sampled topics, per-topic lookup is infeasible, and the policy learns the actual cue↔fact comparison — which transfers zero-shot to twenty words it has never seen (4.9×, recall 0.83, against a lookup floor of 1.08×). Same architecture, same objective; the only change is the diversity of the training distribution.

## Tradeoffs and limits

The buffer is the whole point and also the constraint: `K` slots of `d`-dim hidden is a hard budget, and a FIFO discards by age, not by value. The policy must protect what matters by *not* committing the rest — which is why selectivity, not commit rate, is the quantity that moves recall. The readout is classification over a closed value set; open-vocabulary recall would need a sequence decoder and reintroduces the storage-fidelity question pooling raised.

## Closing claim

> What a memory policy learns is set by the economics of the training distribution, not by the architecture alone. Give it few enough situations and it will memorize them; the policy looks selective and transfers to nothing. Remove the shortcut and the same network, same objective, learns the relational operation underneath — *but only after the representation is allowed to change*, because the relevance signal selectivity depends on is not present in a frozen generic backbone, while the content it ultimately recalls always is.
