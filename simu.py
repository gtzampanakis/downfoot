import random, itertools, numpy

ne = 11

pgeh = 1.525/ne
pgea = 1.139/ne

hist = []

for ma in itertools.count(1):
	gh, ga = 0, 0
	a = (random.random() - .5) * .3
	ph = pgeh + a
	pa = pgea - a
	for ep in xrange(ne):
		r = random.random()
		if r < ph:
			gh += 1
		elif r < ph + pa:
			ga += 1
	hist.append([gh, ga])
	if ma % 50000 == 0:
		print ma
		print numpy.mean(hist, axis = 0)
		print numpy.cov(hist, rowvar = False)
		print


