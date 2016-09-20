import collections, uuid, json, sqlite3, os, itertools, uuid, random
import ConfigParser
import numpy as np
import scipy as sp
import scipy.optimize as spo
import scipy.sparse as sps
import scipy.sparse.linalg as spsl

config_parser = ConfigParser.ConfigParser()
config_parser.read('eval.conf')

DEFAULT_RATING = 0.

PS_PER_TEAM = 11

RESAMPLE = int(config_parser.get('General', 'resample'))

ALGO = config_parser.get('General', 'algo')

H = float(config_parser.get('General', 'H'))

D = float(config_parser.get('General', 'D'))

DAMPING = float(config_parser.get('General', 'damping'))

PLOT_RESIDUAL_QQ = int(config_parser.get('General', 'plot_residual_qq'))

PLOT_RESIDUAL_HIST = int(config_parser.get('General', 'plot_residual_hist'))

PLOT_SCATTER_TOT_EXP_RESIDUALS = int(config_parser.get(
									'General', 'plot_scatter_tot_exp_residuals'))

PRINT_RESID_STD_PER_TOT_EXP_BRACKET = int(config_parser.get(
									'General', 'print_resid_std_per_tot_exp_bracket'))

if '__file__' in globals():
	ROOT_DIR = os.path.dirname(__file__)
else:
# In case this script is run through iPython's execfile.
	ROOT_DIR = '.'

N = 50 * 1000

if 'db_matches' not in globals():

	db_matches = [ ]
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
		db_matches.append(ma)

# Discard all matches that do not have 22 distinct players, for whatever
# reason.
	db_matches = [
		m for m in db_matches
		if  len(set(
			m['lineups'][0] + m['lineups'][1]
		)) == PS_PER_TEAM * 2
	]
	print 'Matches loaded.'

matches = db_matches

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

if 0:
	with open('dat.csv', 'wb') as datcsvf:
		datcsvf.write('gh,ga\n')
		for ma in matches:
			datcsvf.write(str(ma['score'][0]))
			datcsvf.write(',')
			datcsvf.write(str(ma['score'][1]))
			datcsvf.write('\n')

N = len(matches)

if RESAMPLE:
	new_matches = [ ]
	for i in xrange(N):
		new_matches.append(random.choice(matches))
	matches = new_matches
	matches.sort(key = lambda ma: ma['date'])

plist = [ ]
p2i = { }
i2p = { }
rlist = [ ] 
obssuplist = [ ]
home_goals = [ ]
away_goals = [ ]
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
	home_goals.append(ma['score'][0])
	away_goals.append(ma['score'][1])

# Column vector of observed superiorities.
SO = sp.array(obssuplist)
HG = sp.array(home_goals)
AG = sp.array(away_goals)

exps = sp.zeros(len(matches))
tot_exps = sp.zeros(len(matches))

for mai, ma in enumerate(matches):
	for p in ma['lineups'][0]:
		exps[p2i[p]] += 1
		tot_exps[mai] += exps[p2i[p]]

	for p in ma['lineups'][1]:
		exps[p2i[p]] += 1
		tot_exps[mai] += exps[p2i[p]]


if ALGO == 'lsqr':
# This represents the intercept (e.g. home advantage)
	rlist.append(DEFAULT_RATING)
	INTERCEPT_INDEX = len(rlist) - 1
	i2p[INTERCEPT_INDEX] = '___INTERCEPT___'

# Column vector of ratings.
	R = sp.array(rlist)

# Matrix of appearances. Columns are players, rows are matches.
# First using lil_matrix because it allows to build incrementally.
	A = sps.lil_matrix((N, R.size))


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
	res = spsl.lsqr(A, SO, 
					damp=N/DAMPING,
					show=True)
##############################################
##############################################
##############################################
##############################################
##############################################
##############################################

	R = res[0]

	fitted = A * R

elif ALGO == 'distdiff':

	R = sp.array(rlist)
	fitted = [ ]

	for mai, ma in enumerate(matches):
		
		home_rating = sum(
				R[p2i[p]]
				for p in ma['lineups'][0]
		)
		away_rating = sum(
				R[p2i[p]]
				for p in ma['lineups'][1]
		)

		expsup = home_rating - away_rating + H
		obssup = ma['score'][0] - ma['score'][1]

		fitted.append(expsup)

		diff = obssup - expsup

		to_distr = diff * D / 22.

# Distribute the difference to the players of both home team.

		for p in ma['lineups'][0]:
			R[p2i[p]] += to_distr

		for p in ma['lineups'][1]:
			R[p2i[p]] -= to_distr

resid = SO - fitted

order = np.argsort(R)

for nprinted in itertools.count(1):
	print '%s %.3f' % (i2p[order[-nprinted]], R[order[-nprinted]])
	if nprinted > 50:
		break

file_suffix = uuid.uuid4().hex
rfile = open('ratings/ratings_%s.txt' % file_suffix, 'wb')
mfile = open('matches_fitted/fitted_%s.txt' % file_suffix, 'wb')

if 1:
	for ind in reversed(order):
		towrite = '%s,%.3f' % (i2p[ind], R[ind])
		rfile.write(towrite)
		rfile.write('\n')

if 1:
	for mai, ma in enumerate(matches):
		towrite = '%s,%s,%s,%s,%s,%.3f' % (
				ma['date'],
				ma['teams'][0],
				ma['teams'][1],
				ma['score'][0],
				ma['score'][1],
				fitted[mai],
		)
		mfile.write(towrite)
		mfile.write('\n')

print
print 'residual_std: %.10f' % (resid.std())
print

if PLOT_RESIDUAL_QQ:
	import statsmodels.graphics.gofplots as sgg
	sgg.qqplot(resid, fit=True)

if PLOT_RESIDUAL_HIST:
	import pylab
	import scipy.stats as ss

	freqs, lefts = np.histogram(resid, bins = 'auto', density = True)
	centers = (lefts[:-1] + lefts[1:]) / 2
	pylab.bar(centers, freqs, width = centers[1] - centers[0])

	empirical_dist = ss.norm(*(ss.norm.fit(resid)))
	pylab.plot(centers, [empirical_dist.pdf(x) for x in centers], 'g-', linewidth = 5)
	
if PLOT_SCATTER_TOT_EXP_RESIDUALS:
	import pylab
	pylab.scatter(tot_exps, resid, marker = '.', s = 1)

if PRINT_RESID_STD_PER_TOT_EXP_BRACKET:
	import scipy.stats as ss

	percs = np.percentile(tot_exps,
							np.linspace(0, 100, PRINT_RESID_STD_PER_TOT_EXP_BRACKET)[1:-1])
	print 'Residual std per tot_exp bracket:'
	y = [ ]
	x = [ ]
	for lowlim, highlim in zip(percs[:-1], percs[1:]):
		subset = (tot_exps > lowlim) & (tot_exps <= highlim)
		x.append((lowlim + highlim)/2.)
		y.append(resid[subset].std())
	
	for xi, yi in zip(x, y):
		print '%d %.3f' % (xi, yi)
	
	print 'intercept: %.3f' % ss.linregress(x, y).intercept
	print 'slope: %.3e' % ss.linregress(x, y).slope

mfile.close()
rfile.close()

