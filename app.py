#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import locale
locale.setlocale(locale.LC_ALL, '')

CODENAME="utab"

import sys, os, csv, cStringIO, collections, json
from time import time
from urlparse import urlparse

from flask import *
from flask.ext.pymongo import PyMongo
from pymongo import Connection
import flask.ext.login as flask_login
from werkzeug.security import check_password_hash, generate_password_hash

from json2csv import json2list, json2list_rym

# init Flask and create app
app = Flask(CODENAME)
app.secret_key = 'futamuranization'

# init MongoDB
MONGO_URL = os.environ.get('MONGOLAB_URI')

if MONGO_URL:
	# Get a connection
	connection = Connection(MONGO_URL)
	# Get the database
	db = connection[urlparse(MONGO_URL).path[1:]]
else:
	# Not on an app with the MongoHQ add-on, do some localhost action
	#mongo = PyMongo(app)
	connection = Connection('localhost', 27017)
	db = connection['utab']

# init Flask Login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

# add admin to session
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'nimda'

# User Object for session control with flask.ext.login
class User():
	def __init__(self, name, active=True):
		self.name = name
		self.active = active
	def is_anonymous(self):
		return False
	def is_authenticated(self):
		return True
	def is_active(self):
		return self.active
	def get_id(self):
		return self.name
	@staticmethod
	def validate_login(password_hash, password):
		return check_password_hash(password_hash, password)
	@staticmethod
	def get_login_hash(password):
		return generate_password_hash(password)

@login_manager.user_loader
def load_user(user_id):
	session = session_db().find_one({'name':user_id})
	return User(session['name']) if session and 'name' in session and session['name'] else None

@login_manager.unauthorized_handler
def unauthorized_callback():
	return redirect('/login/')

# for debug
def printer(a):
	print a
	return a

# general reader
def csv_reader(f, fun, skip_header=True):
	reader = csv.reader(f)
	if skip_header: next(reader)
	return [fun(i, row) for i, row in enumerate(reader)]

# utilities for templates

def frange(start, stop, step):
	x = start
	stop -= 1
	while x <= stop:
		yield x
		x += step

def is_str_of_float(s):
	return not (s.find('.') == -1)

def pre_float_to_str(f):
	if is_str_of_float(str(f)):
		if not str(f).find('.0') == -1:
			return str(int(f))
	return str(f)

def timediff2str(timediff):
	m = timediff / 60
	s = timediff - m*60
	return '{m}\'{s:02d}\'\''.format(m=m, s=s)

# utilities for db data
def sort_by_timediff(data):
	return sorted(sorted(data, key=lambda d: d['name']), key=lambda d: d['timediff'][0])

def sort_by_venue(data):
	return sorted(data, key=lambda d: d['venue'])

def tolist(d):
	_ = []
	for i in d:
		_.append(i)
	return _

def first(result):
	return tolist(result)[0]

# shortcuts for db control
def config_function_factory(key):
	def _(value=None):
		if value is None:
			record = db.general.find_one()
			if record:
				return record[key]
			else:
				db.general.insert({'maintainance':True, 'round_n':0, 'adj_timer':None})
				return config_function_factory(key)()
		else:
			db.general.update({}, {'$set': {key:value}})
	return _

config_round_n = config_function_factory('round_n')
config_maintainance = config_function_factory('maintainance')
config_adj_timer = config_function_factory('adj_timer')

def round_db_function_factory(key):
	def _(db, name, round_n, value=None):
		if value is None:
			return first(round_db(db, round_n).find({'name':name}))[key]
		else:
			round_db(db, round_n).update({'name':name}, {'$set':{key:value}})
	return _

timediff_of = round_db_function_factory('timediff')
status_of = round_db_function_factory('status')

def config_tournament_name(default=""):
	record = db.config.find_one()
	return record['tournament_name'] if record and 'tournament_name' in record else default

def round_db(d, n):
	return db['round' + str(n) + '_' + d]

def result_db(d, n):
	return db['result' + str(n) + '_' + d]

def draw_db(n):
	return db['draw' + str(n)]

def teams_db(n):
	return db['teams' + str(n)]

def comment_db(d, n):
	return db['comment' + str(n) + '_' + d]

def session_db():
	return db['sessions']

def team_info(n, name):
	return first(teams_db(n).find({'name':name}))

# list flattener
def flatten(l):
	i = 0
	while i < len(l):
		while isinstance(l[i], collections.Iterable) and not isinstance(l[i], basestring):
			if not l[i]:
				l.pop(i)
				i -= 1
				break
			else:
				l[i:i + 1] = l[i]
		i += 1
	return l

