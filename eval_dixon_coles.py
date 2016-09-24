import collections, uuid, json, sqlite3, os, itertools, uuid, random, time
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

T = len(teams)

assert T == len(t2i)

A = sps.lil_matrix((N, T)) # Home occurences
B = sps.lil_matrix((N, T)) # Away occurences
for mai, ma in enumerate(matches):
	A[ mai, t2i[home_teams[mai]] ] = 1
	B[ mai, t2i[away_teams[mai]] ] = 1

A = A.tocsr()
B = B.tocsr()

Ta0 = sp.ones(T) # Attack values
Tb0 = sp.ones(T) # Defence values
g0 = sp.ones(1) # Home advantage

def L(Ta, Tb, g):
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
	).sum()

	return L

def tomin(x):

	should_print = random.random() < .005

	Ta = x[0    :   T    ]
	Tb = x[T    :   2*T  ]
	g  = x[2*T  :   2*T+1]

	result = -L(Ta, Tb, g)

	if should_print:
		best_a = np.argsort(Ta)
		for nprinted in itertools.count(1):
			print '%s %.3f' % (i2t[best_a[-nprinted]], Ta[best_a[-nprinted]])
			if nprinted > min(50, T-1):
				break
		print 'L = ', -result
		print

	return result

assert L(Ta0, Tb0, g0) == -tomin(sp.concatenate((Ta0, Tb0, g0)))

print spo.minimize(
		tomin,
		sp.concatenate((Ta0, Tb0, g0)),
		method = 'Nelder-Mead',
)
