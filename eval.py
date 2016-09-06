import collections, uuid, json, sqlite3, os, itertools
import numpy as np
import scipy as sp
import scipy.optimize as spo
import scipy.sparse as sps
import scipy.sparse.linalg as spsl

DEFAULT_RATING = 0.

PS_PER_TEAM = 11

NCHUNKS = 25

ROOT_DIR = os.path.dirname(__file__)

PLAYER_TO_TRACK = 'gyorgy-sandor'

N = 500000

H = .35

matches = [ ]
from_id = { }

def get_conn():
	conn = sqlite3.connect(os.path.join(ROOT_DIR, 'matches.db'))
	return conn

conn = get_conn()

print 'Loading matches...'
results = conn.execute('''
	select id, match_json from (
		select id, match_json, date
		from matches
		order by date desc
		limit ?
	)
	order by date
''', [N])

for row in results:
	ma_id = row[0]
	ma = json.loads(row[1])
	ma['id'] = ma_id
	from_id[ma_id] = ma
	matches.append(ma)
print 'Matches loaded.'

# Discard all matches that do not have 22 distinct players, for whatever
# reason.
matches = [
	m for m in matches
	if  len(set(
		m['lineups'][0] + m['lineups'][1]
	)) == PS_PER_TEAM * 2
]

N = len(matches)

plist = [ ]
p2i = { }
i2p = { }
rlist = [ ]
obssuplist = [ ]
p2e = collections.defaultdict(int)

for mai, ma in enumerate(matches):

	for p in itertools.chain(*ma['lineups']):
		p2e[p] += 1
		if p not in p2i:
			i = len(plist)
			plist.append(p)
			rlist.append(DEFAULT_RATING)
			p2i[p] = i
			i2p[i] = p

	obs_sup = ma['score'][0] - ma['score'][1]
	obssuplist.append(obs_sup)

# Column vector of ratings.
R = sp.array(rlist)

# Column vector of observed superiorities.
SO = sp.array(obssuplist)

# Matrix of appearances. Columns are players, rows are matches.
# First using lil_matrix because it allows to build incrementally.
A = sps.lil_matrix((N, R.size))


for mai, ma in enumerate(matches):
	for li, l in zip([1,-1], ma['lineups']):
		assert len(l) == PS_PER_TEAM
		assert len(set(l)) == PS_PER_TEAM
		for p in l:
			A[mai, p2i[p]] = li

# Now convert to CSC format for faster operations.
A = A.tocsr()

HM = sp.ones(N) * H

assert A.sum() == 0

##############################################
##############################################
##############################################
##############################################
##############################################
##############################################
res = spsl.lsqr(A, SO - HM, damp=N/100., show=True)
##############################################
##############################################
##############################################
##############################################
##############################################
##############################################

R = res[0]

inds = np.argsort(R)

nprinted = 0
for ind in reversed(inds):
	exp = p2e[i2p[ind]]
	if exp >= 0:
		print '%s    %d    %.3f' % (i2p[ind], exp, R[ind])
		nprinted += 1
	if nprinted >= 5000:
		break

print 'N', N


