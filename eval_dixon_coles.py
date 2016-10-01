import collections, uuid, json, sqlite3, os, itertools, uuid, random, time, re, datetime
import ConfigParser
import numpy as np
import scipy as sp
import scipy.optimize as spo
import scipy.sparse as sps
import scipy.sparse.linalg as spsl

config_parser = ConfigParser.ConfigParser()
config_parser.read('eval_dixon_coles.conf')

PS_PER_TEAM = 11

RESAMPLE = int(config_parser.get('General', 'RESAMPLE'))

FILTER_FILE = config_parser.get('General', 'FILTER_FILE')

REGEXPS = [ ]

CENTER_DATE = config_parser.get('General', 'CENTER_DATE')

if CENTER_DATE:
	CENTER_DATE = datetime.date(*[int(s) for s in CENTER_DATE.split('-')])
	KSI = float(config_parser.get('General', 'KSI'))

if FILTER_FILE:
	filter_file = open(FILTER_FILE, 'r')
	for line in filter_file:
		sline = line.strip()
		if sline:
			REGEXPS.append(re.compile(sline))
	filter_file.close()

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

	if 0:
		db_matches = [
				{
					'teams': ['a', 'b'],
					'score': ['5', '0'],
					'date': '2001-01-01',
				},
				{
					'teams': ['a', 'b'],
					'score': ['0', '1'],
					'date': '2001-01-02',
				},
		]

	print 'Matches loaded.'

if REGEXPS:
	matches = [ ]
	for ma in db_matches:
		proceed = False
		for team in ma['teams']:
			for regexp in REGEXPS:
				if regexp.search(team):
					break
			else:
				break
		else:
			proceed = True
		if not proceed:
			continue
		matches.append(ma)
else:
	matches = db_matches


teams  = [m['teams'][0] for m in matches]
teams += [m['teams'][1] for m in matches]
teams = list(set(teams))

N = len(matches)

if RESAMPLE:
	new_matches = [ ]
	for i in xrange(N):
		new_matches.append(random.choice(matches))
	matches = new_matches

matches.sort(key = lambda ma: ma['date'])

home_teams = [ ]
away_teams = [ ]
teams = [ ]
t2i = { }
i2t = { }
xk = sp.zeros(N)
yk = sp.zeros(N)
for mai, ma in enumerate(matches):
	home_teams.append(ma['teams'][0])
	away_teams.append(ma['teams'][1])
	xk[mai] = ma['score'][0]
	yk[mai] = ma['score'][1]
	for i in [0, 1]:
		team = ma['teams'][i]
		if team not in t2i:
			teams.append(i)
			t2i[team] = len(teams) - 1
			i2t[len(teams) - 1] = team

weights = None

T = len(teams)

assert T == len(t2i)

A = sps.lil_matrix((N, T)) # Home occurences
B = sps.lil_matrix((N, T)) # Away occurences
for mai, ma in enumerate(matches):
	A[ mai, t2i[home_teams[mai]] ] = 1
	B[ mai, t2i[away_teams[mai]] ] = 1

A = A.tocsr()
B = B.tocsr()

Ta0 = sp.ones(T-1)/(T) # Attack values
Tb0 = sp.ones(T)/(T) # Defence values
g0 = sp.ones(1) # Home advantage

def lk_mk(Ta, Tb, g):
	ai = A * Ta # Home attack
	bj = B * Tb # Away defence

	aj = A * Tb # Away attack
	bi = B * Ta # Home defence

	lk = ai * bj * g[0]
	mk = aj * bi

	return lk, mk


def L(Ta, Tb, g, ret_unweighted = False):

	np.clip(Ta, 1e-8, 10., out = Ta)
	np.clip(Tb, 1e-8, 10., out = Tb)
	np.clip(g,  1e-8, 10., out = g )

	lk, mk = lk_mk(Ta, Tb, g)

	L = (
			- lk
			+ xk * sp.log(lk)
			- mk
			+ yk * sp.log(mk)
	)

	if not ret_unweighted:
		return (L*(weights/weights.sum())).sum()
	else:
		return L

def tomin(x):

	should_print = random.random() < .95

	Ta, Tb, g = decompose_x(x)

	result = -L(Ta, Tb, g)

	return result

