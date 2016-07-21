import os, collections, logging, re, heapq, sys, sqlite3
import json
import downloader

_LOGGER = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(__file__)

MATCHES_LIMIT = 400000

YEARS = range(2015, 2003, -1)
STALE = 9999

DATE_RE = re.compile(r'\d{4}-[01]\d-[0123]\d')
SCORE_RE = re.compile(r'^(\d{1,2}):(\d{1,2})($|[(])')
PLAYER_RE = re.compile(r'^[a-z0-9A-F%-]{2,}.\d{1,}$')

matches = [ ]

def get_conn():
	conn = sqlite3.connect(os.path.join(ROOT_DIR, 'matches.db'))
	conn.executescript('''
		create table if not exists matches(
			id integer primary key autoincrement,
			date text not null,
			team1 text not null,
			team2 text not null,
			match_json text not null
		);
		create index if not exists matches_date on matches(date);
		create unique index if not exists uniqueness1 on matches(
												team1, team2, date);
	''')
	return conn

conn = None
def store_match(match_dict):
	global conn
	if conn is None:
		conn = get_conn()
	try:
		conn.execute('''
			insert or ignore into matches
			(date, team1, team2, match_json)
			values
			(?, ?, ?, ?)
		''', [
			match_dict['date'],
			match_dict['teams'][0],
			match_dict['teams'][1],
			json.dumps(match_dict)
		])
	except Exception as e:
		conn.rollback()
		raise
	finally:
		conn.commit()

def comps_handler(crawl_element):

	result = collections.defaultdict(list)

	elems = crawl_element.xpath(
		"//div[@id='yw1']//td[@class='hauptlink']//a[1][@title]",
		[5, None]
	)
	for elemi, elem in enumerate(elems):
		href = elem.element.get('href')
		href = href.replace('startseite', 'gesamtspielplan')
		for year in YEARS:
			to_add = href + '?saison_id=' + str(year)
			result[comp_handler].append(downloader.CrawlURL(to_add, STALE))
	page_elems = crawl_element.xpath("//li[@class='page']/a", [2, None])
	for page_elem in page_elems:
		result[comps_handler].append(downloader.CrawlURL(
								page_elem.element.get('href'), STALE))

	urls = []

	# CHL
	urls += [
		downloader.CrawlURL(
			'http://www.transfermarkt.com/uefa-champions-league'
			'/gesamtspielplan/pokalwettbewerb/CL/saison_id/%s' % year,
			STALE
		)
		for year in YEARS
	]

	# CHL qual
	urls += [
		downloader.CrawlURL(
			'http://www.transfermarkt.com/uefa-cl-qualifikation'
			'/gesamtspielplan/pokalwettbewerb/CLQ/saison_id/%s' % year,
			STALE
		)
		for year in YEARS
	]

	# EUL
	urls += [
		downloader.CrawlURL(
			'http://www.transfermarkt.com/europa-league'
			'/gesamtspielplan/pokalwettbewerb/EL/saison_id/%s' % year,
			STALE
		)
		for year in YEARS
	]

	# EUL qual
	urls += [
		downloader.CrawlURL(
			'http://www.transfermarkt.com/europa-league-qualifikation'
			'/gesamtspielplan/pokalwettbewerb/ELQ/saison_id/%s' % year,
			STALE
		)
		for year in YEARS
	]

	for url in urls:
		result[comp_handler].append(url)

	return result

def comp_handler(crawl_element):
	result = collections.defaultdict(list)
	elems = crawl_element.xpath("//a[@title='Match report']")
	for elemi, elem in enumerate(elems):
		if '-:-' in elem.text_content():
			continue
		href = elem.element.get('href')
		result[match_handler].append(downloader.CrawlURL(href, STALE))
	return result

