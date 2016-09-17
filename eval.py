import collections, uuid, json, sqlite3, os, itertools
import numpy as np
import scipy as sp
import scipy.optimize as spo
import scipy.sparse as sps
import scipy.sparse.linalg as spsl

DEFAULT_RATING = 0.

PS_PER_TEAM = 11

NCHUNKS = 25

if '__file__' in globals():
	ROOT_DIR = os.path.dirname(__file__)
else:
# In case this script is run through iPython's execfile.
	ROOT_DIR = '.'

N = 50 * 1000

if 'matches' not in globals():

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

# Discard all matches that do not have 22 distinct players, for whatever
# reason.
	matches = [
		m for m in matches
		if  len(set(
			m['lineups'][0] + m['lineups'][1]
		)) == PS_PER_TEAM * 2
	]
	print 'Matches loaded.'

teams  = [m['teams'][0] for m in matches]
teams += [m['teams'][1] for m in matches]
teams = list(set(teams))

if 0:
	import networkx as nx
	g = nx.Graph()
	for ma in matches:
		g.add_nodes_from(ma['teams'])
		n1, n2 = ma['teams']
		g.add_edge(
				n1,
				n2,
				attr_dict = {
					'capacity': g.get_edge_data(
						n1, n2, { }
					).get('capacity', 0) + 1,
				}
		)
	import pdb; pdb.set_trace()
	for repi in itertools.count(1):
		print repi, nx.number_of_nodes(g), nx.number_of_edges(g)
		min_cut_edges = list(nx.minimum_edge_cut(g))
		g.remove_edges_from(min_cut_edges)
		ccs = list(nx.connected_component_subgraphs(g))
		assert len(ccs) == 2
		n1, n2 = [ sg.number_of_nodes() for sg in ccs ]
		if n1 > n2:
			g = ccs[0]
		else:
			g = ccs[1]

if 1:
	with open('dat.csv', 'wb') as datcsvf:
		datcsvf.write('gh,ga\n')
		for ma in matches:
			datcsvf.write(str(ma['score'][0]))
			datcsvf.write(',')
			datcsvf.write(str(ma['score'][1]))
			datcsvf.write('\n')

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

# This represents the intercept (e.g. home advantage)
rlist.append(DEFAULT_RATING)
INTERCEPT_INDEX = len(rlist) - 1
i2p[INTERCEPT_INDEX] = '___INTERCEPT___'

# Column vector of ratings.
B = sp.array(rlist)

# Column vector of observed superiorities.
SO = sp.array(obssuplist)

# Matrix of appearances. Columns are players, rows are matches.
# First using lil_matrix because it allows to build incrementally.
A = sps.lil_matrix((N, B.size))


for mai, ma in enumerate(matches):
	for li, l in zip([1,-1], ma['lineups']):
		assert len(l) == PS_PER_TEAM
		assert len(set(l)) == PS_PER_TEAM
		for p in l:
			A[mai, p2i[p]] = li
	A[mai, INTERCEPT_INDEX] = 1

# Now convert to CSC format for faster operations.
A = A.tocsr()

assert A.sum() == N # Sum all the intercept constants.

##############################################
##############################################
##############################################
##############################################
##############################################
##############################################
res = spsl.lsqr(A, SO, damp=N/10000., show=True)
##############################################
##############################################
##############################################
##############################################
##############################################
##############################################

B = res[0]

fitted = A * B
