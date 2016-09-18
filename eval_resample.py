import collections
import glob

import scipy as sp

if 'match_to_fitted' not in globals():
	match_to_fitted = collections.defaultdict(list)

	toti = 0

	for path in glob.glob('matches_fitted/*txt'):
		with open(path, 'rb') as f:
			for line in f:
				toti += 1
				if toti % 5000 == 0:
					print toti / 1000, 'thousand'
				row = line.strip().split(',')
				date, team1, team2, score1, score2, fitted = row
				fitted = float(fitted)
				ma = (date, team1, team2, score1, score2)
				match_to_fitted[ma].append(fitted)

for ma, fitted in match_to_fitted.iteritems():
	fitted = sp.array(fitted)
	print '%s,%.3f,%.3f' % (ma, fitted.mean() - 2*fitted.std(), 
								 fitted.mean() + 2*fitted.std())