def print_results(Ta, Tb, g):
	best = np.argsort(Ta/Ta.sum() - Tb/Tb.sum())
	for nprinted in itertools.count(1):
		print '%.3f %.3f %s' % (
				Ta[best[-nprinted]],
				Tb[best[-nprinted]],
				i2t[best[-nprinted]],
		)
		if nprinted >= min(70, T):
			break
	print 'G = %.3f' % g[0]
	print 'L = %.3f' % L(Ta, Tb, g)
	print

def print_distr_per_quantile(Ta, Tb, g):
	lk, mk = lk_mk(Ta, Tb, g)
	pcs = np.percentile(lk, sp.linspace(0, 100, 15))
	for l, h in zip(pcs[:-1], pcs[1:]):
		subs = (lk >= l) & (lk < h)
		n = subs.sum()
		m = xk[subs].mean()
		v = xk[subs].var()
		print '%.2f: n: %s m: %.2f v: %.2f' % ((h+l)/2., n, m, v)

def decompose_x(x):
	Ta = sp.zeros(T)

	Ta[1:T] = x[ 0      :   T-1   ]
	Tb 		= x[ T-1    :   2*T-1 ]
	g  		= x[ 2*T-1  :   2*T   ]
	Ta[0] = T - Ta.sum()

	return Ta, Tb, g

def optimize(leave_out_index = None, interactive_predict = False):

	global weights

	dates = [ ]
	for mai, ma in enumerate(matches):
		dates.append(datetime.date(*[int(s) for s in ma['date'].split('-')]))
	date_distances = sp.array([abs((CENTER_DATE - d).days) for d in dates])
	weights = sp.exp(-KSI * date_distances)

	if leave_out_index is not None:
		weights[leave_out_index] = 0

	min_results = spo.minimize(
			tomin,
			sp.concatenate((Ta0, Tb0, g0)),
			method = 'CG',
			# options = dict(
			# 	maxiter = 10**8,
			# )
	)

	opt = min_results['x']

	if leave_out_index is None:
		print_results(*decompose_x(opt))

	print 'T:', T
	print 'N:', N
	print min_results

	if leave_out_index is not None:
		unweighted = L(*decompose_x(opt), ret_unweighted = True)
		return unweighted[leave_out_index]

	if interactive_predict:
		import scipy.stats as ss

		Ta, Tb, g = decompose_x(opt)

		while True:
			inp = raw_input('> ').strip()
			if inp == 'exit':
				break
			team1_filt, team2_filt = inp.split()
			team1_filt = team1_filt.strip()
			team2_filt = team2_filt.strip()

			for team in t2i:
				if team1_filt in team:
					team1 = team
					break
			else:
				print 'Not found: %s' % team1_filt
				continue

			for team in t2i:
				if team2_filt in team:
					team2 = team
					break
			else:
				print 'Not found: %s' % team2_filt
				continue

			home_l = Ta[t2i[team1]] * Tb[t2i[team2]] * g[0]
			away_l = Ta[t2i[team2]] * Tb[t2i[team1]]

			ps = sp.array([0., 0., 0.])
			ps_ou = sp.array([0., 0.])
			for score1, score2 in itertools.product(range(12), repeat=2):
				p = (
						  ss.poisson(home_l).pmf(score1)
						* ss.poisson(away_l).pmf(score2)
				)
				if score1 > score2:
					ps[0] += p
				elif score1 == score2:
					ps[1] += p
				elif score1 < score2:
					ps[2] += p
				if score1 + score2 > 2.5:
					ps_ou[0] += p
				else:
					ps_ou[1] += p
			ps /= ps.sum()
			ps = 1/ps
			ps_ou /= ps_ou.sum()
			ps_ou = 1/ps_ou

			print '%s - %s: ML: %.2f - %.2f - %.2f OU: %.2f - %.2f' % (
					team1, team2,
					ps[0], ps[1], ps[2],
					ps_ou[0], ps_ou[1]
			)

	return opt


if 0:
	lools = [ ]
	for mai, ma in enumerate(matches):
		result = optimize(mai)
		print '%s/%s: LOOL: %.3f' % (
				mai + 1,
				len(matches),
				result
		)
		lools.append(result)

	print sp.mean(lools)

opt = optimize(interactive_predict = False)
