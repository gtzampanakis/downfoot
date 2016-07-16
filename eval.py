"""
An ELO system needs:

a) f(c) -> r, where c is a contestant and r his rating.
b) g(d) -> scd, where d is a rating difference and scd is a score distribution.
"""
import collections, uuid

import util

DEFAULT_RATING = 0.

NCHUNKS = 40

K = .05
H = .35

matches = [ ]
from_id = { }
with open('matches.froz.csv') as inf:
	for row in inf:
		row = row.strip()
		date, team1, team2, score1, score2, lineup1, lineup2 = row.split(';')
		lineup1 = lineup1.split(',')
		lineup2 = lineup2.split(',')
		ma = dict(
			id = uuid.uuid4().hex,
			date = date,
			teams = [team1, team2],
			team1 = team1,
			team2 = team2,
			scores = [int(score1), int(score2)],
			score1 = int(score1),
			score2 = int(score2),
			lineups = [lineup1, lineup2],
			lineup1 = lineup1,
			lineup2 = lineup2,
		)
		matches.append(ma)
		from_id[ma['id']] = ma

rmap = collections.defaultdict(lambda: DEFAULT_RATING)
total_error = 0.

for ma in matches:
	
	ratings = [[rmap[p] for p in l] for l in ma['lineups']]
	teams_ratings = [sum(rr) for rr in ratings]

	exp_sup = teams_ratings[0] - teams_ratings[1] + H
	print ma['teams'], ma['date'], exp_sup
	obs_sup = ma['scores'][0] - ma['scores'][1]

	error = obs_sup - exp_sup
	total_error += abs(error)
	correction = error * K
	correction_per_player = correction / 11.

	ma['exp_sup'] = exp_sup
	ma['obs_sup'] = obs_sup
	ma['error'] = error

	for p in ma['lineups'][0]:
		rmap[p] += correction_per_player
	for p in ma['lineups'][1]:
		rmap[p] -= correction_per_player

for p in sorted(rmap.keys(), key = lambda p: -rmap[p])[:1500]:
	print '%s    %.2f' % (p.split('.')[0], rmap[p])

print 'Total error: %s' % total_error

chunk_size = len(matches) / NCHUNKS

to_chunkify = sorted([obj for obj in matches], 
					 key = lambda ma: ma['exp_sup'])
to_chunkify = [obj['id'] for obj in to_chunkify]

chunks = util.chunkify(to_chunkify, chunk_size)

print
for chunk in chunks:
	avg_exp = util.avg([from_id[id]['exp_sup'] for id in chunk])
	avg_obs = util.avg([from_id[id]['obs_sup'] for id in chunk])
	std_obs = util.std([from_id[id]['obs_sup'] for id in chunk])
	avg_err = util.avg([from_id[id]['error'] for id in chunk])
	n = len(chunk)
	to_print = '%s %.3f %.3f %.3f %.3f' % (n, avg_exp, avg_obs, 
								 		   std_obs, avg_err/std_obs)
	print to_print

