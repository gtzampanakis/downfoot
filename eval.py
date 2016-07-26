import collections, uuid, json, sqlite3, os, itertools, random
import numpy as np
import scipy as sp
import scipy.optimize as spo
import scipy.sparse as sps
import scipy.sparse.linalg as spsl

import util

DEFAULT_RATING = 0.

PS_PER_TEAM = 11

NPRINT = 0

SE_THRESHOLD = .01

LIM = 2000

ROOT_DIR = os.path.dirname(__file__)

class Evaluator:

	def __init__(self, matches, **pars):
		self.matches = matches
		for key, val in pars.iteritems():
			setattr(self, key, val)
		self.pars = pars

	def predict(self, match):
		assert self.trained
		teams_ratings = [
				sum(
					self.p2r.get(p, DEFAULT_RATING)
					for p in l
				)
				for l in match['lineups']
		]
		exp_sup = teams_ratings[0] - teams_ratings[1] + self.H
		return exp_sup

	def train(self):

		N = len(self.matches)

		H = self.pars['H']
		D = self.pars['D']

		matches = self.matches

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

		# Column vector of ratings.
		R = sp.array(rlist)

		# Column vector of observed superiorities.
		SO = sp.array(obssuplist)

		# Matrix of appearances. Columns are players, rows are matches.  First
		# using lil_matrix because it allows to build incrementally.
		A = sps.lil_matrix((N, R.size))


		for mai, ma in enumerate(matches):
			for li, l in zip([1,-1], ma['lineups']):
				assert len(l) == PS_PER_TEAM
				assert len(set(l)) == PS_PER_TEAM
				for p in l:
					A[mai, p2i[p]] = li

		# Now convert to CSC format for faster operations.
		A = A.tocsr()

		HM = sp.ones(N) * H

		assert A.sum() == 0

		##############################################
		##############################################
		##############################################
		res = spsl.lsqr(A, SO - HM, damp=N/D, show=True)
		##############################################
		##############################################
		##############################################

		R = res[0]
		rnorm = res[3]
		err = rnorm / N

		inds = np.argsort(R)

		nprinted = 0
		for ind in reversed(inds):
			if nprinted >= NPRINT:
				break
			exp = p2e[i2p[ind]]
			if exp >= 0:
				print '%s    %d    %.3f' % (i2p[ind], exp, R[ind])
				nprinted += 1

		output = { }
		self.p2r = { }
		
		for p, i in p2i.iteritems():
			self.p2r[p] = R[p2i[p]]

		self.trained = True

def get_matches():

	matches = [ ]

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
	''', [LIM])

	for row in results:
		ma_id = row[0]
		ma = json.loads(row[1])
		ma['id'] = ma_id
		matches.append(ma)

# Discard all matches that do not have 22 distinct players, for whatever
# reason.
	matches = [
		m for m in matches
		if  len(set(
			m['lineups'][0] + m['lineups'][1]
		)) == PS_PER_TEAM * 2
	]

# matches = [
# 		{
# 			'lineups': ['a', 'b'],
# 			'score':   [  0,   3],
# 		},
# 		{
# 			'lineups': ['a', 'b'],
# 			'score':   [  2,   0],
# 		},
# ]

	return matches

def cross_validate(pars):

	pH = .35

	pD = pars[0]

	full_matches = get_matches()

	N = len(full_matches)

	errs = [ ]
	for repi in itertools.count(1):
		test_index = random.randint(0, N-1)
		test_match = full_matches[test_index]
		train_matches = [
				ma for mai, ma in enumerate(full_matches)
				if mai != test_index
		]

		evaluator = Evaluator(train_matches, H = pH, D = pD)
		evaluator.train()

		prediction = evaluator.predict(test_match)
		observed = test_match['score'][0] - test_match['score'][1]

		err = abs(prediction - observed)

		errs.append(err)

		mean_err = sp.mean(errs)
		std = sp.std(errs)

		se = std / len(errs)**.5

		print '*** %d %s %.3f %.4f' % (repi, pars, mean_err, se)

		if len(errs) > 1 and se < SE_THRESHOLD:
			return mean_err

if __name__ == '__main__':
	res = spo.fmin(
			cross_validate,
			x0 = [1000.]
	)
	print res
	import pdb; pdb.set_trace()
