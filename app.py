#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# todo
#  - proceed_round前にadjとteamのballotが全部入力済みか確認
#  - data-importer
#  - data-outputter
#  - adjs_editを再編集の際に値が選ばれているようにする
#  - adjs_editでcancel押さずにウインドウを閉じるとstatusがeditingで残ってしまう

import locale
locale.setlocale(locale.LC_ALL, '')

CODENAME="tab"

import os, csv, cStringIO, collections, json
from time import time
from urlparse import urlparse

from flask import *
from flask.ext.pymongo import PyMongo
from pymongo import Connection
import flask.ext.login as flask_login
from werkzeug.security import check_password_hash, generate_password_hash

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
	db = connection['tab']

# init Flask Login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

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
	return sorted(sorted(data, key=lambda d: d['name']), key=lambda d: d['timediff'])

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
				db.general.insert({'maintainance':True, 'round_n':0, 'adj_timer':None, 'team_timer':None, 'adj_eva_timer':None})
				return config_function_factory(key)()
		else:
			db.general.update({}, {'$set': {key:value}})
	return _

config_round_n = config_function_factory('round_n')
config_maintainance = config_function_factory('maintainance')
config_adj_timer = config_function_factory('adj_timer')
config_adj_eva_timer = config_function_factory('adj_eva_timer')
config_team_timer = config_function_factory('team_timer')

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
	return record['tournament_name'] if record and record['tournament_name'] else default

def round_db(d, n):
	return db['round' + str(n) + '_' + d]

def result_db(d, n):
	return db['result' + str(n) + '_' + d]

def comment_db(d, n):
	return db['comment' + str(n) + '_' + d]

def session_db():
	return db['sessions']

def team_info(name):
	return first(db.teams.find({'name':name}))

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

# favicon
@app.route('/favicon.ico')
def icon_ico_callback():
	return app.send_static_file('icons/favicon.ico')
@app.route('/apple-touch-icon.png')
def icon_apple_callback():
	return app.send_static_file('icons/apple-touch-icon.png')

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

