---
title: "Parallel streams in a small transformer"
date: "April 2026"
date_sort: "2026-04-01"
summary: "Two token streams in lockstep through one causal transformer. Whether the trunk routes information between them is measurable and large — and which operating modes the weights support is set by the training distribution, chosen at inference by how you pad."
tags: [streams, transformers, training distribution]
author: "tobelabs research"
---
Two token streams `W` and `V`, paired by some external alignment, advance in lockstep — bilingual sentence pairs, audio frames and transcript, code and comment. Can a single causal transformer consume both at every step and predict both, with each stream conditioning the other?

The minimal architecture is one Linear projection beyond a standard decoder. The interesting questions are whether the resulting model actually routes information between streams, and what training-distribution tricks unlock additional operating modes from the same weights.

## Representation

A pair `(W, V)` is two token sequences over a shared vocabulary, padded to the same length `L`. PAD is a sentinel; PAD targets are masked from the loss with `ignore_index = -1`.

Token embeddings are looked up per stream, concatenated along the channel dim, and projected to `D`:

```
e_W = wte(W_idx)                  # (B, L, D)
e_V = wte(V_idx)                  # (B, L, D)
x   = Linear_2D→D([e_W ; e_V])    # (B, L, D)
```

The trunk is standard causal: 6 blocks, dim 384, 6 heads, RoPE position keyed to step `t`, full attention window. Both streams share RoPE position by construction — `W[t]` and `V[t]` sit at the same phase. There is no separate "input" and "output"; both streams are both.

Two output heads project from the trunk's final hidden:

```
logits_W[t] = head_shared(h_t) + α · Δ_A(h_t)
logits_V[t] = head_shared(h_t) + α · Δ_B(h_t)
```

`α ∈ [0, 1]` is a buffer set per step. With `α = 1` from the start — the simplest schedule — `head_shared` and the two deltas all receive gradient at every position from both streams. Loss is the sum of two cross-entropies. Total parameters at this size: ~22M.

## Cross-stream coupling

Removing one stream at inference is the cleanest test of whether the trunk uses it. Train normally; at eval, replace one stream's tokens with PAD and measure the loss on the other.

| training regime | baseline W | W when V→PAD | Δ | baseline V | V when W→PAD | Δ |
|---|---|---|---|---|---|---|
| τ = 0, no blanking | 2.31 | 4.77 | **+2.46** | 1.83 | 3.63 | **+1.80** |

Removing the other stream costs 1.5–2.5 nats per token, comparable to the gap between a trained and an undertrained model. The trunk routes information between streams; eliminate the source and the predictions collapse.

A second test replaces V with a *different* pair's V (well-formed, unaligned). W loses 1.3 nats — about half the full-removal penalty. Roughly half of the cross-stream signal is "this is the specific aligned sequence," the rest is "this is a V-shaped sequence at all."

## Operating modes via training distribution

The baseline model is brittle in two ways. It expects τ = 0 (synchronous), and it expects both streams non-blank at every example. Two perturbations to the training distribution each fix one, and they compose.

**Blanking.** With probability 0.4 per example, replace one entire side's input with PAD (50/50 between W and V). The model must predict the blanked side from the other alone. Loss on the blanked side is computed normally; the model gets direct gradient on the single-stream-from-the-other task.

**Signed delays.** A signed offset τ pads one stream's prefix:

- `τ > 0`  →  V gets τ leading PADs  (W leads, V follows — ASR-shaped)
- `τ < 0`  →  W gets `|τ|` leading PADs (V leads, W follows — TTS-shaped)
- `τ = 0`  →  synchronous

Sample τ uniformly per example from a symmetric set such as `{-16, -8, -4, -2, 0, 2, 4, 8, 16}`. RoPE positions still tick by step `t`; the leading PADs just mean the trailing stream has no informative content until later.

Training with both perturbations for 5000 steps:

| evaluation | baseline (τ = 0, no blank) | sym (signed τ + blank 0.4) |
|---|---|---|
| val loss sum at τ = 0, both streams present | 2.06 | 2.24 |
| Δ W when V → PAD | +2.46 | +0.20 |
| Δ V when W → PAD | +1.80 | +0.52 |
| Δ W at τ′ = +8 mismatch | +3.04 | +0.26 |
| Δ W at τ′ = −8 mismatch | untrained | −1.22 |

The cross-stream removal penalty drops by an order of magnitude. The delay-mismatch penalty changes sign: at negative τ, W loss decreases because its first-token predictions defer until V has accumulated context. Cost paid on canonical synchronous mode: +0.18 nats.

The same weights now operate in three regimes selected by inference-time padding alone — joint dual-stream prediction at `τ = 0`, W→V generation at `τ > 0` with V's content starting from PAD, V→W generation at `τ < 0` with W's content starting from PAD.

## Failure mode

Per-token cross-entropy says the model has learned to predict V from W and vice versa. Greedy autoregressive decode produces a fluent first sentence and degrades:

```
EN:  I told you not to call me on weekends.
REF: Je vous ai dit de ne pas m'appeler pendant les week-ends.
HYP: Je lui ai dit de ne pas m'appeler la semaine passée.
     Je ne suis pas prêt. Je n'en ai pas fini. ...
```

Classic teacher-forcing exposure bias: training only conditions on real `V_t` at every step, never on `V_t` produced by the model itself. The loss numbers are honest about next-token capability; multi-step generation is a separate problem that scheduled sampling, sequence-level objectives, or sampling-and-scoring would address.

## What didn't matter

A symmetry-breaking schedule on `α` — start tied, gradually untie — was tested across multiple variants. At this scale it does not matter. Independent training of the two heads from step 0 (`α = 1 ∀t`) is tied with a hard 0→1 untying at the midpoint, and both beat a linear `α` ramp by a small constant margin. The schedule of head specialization is the wrong knob to turn. The right knob is the training distribution.

## Closing

> Two streams advancing in lockstep can be modeled by one causal transformer with one extra Linear at the input and one extra head at the output. Whether the trunk actually uses the other stream is measurable and large. Which operating modes the trained weights support is set by what the training distribution exposes them to. The same network can be joint LM, forward translator, reverse translator, or any delay-shifted variant — *the choice is made at inference by how the inputs are padded.*
