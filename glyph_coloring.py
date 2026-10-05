"""Deterministic, capacity-bounded colouring of measured glyph lifetimes.

This module does NOT infer lifetimes or borrow tiles. Every input window is an
all-different constraint. A colour is also a ROM storage column. Greedy DSATUR
alone is not an infeasibility proof; solve the high-degree core with bounded
list-colouring, then extend and balance the sparse fringe. No third-party solver.
"""
from collections import Counter, deque


def colour_windows(windows, slots, capacity, fixed=None, node_limit=50000):
    fixed = dict(fixed or {})
    ws = [set(w) for w in windows]
    chars = sorted(set().union(*ws, set(fixed)))
    if not 0 < slots or not 0 < capacity:
        raise ValueError('invalid glyph column capacity')
    if any(len(w) > slots for w in ws) or len(chars) > slots * capacity:
        raise ValueError('live-window/storage pigeonhole limit exceeded')
    if any(not 0 <= s < slots for s in fixed.values()):
        raise ValueError('fixed glyph column out of range')
    adj = {c: set() for c in chars}
    for w in ws:
        for c in w:
            adj[c].update(w - {c})
    if any(fixed[c] == fixed[z] for c in fixed for z in adj[c] & fixed.keys()):
        raise ValueError('co-visible fixed glyph collision')

    # A vertex below k degree is easy to extend in an uncapacitated k-colouring.
    # Capacities are still checked on the COMPLETE graph below, not discarded.
    core = set(chars)
    while True:
        low = {c for c in core if len(adj[c] & core) < slots}
        if not low:
            break
        core.difference_update(low)
    best = []
    for seed in sorted(core, key=lambda c: (-len(adj[c]), c)):
        clique, cand = [seed], adj[seed] & core
        while cand:
            c = max(cand, key=lambda z: (len(cand & adj[z]), len(adj[z]), z))
            clique.append(c)
            cand = cand & adj[c]
        if len(clique) > len(best):
            best = clique
    if len(best) > slots:
        raise ValueError('observed clique needs %d columns' % len(best))
    assigned = fixed.copy()
    # Only break colour-permutation symmetry if every fixed vertex belongs to
    # this clique. Otherwise an arbitrary precolour could exclude a solution.
    if set(fixed) <= set(best):
        used = set(fixed.values())
        for c in sorted(set(best) - fixed.keys()):
            s = next(s for s in range(slots) if s not in used)
            assigned[c] = s
            used.add(s)
    domains = {c: (1 << slots) - 1 for c in core - assigned.keys()}
    for c in domains:
        for z in adj[c] & assigned.keys():
            domains[c] &= ~(1 << assigned[z])

    def extend(seed):
        col = seed.copy()
        loads = Counter(col.values())
        if max(loads.values(), default=0) > capacity:
            return None
        remaining = set(chars) - col.keys()
        while remaining:
            bans = {c: {col[z] for z in adj[c] & col.keys()} for c in remaining}
            c = max(remaining, key=lambda z: (len(bans[z]), len(adj[z]), z))
            free = [s for s in range(slots) if s not in bans[c]]
            if not free:
                return None
            s = min(free, key=lambda z: (loads[z], z))
            col[c] = s
            loads[s] += 1
            remaining.remove(c)
        # Augmenting colour paths move an unfixed vertex out of an overloaded
        # column into a legal spare column. Apply paths backwards; later moves
        # only REMOVE blockers from the next destination. All edges stay live.
        while max(loads.values(), default=0) > capacity:
            over = [s for s in range(slots) if loads[s] > capacity]
            under = {s for s in range(slots) if loads[s] < capacity}
            arc = {s: {} for s in range(slots)}
            for c in sorted(set(chars) - fixed.keys(), key=lambda z: (len(adj[z]), z)):
                s = col[c]
                banned = {col[z] for z in adj[c]}
                for t in range(slots):
                    if t != s and t not in banned and t not in arc[s]:
                        arc[s][t] = c
            q = deque(sorted(over, key=lambda s: (-loads[s], s)))
            prev = {s: None for s in q}
            end = None
            while q and end is None:
                s = q.popleft()
                for t, c in sorted(arc[s].items(), key=lambda z: (loads[z[0]], z[0])):
                    if t in prev:
                        continue
                    prev[t] = (s, c)
                    if t in under:
                        end = t
                        break
                    q.append(t)
            if end is None:
                return None
            t = end
            while prev[t] is not None:
                s, c = prev[t]
                if any(col[z] == t for z in adj[c]):
                    raise AssertionError('invalid augmenting colour path')
                col[c] = t
                loads[s] -= 1
                loads[t] += 1
                t = s
        return col

    visited = 0

    def search(dom, col):
        nonlocal visited
        visited += 1
        if visited > node_limit:
            # Not an infeasibility claim: do not weaken windows after a timeout.
            raise ValueError('bounded core search exhausted (%d nodes)' % node_limit)
        while dom:
            singles = sorted(c for c, v in dom.items() if v.bit_count() <= 1)
            if not singles:
                break
            for c in singles:
                mask = dom.pop(c)
                if not mask:
                    return None
                s = mask.bit_length() - 1
                col[c] = s
                for z in adj[c] & dom.keys():
                    dom[z] &= ~(1 << s)
                    if not dom[z]:
                        return None
        if not dom:
            return extend(col)
        c = min(dom, key=lambda z: (dom[z].bit_count(), -len(adj[z] & dom.keys()), -len(adj[z]), z))
        mask = dom.pop(c)
        free = [s for s in range(slots) if mask >> s & 1]
        free.sort(key=lambda s: (sum(bool(dom[z] >> s & 1) for z in adj[c] & dom.keys()), s))
        for s in free:
            ds, cs = dom.copy(), col.copy()
            cs[c] = s
            for z in adj[c] & ds.keys():
                ds[z] &= ~(1 << s)
            if all(ds.values()):
                answer = search(ds, cs)
                if answer is not None:
                    return answer
        return None

    result = search(domains.copy(), assigned.copy())
    if result is None:
        raise ValueError('no capacity-bounded colouring found for this window graph')
    loads = [sum(result[c] == s for c in chars) for s in range(slots)]
    if any(len({result[c] for c in w}) != len(w) for w in ws):
        raise AssertionError('colouring violated a live window')
    if max(loads, default=0) > capacity or any(result[c] != s for c, s in fixed.items()):
        raise AssertionError('colouring violated source column bounds')
    return result, loads, {'core': len(core), 'seed_clique': len(best), 'search_nodes': visited}
