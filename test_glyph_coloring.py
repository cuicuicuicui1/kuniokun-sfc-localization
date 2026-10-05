"""ROM-free regression of measured-window colouring, not lifetime inference."""
from glyph_coloring import colour_windows

def fails(w, k, cap, fixed=None):
    try:
        colour_windows(w, k, cap, fixed, node_limit=10000)
    except ValueError:
        return
    raise AssertionError('illegal allocation accepted')

windows = [set('abcd'), set('bcde'), set('cdef'), set('defg')]
c, loads, stats = colour_windows(windows, 4, 2, {'a': 0})
assert c['a'] == 0 and max(loads) <= 2 and sum(loads) == 7
assert all(len({c[x] for x in w}) == len(w) for w in windows)
assert colour_windows(windows[::-1], 4, 2, {'a': 0})[0] == c
fails([set('abcd')], 3, 2)
fails([set('abc')], 3, 2, {'a': 0, 'b': 0})
fails([{x} for x in 'abcdefg'], 3, 2)
fails([set('ab'), set('bc'), set('ca')], 2, 3)
# An odd cycle has no 2-colouring, including graphs without a triangle clique.
fails([set('ab'), set('bc'), set('cd'), set('de'), set('ea')], 2, 3)
c, loads, _ = colour_windows([{x} for x in 'abcdefghi'], 3, 3, {'a': 2})
assert c['a'] == 2 and loads == [3, 3, 3]
print('PASS: deterministic complete-window constraints, fixed source, capacities, clique/odd-cycle negatives')
