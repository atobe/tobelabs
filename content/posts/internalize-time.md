---
title: "Can a 10M-parameter language model internalize time?"
date: "June 2026"
date_sort: "2026-06-01"
summary: "A cheap auxiliary objective teaches a tiny LM to predict cumulative word timing within one frame — and a post-hoc inject probe shows the trunk's representations actually adapted, not just the head."
tags: [timing, representations, small models]
author: "tobelabs research"
---
A small text LM emits tokens at one rate; the audio stack that consumes them runs at another. The usual fix is to pad the text stream to the audio frame rate — most positions become `PAD`, the model spends capacity learning when *not* to speak. The alternative is a bursty text stream plus some implicit sense of time inside the model, with explicit time injection (a clock signal, VAD chunks, or an additive embedding in the style of Moshi) layered on later. That second path only works if the hidden states are receptive to time in the first place. This note is the probe.

## Question

Given a 10M-parameter transformer trained on short synthetic dialogues, can an auxiliary time-prediction objective *shape* the representations enough that downstream time-conditioning has something to hook into? The goal is not a competitive timing model; it is to test whether the path is worth taking.

## Setup

The data is a synthetic single-turn dialogue corpus, ≈135k examples. Each example is a `(scenario, persona, user_text, response)` quadruple. The TTS for the response side has been force-aligned, so every word of the response has a known start and end time. Average response length is ≈11 BPE tokens (≈7 words, ≈2.3 s of speech). Word-end times cluster in 0–6 s; the tail past 6 s is <0.1 %.

The base model is a publicly available 10M-parameter decoder, pretrained on 1B tokens of general English. Both arms use the same backbone, tokenizer, and training schedule:

| Arm   | Word LM loss | Time-head loss | Time head |
|-------|--------------|----------------|-----------|
| base  | yes          | weight 0       | random    |
| +time | yes          | weight 0.5     | trained   |

The time head is a single linear layer reading the final hidden state, predicting a class over 80 bins of 80 ms each (one Mimi frame) plus one *null* class. Targets are the cumulative word-end time at the last subword of each word; mid-word and prompt positions get the null class or are ignored. The head adds 12k parameters to a 17M total.

The padding question is dealt with on the data side: dialogues are concatenated end-to-end and chunked into 128-token windows. This raises useful-token fill from 32 % to 100 % and tripled training throughput.

## Results

Two questions to answer, both per-position on a held-out split.

**Did the aux signal get learned?** The time head's NLL drops from 5.49 (random over 81 classes) to 1.67. Word-end accuracy within ±1 frame (±160 ms) climbs from 4 % to 64 %, and MAE on word-end positions reaches 155 ms. A backoff Gaussian bigram fit to the same data scores 59 % within ±1 frame at 132 ms MAE: the LM is in the bigram's neighborhood, slightly higher on coarse accuracy, slightly worse on mean error.

**What did it cost?** Word LM NLL rises from 1.60 to 1.66 — about 4 % more cross-entropy on the main objective. Not free, not catastrophic.

| Metric                       | base       | +time        |
|------------------------------|------------|--------------|
| Word LM NLL                  | 1.601      | 1.665        |
| Time-head NLL                | 5.485      | 1.668        |
| Within ±1 frame (±160 ms)    | 0.040      | 0.644        |
| Within ±2 frames (±240 ms)   | 0.068      | 0.809        |
| MAE on word-end positions    | 27 bins    | 1.94 bins    |

## Inject probe

The head-accuracy numbers are not the gate. They show the signal is learnable, but say nothing about whether the trunk learned to *represent* time, as opposed to letting the linear head do all the work on top of unchanged features.

The diagnostic: freeze each trained model, add a zero-initialized embedding `(81 → 144)` that sums into input embeddings, train only the embedding on word LM loss with ground-truth time bins injected. The adapter has 12k parameters; both arms get identical training. How much extra word-LM signal can each frozen model extract from time conditioning, given equal post-hoc adapter capacity?

| Arm   | Word LM NLL pre | After inject-train | Δ        |
|-------|------------------|--------------------|----------|
| base  | 1.598            | 1.591              | −0.0076  |
| +time | 1.662            | 1.649              | −0.0132  |

The +time arm absorbs ≈1.7× more value from injected time than the base arm. Magnitudes are small (<1 % NLL on either), but the asymmetry is the point: the aux objective changed what the trunk learned, not just what the head reads.

## Interpretation

Three claims, decreasing in strength. The aux signal is learnable at this scale: a 4 nats drop on per-position 81-way classification, head accuracy in the bigram neighborhood. The cost on the main objective is modest: ≈4 % NLL. The trunk's representations adapt to make time conditioning more effective: directional, 1.7× inject ratio, small absolute Δ. The first two are the headline; the third is what makes the diagnostic interesting, and it is the weakest of the three.

The result is bounded in several obvious ways. 10M parameters is small. The corpus is narrow and synthetic. Loss weight λ=0.5 was a guess, not a sweep. Both arms' validation loss was still descending at training end, so saturated numbers might look different. And the inject probe measures receptivity to *ground-truth* time, not whether the model can usefully act on noisy time signals in deployment.

## Closing claim

> A 10M LM with a cheap auxiliary objective can predict cumulative word timing within one frame for the majority of word-ends, at a 4 % cost to its language model, and its hidden states adapt to absorb injected time information about 1.7× more effectively than an otherwise-identical model trained without the objective. The numbers are modest in absolute terms.
>
> The useful part is the diagnostic: *post-hoc inject-Δ measures whether an auxiliary objective changed the trunk's representations, not just what its head can read off them.*
