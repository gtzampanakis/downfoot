import scipy.optimize
import scipy.special as ss
import scipy.stats as sst
import os, csv, math

def fra(x1, x2, n):
	return (
			# math.factorial(n) 
			# 	/ math.factorial(x1) 
			# 	/ math.factorial(x2)
			# 	/ math.factorial(n - x1 - x2)
			ss.gamma(n+1) 
				/ ss.gamma(x1+1)
				/ ss.gamma(x2+1)
				/ ss.gamma(n - x1 - x2 + 1)
	)

def multinomial_pmf(x1, x2, n, p1, p2):
	return fra(x1, x2, n) * p1**x1 * p2**x2 * (1 - p1 - p2)**(n - x1 - x2)

for name in os.listdir('corr_score_odds'):
	print name
	fo = open(os.path.join('corr_score_odds', name), 'rb')
	rea = csv.reader(fo)

	oddset = []
	for row in rea:
		row = [int(row[0]), int(row[1]), float(row[2])]
		oddset.append(row)

	def obj(x):
		n, ph, pa = x
		sumsq = 0
		for score_odds in oddset:
			odds_derived = 1./multinomial_pmf(
					score_odds[0],
					score_odds[1],
					n, ph, pa
			)
			odds_observed = score_odds[2]
			sumsq += (odds_observed - odds_derived)**2
		return sumsq

	def obj2(x):
		lh, la = x
		sumsq = 0
		for score_odds in oddset:
			odds_derived = (
					1.
						/(sst.poisson.pmf(score_odds[0], lh))
						/(sst.poisson.pmf(score_odds[1], la))
			)
			odds_observed = score_odds[2]
			sumsq += (odds_observed - odds_derived)**2
		return sumsq

	nhat, phhat, pahat = scipy.optimize.fmin(
			obj,
			[5, .2, .1],
			full_output = 1,
			disp = 1,
			maxiter = 50000,
			maxfun = 50000,
	)[0]
	
	lhhat, lahat = scipy.optimize.fmin(
			obj2,
			[1.5, 1.0],
			full_output = 1,
			disp = 1,
			maxiter = 50000,
			maxfun = 50000,
	)[0]

	print nhat, phhat, pahat
	print lhhat, lahat
	for score_odds in oddset:
		print (
				name,
				score_odds[0], 
				score_odds[1], 
				score_odds[2], 
				round(1./multinomial_pmf(
					score_odds[0], score_odds[1],
					nhat, phhat, pahat
				), 2),
				round(1./sst.poisson.pmf(
					score_odds[0], lhhat
				)/sst.poisson.pmf(score_odds[1], lahat) , 2),
		)
