"""
Lexical stage: where can each word boundary be, given the transcript?

The transcript is spelled into the CTC label set of the pretrained HuBERT-large model (letters,
apostrophe, '|' between words). CTC forward-backward over that label sequence gives, for every
20 ms frame, the posterior of every label position. From it, per word boundary k (between token k
and k+1):
    A(t) = P(the last letter of token k is finished by frame t)
    B(t) = P(the first letter of token k+1 has started by frame t)
The boundary CDF is taken as (A + B) / 2 -- all the mass sits between the two words' letter
evidence, spread over the frames the model cannot attribute to either -- and its density, blurred
by one frame, is the boundary prior on the 2 ms grid.

Works on letters (HuBERT CTC, '|' between words) or on phones (xlsr-53 espeak CTC, no separator): pass
`units` (per-token label ids), `sep` and `wild_from` (first real label id) for phones.

Transcript conventions: '(())' (unintelligible) and tokens with no letters become a wildcard label
that emits the best letter at each frame; '((word))' -> word; cut-offs 's-' -> 's'; digits are spelled.
"""
import re

import numpy as np

BLANK, SEP = 0, 4
FRAME = 0.020
FRAME_OFF = 0.0125          # HuBERT frame k covers samples [320k, 320k + 400): centre 20k + 12.5 ms
VOCAB = {c: i for i, c in enumerate(["<pad>", "<s>", "</s>", "<unk>", "|", "E", "T", "A", "O", "N", "I", "H", "S", "R",
                                     "D", "L", "U", "M", "W", "C", "F", "G", "Y", "P", "B", "V", "K", "'", "X", "J", "Q", "Z"])}
WILD = -1


def spell(token):
    """token text -> list of label ids (WILD for a wildcard)"""
    w = token.strip()
    w = re.sub(r"^\(\((.*)\)\)$", r"\1", w)
    if re.search(r"\d", w):
        from num2words import num2words
        w = re.sub(r"\d+(\.\d+)?", lambda m: " " + num2words(float(m.group()) if "." in m.group() else int(m.group())) + " ", w)
    letters = [VOCAB[c] for c in w.upper() if c in VOCAB and VOCAB[c] > SEP]
    return letters or [WILD]


def label_sequence(tokens, units=None, sep=SEP):
    """labels (optionally with `sep` between tokens); returns (labels, first_idx[k], last_idx[k]).
    units: per-token label id lists (e.g. phones); default = the tokens spelled in letters."""
    units = units if units is not None else [spell(t) for t in tokens]
    labels, first, last = [], [], []
    for k, u in enumerate(units):
        if k and sep is not None:
            labels.append(sep)
        first.append(len(labels)); labels.extend(u); last.append(len(labels) - 1)
    return labels, first, last


def forward_backward(logp, labels, wild_from=SEP + 1):
    """log posteriors gamma[t, s] over the CTC state sequence (blank, l1, blank, l2, ..., blank)"""
    T = logp.shape[0]
    lab = np.asarray(labels)
    S = 2 * len(lab) + 1
    st = np.full(S, BLANK); st[1::2] = lab
    wild = st == WILD
    best_letter = np.max(logp[:, wild_from:], axis=1)
    em = np.empty((T, S))
    em[:, ~wild] = logp[:, st[~wild]]
    em[:, wild] = best_letter[:, None]
    skip = np.zeros(S, bool)
    skip[3::2] = (st[3::2] != st[1:-2:2]) | wild[3::2]      # s-2 -> s allowed between different labels
    NEG = -1e30
    alpha = np.full((T, S), NEG)
    alpha[0, 0] = em[0, 0]; alpha[0, 1] = em[0, 1]
    for t in range(1, T):
        a = alpha[t - 1]
        m = np.logaddexp(a, np.r_[NEG, a[:-1]])
        m = np.where(skip, np.logaddexp(m, np.r_[NEG, NEG, a[:-2]]), m)
        alpha[t] = m + em[t]
    beta = np.full((T, S), NEG)
    beta[T - 1, S - 1] = 0.0; beta[T - 1, S - 2] = 0.0
    skip_next = np.r_[skip[2:], False, False]                 # s -> s+2 allowed if skip[s+2]
    for t in range(T - 2, -1, -1):
        b = beta[t + 1] + em[t + 1]
        m = np.logaddexp(b, np.r_[b[1:], NEG])
        m = np.where(skip_next, np.logaddexp(m, np.r_[b[2:], NEG, NEG]), m)
        beta[t] = m
    logZ = np.logaddexp(alpha[T - 1, S - 1], alpha[T - 1, S - 2])
    return alpha + beta - logZ, logZ