def match_handler(crawl_element):
	result = collections.defaultdict(list)

	if crawl_element.xpath("//div[text() = '(uncontested)']"):
		return

	date_elem = crawl_element.xpath_one(
		"//div/div/div/div/p[@class='sb-datum hide-for-small']"
		"/a[contains(@href, '/datum')]"
	)
	href = date_elem.element.get('href')
	mo = DATE_RE.search(href)
	if not mo:
		raise Exception(href)
	date_string = mo.group(0)

	team1_elem = crawl_element.xpath_one(
		"//div/div[@class='box sb-spielbericht-head']"
		"/div[@class='box-content']"
		"/div[@class='sb-team sb-heim hide-for-small']"
		"/a[2]"
	)
	team2_elem = crawl_element.xpath_one(
		"//div/div[@class='box sb-spielbericht-head']"
		"/div[@class='box-content']"
		"/div[@class='sb-team sb-gast hide-for-small']"
		"/a[2]"
	)
	team1_id = team1_elem.element.get('href').split('/')[3]
	team2_id = team2_elem.element.get('href').split('/')[3]
	team1_id += '.'
	team2_id += '.'
	team1_id += team1_elem.element.get('href').split('/')[6]
	team2_id += team2_elem.element.get('href').split('/')[6]

	score_elem = crawl_element.xpath_one(
		"//div/div/div/div/div[@class='sb-ergebnis']/div[@class='sb-endstand']"
	)
	score_text = score_elem.text_content().strip()
	score_mo = SCORE_RE.match(score_text)
	if not score_mo:
		if (
			'PENS' in score_elem.text_content() 
				or 
			'AET' in score_elem.text_content()
				or
			'-:-' in score_elem.text_content()
		):
			return
		else:
			raise Exception(score_text)
	score1 = int(score_mo.group(1))
	score2 = int(score_mo.group(2))

	lineups = [[], []]
	try:
		for team_index in [0, 1]:
			for player_index in xrange(1, 12):
				if team_index == 0:
					player_elem = crawl_element.xpath_pick_one([
						"//div[2]/div[3]/div[2]"
						"/div[@class='aufstellung-spieler-container' "
						"and @style][%s]"
						"/div[2]/span/a" % player_index,
						"(//div[2]"
						"/div/table"
						"//tr/td/a[@class='spielprofil_tooltip' and @id])[%s]"
						% player_index
					])
				elif team_index == 1:
					player_elem = crawl_element.xpath_pick_one([
						"//div[3]/div[3]/div[2]"
						"/div[@class='aufstellung-spieler-container' "
						"and @style][%s]"
						"/div[2]/span/a"
						% player_index,
						"(//div[3]"
						"/div/table"
						"//tr/td/a[@class='spielprofil_tooltip' and @id])[%s]"
						% player_index
					])
				href = player_elem.element.get('href')
				player_id = href.split('/')[3]
				player_id += '.'
				player_id += href.split('/')[6]
				assert PLAYER_RE.match(player_id), player_id
				lineups[team_index].append(player_id)
	except downloader.UnexpectedContentException as e:
		# There are cases where lineups are not available, for example when the
		# match was uncontested. Example: https://tinyurl.com/h6da9uu
		return 

	assert lineups[0] != lineups[1]
	match = {
		'date': date_string,
		'teams': [team1_id, team2_id],
		'score': [score1, score2],
		'lineups': lineups,
	}
	store_match(match)
	matches.append(match)
	if len(matches) % 25 == 0:
		print 'Matches so far:', len(matches)
		print 'Last match:', matches[-1]
	
	if len(matches) >= MATCHES_LIMIT:
		sys.exit(0)

	return

def crawl():
	db_path = os.path.join(ROOT_DIR, 'pages.db')

	crawler = downloader.Crawler(
		comps_handler,
		downloader.CrawlURL(
			'http://www.transfermarkt.com/?ajax=yw1&page=2&plus=1&seo=wettbewerbe', STALE),
		db_path,
		[.2, 4]
	)
	crawler.crawl()

if __name__ == '__main__':
	logging.basicConfig(level = logging.INFO)

	crawl()

