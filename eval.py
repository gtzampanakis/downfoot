import collections, uuid, json, sqlite3, os, itertools
import scipy as sp
import scipy.optimize as spo
import scipy.sparse as sps

import util

DEFAULT_RATING = 0.

NCHUNKS = 25

ROOT_DIR = os.path.dirname(__file__)

PLAYER_TO_TRACK = 'gyorgy-sandor'

N = 1000

K = .05
H = .35
T = 20
M = 1

matches = [ ]
from_id = { }
# with open('matches.froz.csv') as inf:
# 	for row in inf:
# 		row = row.strip()
# 		date, team1, team2, score1, score2, lineup1, lineup2 = row.split(';')
# 		lineup1 = lineup1.split(',')
# 		lineup2 = lineup2.split(',')
# 		ma = dict(
# 			id = uuid.uuid4().hex,
# 			date = date,
# 			teams = [team1, team2],
# 			team1 = team1,
# 			team2 = team2,
# 			scores = [int(score1), int(score2)],
# 			score1 = int(score1),
# 			score2 = int(score2),
# 			lineups = [lineup1, lineup2],
# 			lineup1 = lineup1,
# 			lineup2 = lineup2,
# 		)
# 		matches.append(ma)
# 		from_id[ma['id']] = ma

def get_conn():
	conn = sqlite3.connect(os.path.join(ROOT_DIR, 'matches.db'))
	return conn

conn = get_conn()

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

# Discard all matches that do not have 22 distinct players, for whatever
# reason.
matches = [
	m for m in matches
	if  len(set(
		m['lineups'][0] + m['lineups'][1]
	)) == 22
]

N = len(matches)

plist = [ ]
p2i = { }
i2p = { }
rlist = [ ]
obssuplist = [ ]

for mai, ma in enumerate(matches):

	for p in itertools.chain(*ma['lineups']):
		if p not in p2i:
			i = len(plist)
			plist.append(p)
			rlist.append(DEFAULT_RATING)
			p2i[p] = i
			i2p[i] = p

	obs_sup = ma['score'][0] - ma['score'][1]
	obssuplist.append(obs_sup)

# To accommodate the final all-ones A column.
obssuplist.append(H)

# Column vector of ratings.
R = sp.array(rlist)

# Column vector of observed superiorities.
SO = sp.array(obssuplist)

# Matrix of appearances. Columns are players, rows are matches.
# First using lil_matrix because it allows to build incrementally.
A = sps.lil_matrix((N+1, R.size))


for mai, ma in enumerate(matches):
	for li, l in zip([1,-1], ma['lineups']):
		assert len(l) == 11
		assert len(set(l)) == 11
		for p in l:
			A[mai, p2i[p]] = li

A[N,:] = sp.ones((1,R.size))

# Now convert to CSC format for faster operations.
A = A.tocsr()

HM = sp.ones(N+1) * H

assert A[:N,:].sum() == 0

def errf(Rin):
	res = abs(A * Rin + HM - SO).sum() * 1./N
	print Rin.sum(), res
	return

import scipy.sparse.linalg as spsl

spsl.lsqr(A, SO - H)

import scipy.optimize as so

res = spo.fmin(errf, x0=R, disp=1)

print res