# add sessions
if session_db().find({'name':ADMIN_USERNAME}).count() <= 0:
	session_db().insert({'name':ADMIN_USERNAME, 'password':generate_password_hash(ADMIN_PASSWORD)})
else:
	session_db().update({'name':ADMIN_USERNAME}, {'$set': {'name':ADMIN_USERNAME, 'password':generate_password_hash(ADMIN_PASSWORD)}})

# favicon
@app.route('/favicon.ico')
def icon_ico_callback():
	return app.send_static_file('icons/favicon.ico')
@app.route('/apple-touch-icon.png')
def icon_apple_callback():
	return app.send_static_file('icons/apple-touch-icon.png')
@app.route('/icons/manifest.json')
def icon_manifest_callback():
	data = {}
	with open('./templates/manifest.json') as f:
		data = json.load(f)
	data['name'] = config_tournament_name(CODENAME)
	return make_json_response(data)

# manual
@app.route('/admin/manual/')
@flask_login.login_required
def manual_callback():
	#if config_maintainance() and not flask_login.current_user.is_authenticated():
	#	return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	return render_template('man.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name)

# root
@app.route('/')
@app.route('/home/')
def index_callback():
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	return render_template('index.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n)

# for session control
def next_is_valid(next):
	return next and next[:1] == '/'

@app.route('/login/', methods=['GET', 'POST'])
def login_callback():
	tournament_name = config_tournament_name(CODENAME)
	data = request.form if request.method == 'POST' else None
	if data:
		user = session_db().find_one({'name':data['username']})
		if user and User.validate_login(user['password'], data['password']):
			user_obj = User(user['name'])
			flask_login.login_user(user_obj)
			flask_login.flash("Logged in successfully", category='success')
			next = request.args.get('next')
			if not next_is_valid(next):
				next = '/admin/'
			
			return redirect(next or '/admin/')
		flask_login.flash("Wrong username or password", category='error')
	return render_template('login.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name)

@app.route('/logout/')
def logout_callback():
	flask_login.logout_user()
	return redirect('/login/')

@app.route('/draw/<int:n>/')
def draw_callback(n):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = tolist(draw_db(n).find())
	return render_template('draw.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, n=n, data=data)

@app.route('/draw/<int:n>/edit')
@flask_login.login_required
def draw_edit_callback(n):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name()
	round_n = config_round_n()
	data = tolist(draw_db(n).find())
	return render_template('draw_edit.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, n=n, data=data, row_n=len(data), num_of_row=[i+1 for i in range(len(data))])

@app.route('/draw/<int:n>/edit', methods=['POST'])
@flask_login.login_required
def draw_edit_post_callback(n):
	data = request.get_json()
	if data is not None:
		draw_db(n).remove()
		for item in data:
			draw_db(n).insert({'gov':item['gov'], 'opp':item['opp'], 'chair':item['chair'], 'panel':item['panel'], 'venue':item['venue'], 'trainee':item['trainee']})
	return redirect('/draw/{0}'.format(n))

@app.route('/adjs/')
def adjs_callback():
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = sort_by_timediff(tolist(round_db('adjs', round_n).find()))
	return render_template('adjs.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, data=data, timediff2str=timediff2str)

@app.route('/adjs/<name>/cancel/<int:round_n>')
def adjs_edit_cancel_callback(name, round_n):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	if timediff_of('adjs', name, round_n)[0] == -1:
		past_status = 'unsaved'
	else:
		past_status = 'saved'
	status_of('adjs', name, round_n, past_status)
	return redirect('/adjs/')

@app.route('/adjs/<name>/', methods=['GET'])
def adjs_edit_callback(name):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = first(round_db('adjs', round_n).find({'name':name}))
	past_status = status_of('adjs', name, round_n)
	status_of('adjs', name, round_n, 'editing')
	gov = team_info(round_n, data['round']['gov'])
	opp = team_info(round_n, data['round']['opp'])
	config = db.config.find_one()
	score_range = config['score_range_const']
	reply_range = config['score_range_reply']
	return render_template('adjs_edit.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, past_status=past_status, frange=frange, round_n=round_n, data=data, gov=gov, opp=opp, score_range=score_range, reply_range=reply_range, pre_float_to_str=pre_float_to_str)

@app.route('/adjs/<name>/', methods=['POST'])
def adjs_edit_post_callback(name):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	data = request.get_json()
	timer = config_adj_timer()
	round_n = config_round_n()
	if data is not None:
		status_of('adjs', name, round_n, 'saved')
		if timer is None:
			config_adj_timer(time())
			timediff_of('adjs', name, round_n, [0])
		else:
			p_td = timediff_of('adjs', name, round_n)
			now = time()
			timediff = int(now - timer)
			if p_td[0] == -1:
				timediff_of('adjs', name, round_n, [timediff])
			else:
				p_td.append(timediff)
				print p_td
				timediff_of('adjs', name, round_n, p_td)
		gov, opp = data['gov'], data['opp']
		result_db('teams', round_n).update({'from':name, 'side':'gov'}, {'from':name, 'name':gov['name'], 'side':'gov', 'win':gov['win'], 'pm':gov['pm'], 'mg':gov['mg'], 'gr':gov['gr'], 'total':gov['total'], 'opponent':opp['name']}, True)
		result_db('teams', round_n).update({'from':name, 'side':'opp'}, {'from':name, 'name':opp['name'], 'side':'opp', 'win':opp['win'], 'lo':opp['lo'], 'mo':opp['mo'], 'or':opp['or'], 'total':opp['total'], 'opponent':gov['name']}, True)
	return redirect('/adjs/#thanks')

@app.route('/admin/')
@app.route('/admin/home/')
@flask_login.login_required
def admin_callback():
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	maintainance = config_maintainance()
	return render_template('admin.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, maintainance=maintainance)

@app.route('/admin/config/', methods=['GET'])
@flask_login.login_required
def admin_config_callback():
	tournament_name = config_tournament_name(CODENAME)
	data = db.config.find_one()
	return render_template('admin_config.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, data=data)

@app.route('/admin/config/', methods=['POST'])
@flask_login.login_required
def admin_config_post_callback():
	_ = request.form
	if _ is not None:
		data = {}
		data['tournament_name'] = _['tournament_name']
		for t in ['const', 'reply']:
			t_min = _['score_range_' + t + '_min']
			t_max = _['score_range_' + t + '_max']
			t_step = _['score_range_' + t + '_step']
			if is_str_of_float(t_min) or is_str_of_float(t_max) or is_str_of_float(t_step):
				t_min = float(t_min)
				t_max = float(t_max)
				t_step = float(t_step)
			else:
				t_min = int(t_min)
				t_max = int(t_max)
				t_step = int(t_step)
			data['score_range_' + t] = {
				'min': t_min,
				'max': t_max,
				'step': t_step
			}
		
		db.config.remove()
		db.config.insert(data)
		return redirect('/admin/')
	return redirect('/admin/config/')

# info board
@app.route('/$$$_info_board_$$$')
def info_board_callback():
	data = db.info_board.find_one()
	if data:
		data.pop('_id')
	else:
		data = {}
	return make_json_response(data)

@app.route('/admin/info-board/')
@flask_login.login_required
def admin_info_board_callback():
	tournament_name = config_tournament_name(CODENAME)
	data = db.info_board.find_one()
	if data:
		data.pop('_id')
	else:
		data = {}
	return render_template('admin_info_board.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, data=data)

@app.route('/admin/info-board/', methods=['POST'])
@flask_login.login_required
def admin_info_board_post_callback():
	_ = request.form
	if _ is not None:
		data = {
			'title':_['info_title'],
			'body':_['info_body']
		}
		db.info_board.remove()
		db.info_board.insert(data)
		return redirect('/admin/')
	return redirect('/admin/info-board/')

@app.route('/admin/rollback/<int:n>', methods=['GET', 'DELETE'])
@flask_login.login_required
def admin_rollback_round_callback(n):
	round_n = config_round_n()
	db.general.update({'round_n':round_n}, {'$set':{'round_n':n}})
	db.general.update({'round_n':round_n}, {'$set':{'adj_timer':None}})
	for i in xrange(n + 1, round_n - n + 1):
		round_db('adjs', i).remove()
		result_db('teams', i).remove()
		draw_db(i).remove()
		teams_db(i).remove()
		
	return redirect('/admin/')

@app.route('/admin/account', methods=['POST'])
@flask_login.login_required
def admin_account_callback():
	data = request.get_json()
	user = session_db().find_one({'name':data['old_u']})
	if user and 'name' in user and user['name']:
		if User.validate_login(user['password'], data['old_p']):
			session_db().remove({'name':data['old_u']})
			session_db().insert({'name':data['new_u'], 'password':generate_password_hash(data['new_p'])})
			return 'Success'
		else:
			return 'Fail: Password is incorrect.'
	return 'Fail: No such name in database, \"{0}\"'.format(data['old_u'])

@app.route('/admin/maintainance/<to>', methods=['GET'])
@flask_login.login_required
def admin_maintainance_callback(to):
	round_n = config_round_n()
	db.general.update({'round_n':round_n}, {'$set':{'maintainance':(to == 'on')}})
	return redirect('/admin/')

@app.route('/admin/data-importer/<int:n>', methods=['POST'])
@flask_login.login_required
def admin_proceed_round_callback(n):
	round_n = config_round_n()
	files = request.files
	if files['teams_data'] and files['draw_data']:
		if import_data(files['teams_data'], files['draw_data'], n):
			config_round_n(n)
			
			return redirect('/admin/')
	return redirect('/admin/')

def not_empty(l):
	return [n for n in l if n != '']

def import_data(teams_data, draw_data, next_round):
	teams = csv_reader(teams_data, lambda _, r: {'name':r[0], 'speakers':r[1:4], 'institution_scale':r[4], 'institutions':r[5:]})
	draw = csv_reader(draw_data, lambda _, r: {'gov':r[0], 'opp':r[1], 'chair':not_empty([r[2]]), 'panel':not_empty(r[3:5]), 'venue':r[5], 'trainee':[]})
	
	if teams and draw:
		teams_db(next_round).remove()
		teams_db(next_round).insert(teams)
		draw_db(next_round).remove()
		draw_db(next_round).insert(draw)
		
		data_adjs = []
		
		for r_info in draw_db(next_round).find():
			for chair in r_info['chair']:
				adj = {'timediff':[-1], 'status':'unsaved', 'round':r_info, 'name':chair, 'role':'chair'}
				data_adjs.append(adj)
			for panel in r_info['panel']:
				adj = {'timediff':[-1], 'status':'unsaved', 'round':r_info, 'name':panel, 'role':'panel'}
				data_adjs.append(adj)
		
		round_db('adjs', next_round).remove()
		round_db('adjs', next_round).insert(data_adjs)
		maintainance = config_maintainance()
		db.general.remove()
		db.general.insert({'round_n':next_round, 'adj_timer':None, 'maintainance':maintainance})
		result_db('adjs', next_round).remove()
		return True
	return False

def csv_writer(data, header=None, **kwargs):
	csv_file = cStringIO.StringIO()
	csv.writer(csv_file, **kwargs).writerows(data)
	return csv_file.getvalue()

def make_text_response(data, filename=None, filetype=None):
	response = make_response()
	response.data = data
	filetype = filetype if filetype is not None else 'text/plain'
	if filename is None:
		response.headers['Content-Type'] = filetype
	else:
		response.headers['Content-Type'] = 'application/octet-stream'
		response.headers['Content-Disposition'] = u'attachment; filename={0}'.format(filename)
	return response

def make_json_response(data, filename=None):
	response = make_response()
	response.data = json.dumps(data)
	if filename is None:
		response.headers['Content-Type'] = 'application/json'
	else:
		response.headers['Content-Type'] = 'application/octet-stream'
		response.headers['Content-Disposition'] = u'attachment; filename={0}'.format(filename)
	return response

def make_csv_response(data, filename=None, header=None, **kwargs):
	if header:
		data.insert(0, header)
	response = make_response()
	response.data = csv_writer(data, **kwargs)
	if filename is None:
		response.headers['Content-Type'] = 'text/csv'
	else:
		response.headers['Content-Type'] = 'application/octet-stream'
		response.headers['Content-Disposition'] = u'attachment; filename={0}'.format(filename)
	return response

def get_results_as_json(n):
	data = []
	for item in result_db('teams', n).find():
		it = dict(item)
		it.pop('_id')
		data.append(it)
	return data

@app.route('/data/round<int:n>/Results<int:m>.json')
@flask_login.login_required
def data_ballots_json_callback(n, m):
	#results=>[team name, name, R[i] 1st, R[i] 2nd, R[i] rep, win?lose?, opponent name, gov?opp?]
	return make_json_response(get_results_as_json(n), 'Results{0}.json'.format(m))

@app.route('/data/round<int:n>/Results<int:m>.csv')
@flask_login.login_required
def data_ballots_csv_callback(n, m):
	data = json2list_rym(get_results_as_json(n))
	return make_csv_response(data, 'Results{0}.csv'.format(m), header=['team name', 'name', '1st score', '2nd score', '3rd score', 'win', 'opponent', 'side'])

@app.route('/data/round<int:n>/Results<int:m>_sep.csv')
@flask_login.login_required
def data_ballots_csv_sep_callback(n, m):
	data = json2list(get_results_as_json(n))
	return make_csv_response(data, 'Results{0}_sep.csv'.format(m), header=['team name', 'name', '1st score A', '1st score B', '2nd score A', '2nd score B', '3rd score A', '3rd score B', 'win', 'opponent', 'side'])

if __name__ == '__main__':
	if len(sys.argv) == 2:
		app.run(host=sys.argv[1])
	elif len(sys.argv) == 3:
		app.run(host=sys.argv[1], port=int(sys.argv[2]))
	else:
		app.run(debug=True)