@app.route('/draw/')
def draw_callback():
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = tolist(db.draw.find())
	return render_template('draw.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, data=data)

@app.route('/draw/edit')
@flask_login.login_required
def draw_edit_callback():
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name()
	round_n = config_round_n()
	data = tolist(db.draw.find())
	return render_template('draw_edit.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, data=data, row_n=len(data), num_of_row=[i+1 for i in range(len(data))])

@app.route('/draw/edit', methods=['POST'])
@flask_login.login_required
def draw_edit_post_callback():
	data = request.get_json()
	if data is not None:
		db.draw.remove()
		for item in data:
			db.draw.insert({'gov':item['gov'], 'opp':item['opp'], 'chair':item['chair'], 'panel':item['panel'], 'venue':item['venue'], 'trainee':item['trainee']})
	return redirect('/draw/')

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
	if timediff_of('adjs', name, round_n) == -1:
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
	gov = team_info(data['round']['gov'])
	opp = team_info(data['round']['opp'])
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
			timediff_of('adjs', name, round_n, 0)
		else:
			if timediff_of('adjs', name, round_n) == -1:
				now = time()
				timediff = int(now - timer)
				timediff_of('adjs', name, round_n, timediff)
		gov, opp = data['gov'], data['opp']
		result_db('teams', round_n).update({'from':name, 'side':'gov'}, {'from':name, 'name':gov['name'], 'side':'gov', 'win':gov['win'], 'pm':gov['pm'], 'mg':gov['mg'], 'gr':gov['gr'], 'total':gov['total']}, True)
		result_db('teams', round_n).update({'from':name, 'side':'opp'}, {'from':name, 'name':opp['name'], 'side':'opp', 'win':opp['win'], 'lo':opp['lo'], 'mo':opp['mo'], 'or':opp['or'], 'total':opp['total']}, True)
	return redirect('/adjs/')

@app.route('/adjs-eva/')
def adjs_eva_callback():
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = []
	for item in round_db('adjs_eva', round_n).find():
		if len(item['round']['chair']) + len(item['round']['panel']) + len(item['round']['trainee']) > 1:
			data.append(item)

	data = sort_by_timediff(data)
	return render_template('adjs_eva.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, data=data, timediff2str=timediff2str)

@app.route('/adjs-eva/<name>/cancel/<int:round_n>')
def adjs_eva_edit_cancel_callback(name, round_n):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	if timediff_of('adjs_eva', name, round_n) == -1:
		past_status = 'unsaved'
	else:
		past_status = 'saved'
	status_of('adjs_eva', name, round_n, past_status)
	return redirect('/adjs-eva/')

@app.route('/adjs-eva/<name>/', methods=['GET'])
def adjs_eva_edit_callback(name):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = first(round_db('adjs_eva', round_n).find({'name':name}))
	past_status = status_of('adjs_eva', name, round_n)
	status_of('adjs_eva', name, round_n, 'editing')
	config = db.config.find_one()
	feedback_range = config['score_range_adj']
	other_adjs_chair = []
	other_adjs_panel = []
	other_adjs_trainee = []
	for chair in data['round']['chair']:
		if chair != data['name']:
			other_adjs_chair.append({'role':'chair', 'name':chair})
	for panel in data['round']['panel']:
		if panel != data['name']:
			other_adjs_panel.append({'role':'panel', 'name':panel})
	for trainee in data['round']['trainee']:
		if trainee != data['name']:
			other_adjs_trainee.append({'role':'trainee', 'name':trainee})
	other_adjs = []
	if data['role'] == 'chair':
		other_adjs = other_adjs_panel + other_adjs_trainee
	elif data['role'] == 'panel':
		other_adjs = other_adjs_chair
	return render_template('adjs_eva_edit.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, past_status=past_status, frange=frange, round_n=round_n, data=data, feedback_range=feedback_range, other_adjs=other_adjs, pre_float_to_str=pre_float_to_str)

@app.route('/adjs-eva/<name>/', methods=['POST'])
def adjs_eva_edit_post_callback(name):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	data = request.get_json()
	timer = config_adj_eva_timer()
	round_n = config_round_n()
	print data
	if data is not None:
		status_of('adjs_eva', name, round_n, 'saved')
		if timer is None:
			config_adj_eva_timer(time())
			timediff_of('adjs_eva', name, round_n, 0)
		else:
			if timediff_of('adjs_eva', name, round_n) == -1:
				now = time()
				timediff = int(now - timer)
		timediff_of('adjs_eva', name, round_n, 0)
		for adj in data['adjs']:
			result_db('adjs', round_n).update({'from':name, 'name':adj['name']}, {'from':name, 'name':adj['name'], 'role':adj['role'], 'score':adj['score']}, True)
	return redirect('/adjs-eva/')

@app.route('/teams/')
def teams_callback():
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = sort_by_timediff(tolist(round_db('teams', round_n).find()))
	return render_template('teams.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, data=data, timediff2str=timediff2str)

@app.route('/teams/<name>/cancel/<int:round_n>')
def teams_edit_cancel_callback(name, round_n):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	if timediff_of('teams', name, round_n) == -1:
		past_status = 'unsaved'
	else:
		past_status = 'saved'
	status_of('teams', name, round_n, past_status)
	return redirect('/teams/')

@app.route('/teams/<name>/', methods=['GET'])
def teams_edit_callback(name):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = first(round_db('teams', round_n).find({'name':name}))
	status_of('teams', name, round_n, 'editing')
	config = db.config.find_one()
	feedback_range = config['score_range_adj']
	num_of_adjs = len(data['round']['chair']) + len(data['round']['panel'])
	return render_template('teams_edit.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, frange=frange, round_n=round_n, data=data, feedback_range=feedback_range, num_of_adjs=num_of_adjs, pre_float_to_str=pre_float_to_str)

@app.route('/teams/<name>/', methods=['POST'])
def teams_edit_post_callback(name):
	if config_maintainance() and not flask_login.current_user.is_authenticated():
		return render_template('maintainance.html')
	post_data = request.get_json()
	timer = config_team_timer()
	round_n = config_round_n()
	if post_data is not None:
		status_of('teams', name, round_n, 'saved')
		if timer is None:
			config_team_timer(time())
			timediff_of('teams', name, round_n, 0)
		else:
			if timediff_of('teams', name, round_n) == -1:
				now = time()
				timediff = int(now - timer)
				timediff_of('teams', name, round_n, timediff)
		data = post_data['data']
		comment = post_data['comment']
		for item in round_db('adjs', round_n).find({'name':data['name']}):
			role = item['role']
		result_db('adjs', round_n).update({'from':name}, {'from':name, 'name':data['name'], 'role':role, 'score':data['score']}, True)
		if comment and comment['content'] and comment['content'] != '':
			comment_db('adjs', round_n).update({'from':comment['from']}, {'from':comment['from'], 'to':comment['to'], 'content':comment['content']}, True)
		return redirect('/teams/')
	return redirect('/teams/{0}/'.formtat(name))

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
		for t in ['const', 'reply', 'adj']:
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

@app.route('/admin/rollback/<int:n>', methods=['GET', 'DELETE'])
@flask_login.login_required
def admin_rollback_round_callback(n):
	round_n = config_round_n()
	db.general.update({'round_n':round_n}, {'$set':{'round_n':n}})
	return redirect('/admin/')

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
	teams = csv_reader(teams_data, lambda _, r: {'name':r[0], 'speakers':r[1:3], 'institution_scale':r[3], 'institutions':r[4:]})
	draw = csv_reader(draw_data, lambda _, r: {'gov':r[0], 'opp':r[1], 'chair':not_empty([r[2]]), 'panel':not_empty(r[3:5]), 'venue':r[5], 'trainee':[]})
	
	if teams and draw:
		db.teams.remove()
		db.teams.insert(teams)
		db.draw.remove()
		db.draw.insert(draw)
		
		data_adjs = []
		data_teams = []
		
		for r_info in db.draw.find():
			for side, team_name in [('gov', r_info['gov']), ('opp', r_info['opp'])]:
				team = {'timediff':-1, 'status':'unsaved', 'round':r_info, 'name':team_name, 'side':side}
				data_teams.append(team)
			
			for chair in r_info['chair']:
				adj = {'timediff':-1, 'status':'unsaved', 'round':r_info, 'name':chair, 'role':'chair'}
				data_adjs.append(adj)
			for panel in r_info['panel']:
				adj = {'timediff':-1, 'status':'unsaved', 'round':r_info, 'name':panel, 'role':'panel'}
				data_adjs.append(adj)
		
		round_db('adjs', next_round).remove()
		round_db('adjs', next_round).insert(data_adjs)
		round_db('adjs_eva', next_round).remove()
		round_db('adjs_eva', next_round).insert(data_adjs)
		round_db('teams', next_round).remove()
		round_db('teams', next_round).insert(data_teams)
		maintainance = config_maintainance()
		db.general.remove()
		db.general.insert({'round_n':next_round, 'adj_timer':None, 'team_timer':None, 'maintainance':maintainance})
		result_db('adjs', next_round).remove()
		result_db('teams', next_round).remove()
		return True
	return False

def csv_writer(data, header=None, **kwargs):
	csv_file = cStringIO.StringIO()
	csv.writer(csv_file, **kwargs).writerows(data)
	return csv_file.getvalue()

def make_json_response(data, filename):
	response = make_response()
	response.data = json.dumps(data)
	response.headers['Content-Type'] = 'application/octet-stream'
	response.headers['Content-Disposition'] = u'attachment; filename={0}'.format(filename)
	return response

def make_csv_response(data, filename, header=None, **kwargs):
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

@app.route('/data/round<int:n>/Results<int:m>.json')
@flask_login.login_required
def data_ballots_csv_callback(n, m):
	#results=>[team name, name, R[i] 1st, R[i] 2nd, R[i] rep, win?lose?, opponent name, gov?opp?]
	data = []
	
	for item in result_db('teams', n).find():
		it = dict(item)
		it.pop('_id')
		data.append(it)
	
	return make_json_response(data, 'Results{0}.json'.format(m))

@app.route('/data/round<n>/teams<m>.json')
@flask_login.login_required
def data_teams_callback(n, m):
	#results=>[team name, name, R[i] 1st, R[i] 2nd, R[i] rep, win?lose?, opponent name, gov?opp?]
	data = []
	
	for item in result_db('teams', n).find():
		it = dict(item)
		it.pop('_id')
		data.append(it)
	
	return make_json_response(data, 'teams{0}.json'.format(m))

@app.route('/data/round<int:n>/Results_of_adjs<int:m>.json')
@flask_login.login_required
def data_feedbacks_csv_callback(n, m):
	data = []
	
	for item in result_db('adjs', n).find():
		it = dict(item)
		it.pop('_id')
		data.append(it)
	
	return make_json_response(data, 'Results_of_adjs{0}.json'.format(m))

@app.route('/data/round<int:n>/comments.csv')
@flask_login.login_required
def data_comments_csv_callback(n):
	data = []
	for item in comment_db('adjs', n).find():
		data.append([item['to'], item['from'], item['content'].replace('\n', '\\n').encode('utf-8')])
	return make_csv_response(data, 'comments.csv', header=['to', 'from', 'comment'], quoting=csv.QUOTE_MINIMAL)

if __name__ == '__main__':
	app.run(debug=True)
