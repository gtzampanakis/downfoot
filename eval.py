import collections, uuid, json, sqlite3, os

import util

DEFAULT_RATING = 0.

NCHUNKS = 25

ROOT_DIR = os.path.dirname(__file__)

PLAYER_TO_TRACK = 'cristiano-ronaldo'

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
	select id, match_json
	from matches
	order by date
''')

for row in results:
	ma_id = row[0]
	ma = json.loads(row[1])
	ma['id'] = ma_id
	from_id[ma_id] = ma
	matches.append(ma)

rmap = collections.defaultdict(lambda: DEFAULT_RATING)
total_error = 0.

for ma in matches:
	
	ratings = [[rmap[p] for p in l] for l in ma['lineups']]
	teams_ratings = [sum(rr) for rr in ratings]

	exp_sup = teams_ratings[0] - teams_ratings[1] + H
	print (
		'%s %s %.3f-%.3f %.3f' % (
			ma['teams'], ma['date'], teams_ratings[0], teams_ratings[1], exp_sup
		)
	)
	obs_sup = ma['score'][0] - ma['score'][1]

	error = obs_sup - exp_sup
	total_error += abs(error)
	correction = error * K
	correction_per_player = correction / 11.

	ma['sum_team_ratings'] = sum(teams_ratings)
	ma['team_ratings'] = teams_ratings
	ma['exp_sup'] = exp_sup
	ma['obs_sup'] = obs_sup
	ma['abs_error'] = abs(error)
	ma['abs_error_of_dumb'] = abs(obs_sup - H)

	for p in ma['lineups'][0]:
		if p.split('.')[0] == PLAYER_TO_TRACK:
			print 'TRACKING (%s): %.3f' % (p.split('.')[0], rmap[p])
		rmap[p] += correction_per_player
	for p in ma['lineups'][1]:
		if p.split('.')[0] == PLAYER_TO_TRACK:
			print 'TRACKING (%s): %.3f' % (p.split('.')[0], rmap[p])
		rmap[p] -= correction_per_player

for p in sorted(rmap.keys(), key = lambda p: -rmap[p])[:1500]:
	print '%s    %.3f' % (p.split('.')[0], rmap[p])

print 'Total error: %s' % total_error

chunk_size = len(matches) / NCHUNKS


to_chunkify = sorted(matches, 
					 key = lambda ma: ma['exp_sup'])
to_chunkify = [obj['id'] for obj in to_chunkify]

chunks = util.chunkify(to_chunkify, chunk_size)

print
for chunk in chunks:
	avg_exp = util.avg([from_id[id]['exp_sup'] for id in chunk])
	avg_err_d = util.avg([from_id[id]['abs_error_of_dumb'] for id in chunk])
	avg_err = util.avg([from_id[id]['abs_error'] for id in chunk])
	n = len(chunk)
	to_print = '%s %.3f %.3f %.3f' % (n, avg_exp, avg_err_d, avg_err)
	print to_print


to_chunkify = sorted(matches, 
					 key = lambda ma: ma['sum_team_ratings'])
to_chunkify = [obj['id'] for obj in to_chunkify]

chunks = util.chunkify(to_chunkify, chunk_size)

print
for chunk in chunks:
	avg_sum = util.avg([from_id[id]['sum_team_ratings'] for id in chunk])
	avg_err_d = util.avg([from_id[id]['abs_error_of_dumb'] for id in chunk])
	avg_err = util.avg([from_id[id]['abs_error'] for id in chunk])
	n = len(chunk)
	to_print = '%s %.3f %.3f %.3f' % (n, avg_sum, avg_err_d, avg_err)
	print to_print

