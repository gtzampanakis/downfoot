"""
An ELO system needs:

a) f(c) -> r, where c is a contestant and r his rating.
b) g(d) -> scd, where d is a rating difference and scd is a score distribution.
"""
import collections

import util

DEFAULT_RATING = 0.

K = .05
H = .30

matches = [ ]
with open('matches.froz.csv') as inf:
	for row in inf:
		row = row.strip()
		date, team1, team2, score1, score2, lineup1, lineup2 = row.split(';')
		lineup1 = lineup1.split(',')
		lineup2 = lineup2.split(',')
		matches.append(dict(
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
		))

rmap = collections.defaultdict(lambda: DEFAULT_RATING)

for ma in matches:
	
	ratings = [[rmap[p] for p in l] for l in ma['lineups']]
	teams_ratings = [sum(rr) for rr in ratings]

	goals_sup = teams_ratings[0] - teams_ratings[1] + H
	print ma['teams'], ma['date'], goals_sup
	obs_sup = ma['scores'][0] - ma['scores'][1]

	error = obs_sup - goals_sup
	correction = error * K
	correction_per_player = correction / 11.

	for p in ma['lineups'][0]:
		rmap[p] += correction_per_player
	for p in ma['lineups'][1]:
		rmap[p] -= correction_per_player

for p in sorted(rmap.keys(), key = lambda p: -rmap[p]):
	print p, rmap[p]