def forward_backward_torch(logp, labels, device="cuda", wild_from=SEP + 1):
    """same as forward_backward, on the GPU; returns gamma as a torch tensor (T, S) on `device`"""
    import torch
    lp = torch.as_tensor(logp, dtype=torch.float64, device=device)
    T = lp.shape[0]
    lab = np.asarray(labels)
    S = 2 * len(lab) + 1
    st = np.full(S, BLANK); st[1::2] = lab
    wild = st == WILD
    em = torch.empty((T, S), dtype=torch.float64, device=device)
    em[:, torch.as_tensor(~wild, device=device)] = lp[:, torch.as_tensor(st[~wild], device=device)]
    if wild.any():
        em[:, torch.as_tensor(wild, device=device)] = lp[:, wild_from:].max(1).values[:, None]
    skip_np = np.zeros(S, bool); skip_np[3::2] = (st[3::2] != st[1:-2:2]) | wild[3::2]
    skip = torch.as_tensor(skip_np, device=device)
    skip_next = torch.as_tensor(np.r_[skip_np[2:], False, False], device=device)
    NEG = torch.tensor(-1e30, dtype=torch.float64, device=device)
    pad1 = NEG.expand(1); pad2 = NEG.expand(2)
    alpha = torch.full((T, S), -1e30, dtype=torch.float64, device=device)
    alpha[0, 0] = em[0, 0]; alpha[0, 1] = em[0, 1]
    for t in range(1, T):
        a = alpha[t - 1]
        m = torch.logaddexp(a, torch.cat([pad1, a[:-1]]))
        m = torch.where(skip, torch.logaddexp(m, torch.cat([pad2, a[:-2]])), m)
        alpha[t] = m + em[t]
    beta = torch.full((T, S), -1e30, dtype=torch.float64, device=device)
    beta[T - 1, S - 1] = 0.0; beta[T - 1, S - 2] = 0.0
    for t in range(T - 2, -1, -1):
        b = beta[t + 1] + em[t + 1]
        m = torch.logaddexp(b, torch.cat([b[1:], pad1]))
        m = torch.where(skip_next, torch.logaddexp(m, torch.cat([b[2:], pad2])), m)
        beta[t] = m
    logZ = torch.logaddexp(alpha[T - 1, S - 1], alpha[T - 1, S - 2])
    return alpha + beta - logZ, float(logZ)


def boundary_priors(logp, tokens, n_grid, grid_hop=0.002, device=None, units=None, sep=SEP, wild_from=SEP + 1,
                    frame_off=FRAME_OFF):
    """per boundary k (0..N-2): prior density over the 2 ms grid (sums to 1), plus the CDFs of token 0
    having started and the last token having finished. device='cuda' runs forward-backward on the GPU."""
    labels, first, last = label_sequence(tokens, units, sep)
    if device:
        import torch
        g, logZ = forward_backward_torch(logp, labels, device, wild_from)
        cum = torch.flip(torch.cumsum(torch.flip(torch.exp(g), [1]), 1), [1])     # P(state >= s at t)
        cols = [2 * last[k] + 2 for k in range(len(tokens) - 1)] + [2 * first[k + 1] + 1 for k in range(len(tokens) - 1)]
        cols += [2 * first[0] + 1, 2 * last[-1] + 2]
        C = cum[:, torch.as_tensor(cols, device=device)].cpu().numpy()
        edge = [2 * f + 1 for f in first] + [2 * l + 1 for l in last]
        G = torch.exp(g[:, torch.as_tensor(edge, device=device)]).cpu().numpy()
    else:
        g, logZ = forward_backward(logp, labels, wild_from)
        cum = np.cumsum(np.exp(g)[:, ::-1], axis=1)[:, ::-1]
        cols = [2 * last[k] + 2 for k in range(len(tokens) - 1)] + [2 * first[k + 1] + 1 for k in range(len(tokens) - 1)]
        cols += [2 * first[0] + 1, 2 * last[-1] + 2]
        C = cum[:, cols]
        G = np.exp(g[:, [2 * f + 1 for f in first] + [2 * l + 1 for l in last]])
    nb = len(tokens) - 1
    T = C.shape[0]
    tf = np.arange(T) * FRAME + frame_off
    grid = np.arange(n_grid) * grid_hop
    sig = int(round(FRAME / grid_hop))                        # blur by one CTC frame
    ker = np.exp(-0.5 * (np.arange(-3 * sig, 3 * sig + 1) / sig) ** 2); ker /= ker.sum()
    priors, between, ab = [], [], []
    for k in range(nb):
        A, B = C[:, k], C[:, nb + k]                          # past token k's last letter / reached k+1's first
        F = np.interp(grid, tf, 0.5 * (A + B))
        dens = np.convolve(np.maximum(np.diff(np.r_[0.0, F]), 0), ker, "same") + 1e-12
        priors.append(dens / dens.sum())
        between.append(np.clip(np.interp(grid, tf, A - B), 0, 1).astype(np.float32))   # P(in neither word)
        ab.append((np.interp(grid, tf, A).astype(np.float32), np.interp(grid, tf, B).astype(np.float32)))
    first_start = np.interp(grid, tf, C[:, 2 * nb])
    last_end = np.interp(grid, tf, C[:, 2 * nb + 1])
    n = len(tokens)
    edge_post = {"first": [np.interp(grid, tf, G[:, k]).astype(np.float32) for k in range(n)],   # P(token k's first letter)
                 "last": [np.interp(grid, tf, G[:, n + k]).astype(np.float32) for k in range(n)]}  # P(token k's last letter)
    return priors, first_start, last_end, float(logZ), between, edge_post, ab
