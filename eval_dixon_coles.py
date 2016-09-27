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
dates = [ ]
for mai, ma in enumerate(matches):
	home_teams.append(ma['teams'][0])
	away_teams.append(ma['teams'][1])
	dates.append(datetime.date(*[int(s) for s in ma['date'].split('-')]))
	xk[mai] = ma['score'][0]
	yk[mai] = ma['score'][1]
	for i in [0, 1]:
		team = ma['teams'][i]
		if team not in t2i:
			teams.append(i)
			t2i[team] = len(teams) - 1
			i2t[len(teams) - 1] = team
date_distances = sp.array([abs((CENTER_DATE - d).days) for d in dates])
weights = sp.exp(-KSI * date_distances)

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

def Lold(Ta, Tb, g):
	ai = A * Ta # Home attack
	bj = B * Tb # Away defence

	aj = A * Tb # Away attack
	bi = B * Ta # Home defence

	lk = ai * bj * g[0]
	mk = aj * bi

	L = (
			- lk
			+ xk * sp.log(lk)
			- mk
			+ yk * sp.log(mk)
	)

	return L.sum()

def L(Ta, Tb, g):

	np.clip(Ta, 1e-8, 10., out = Ta)
	np.clip(Tb, 1e-8, 10., out = Tb)
	np.clip(g,  1e-8, 10., out = g )

	ai = A * Ta # Home attack
	bj = B * Tb # Away defence

	aj = A * Tb # Away attack
	bi = B * Ta # Home defence

	lk = ai * bj * g[0]
	mk = aj * bi

	L = (
			- lk
			+ xk * sp.log(lk)
			- mk
			+ yk * sp.log(mk)
	)

	# L = ai # ai is not needed anymore
	# log_lk = np.log(lk, out = bj) # nor is bj
	# log_mk = np.log(mk, out = aj) # nor is aj

	# np.negative(lk, out = L)
	# np.add(L, xk * log_lk, out = L)
	# np.subtract(L, mk, out = L)
	# np.add(L, yk * log_mk, out = L)

	return (L*weights).sum()

def tomin(x):

	should_print = random.random() < .95

	Ta, Tb, g = decompose_x(x)

	result = -L(Ta, Tb, g)

	if should_print:
		print 'L = %.3f' % -result
		print_results(Ta, Tb, g)
		print

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
	print

def decompose_x(x):
	Ta = sp.zeros(T)

	Ta[1:T] = x[ 0      :   T-1   ]
	Tb 		= x[ T-1    :   2*T-1 ]
	g  		= x[ 2*T-1  :   2*T   ]
	Ta[0] = T - Ta.sum()

	return Ta, Tb, g

def optimize():
	min_results = spo.minimize(
			tomin,
			sp.concatenate((Ta0, Tb0, g0)),
			method = 'CG',
			# options = dict(
			# 	maxiter = 10**8,
			# )
	)

	opt = min_results['x']

	print_results(*decompose_x(opt))

	print 'T:', T
	print 'N:', N
	print min_results

optimize()
