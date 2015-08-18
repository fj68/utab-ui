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

import os, csv, cStringIO
from time import time
from flask import *
from flask.ext.pymongo import PyMongo
from pymongo import Connection
from csv_mongo import CSVDataImporter as DataImporter

app = Flask(CODENAME)

MONGO_URL = os.environ.get('MONGOHQ_URL')

if MONGO_URL:
	# Get a connection
	connection = Connection(MONGO_URL)
	# Get the database
	db = connection[urlparse(MONGO_URL).path[1:]]
else:
	# Not on an app with the MongoHQ add-on, do some localhost action
	mongo = PyMongo(app)
	connection = Connection('localhost', 27017)
	db = connection['tab']

def printer(a):
	print a
	return a

def csv_reader(f, fun, skip_header=True):
	reader = csv.reader(f)
	if skip_header: next(reader)
	return [fun(i, row) for i, row in enumerate(reader)]

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

def sort_by_timediff(data):
	return sorted(sorted(data, key=lambda d: d['name']), key=lambda d: d['timediff'])

def tolist(d):
	_ = []
	for i in d:
		_.append(i)
	return _

def first(result):
	return tolist(result)[0]

def config_function_factory(key):
	def _(value=None):
		if value is None:
			record = db.general.find_one()
			if record:
				return record[key]
			else:
				db.general.insert({'round_n':0, 'adj_timer':None, 'team_timer':None})
				return config_function_factory(key)()
		else:
			db.general.update({}, {'$set': {key:value}})
	return _

config_round_n = config_function_factory('round_n')
config_adj_timer = config_function_factory('adj_timer')
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

def team_info(name):
	return first(db.teams.find({'name':name}))

@app.route('/')
@app.route('/home/')
def index_callback():
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	return render_template('index.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n)

@app.route('/adjs/')
def adjs_callback():
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = sort_by_timediff(tolist(round_db('adjs', round_n).find()))
	return render_template('adjs.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, data=data, timediff2str=timediff2str)

@app.route('/adjs/<name>/cancel/<int:round_n>')
def adjs_edit_cancel_callback(name, round_n):
	if timediff_of('adjs', name, round_n) == -1:
		past_status = 'unsaved'
	else:
		past_status = 'saved'
	status_of('adjs', name, round_n, past_status)
	return redirect('/adjs/')

@app.route('/adjs/<name>/', methods=['GET'])
def adjs_edit_callback(name):
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = first(round_db('adjs', round_n).find({'name':name}))
	status_of('adjs', name, round_n, 'editing')
	gov = team_info(data['round']['gov'])
	opp = team_info(data['round']['opp'])
	config = db.config.find_one()
	score_range = config['score_range_const']
	reply_range = config['score_range_reply']
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
	return render_template('adjs_edit.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, frange=frange, round_n=round_n, data=data, gov=gov, opp=opp, score_range=score_range, reply_range=reply_range, feedback_range=feedback_range, other_adjs=other_adjs, pre_float_to_str=pre_float_to_str)

@app.route('/adjs/<name>/', methods=['POST'])
def adjs_edit_post_callback(name):
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
	print gov
	result_db('teams', round_n).update({'from':name, 'side':'gov'}, {'from':name, 'name':gov['name'], 'side':'gov', 'win':gov['win'], 'pm':gov['pm'], 'mg':gov['mg'], 'gr':gov['gr'], 'total':gov['total']}, True)
	result_db('teams', round_n).update({'from':name, 'side':'opp'}, {'from':name, 'name':opp['name'], 'side':'opp', 'win':opp['win'], 'lo':opp['lo'], 'mo':opp['mo'], 'or':opp['or'], 'total':opp['total']}, True)
	for adj in data['adjs']:
		result_db('adjs', round_n).update({'from':name, 'name':adj['name']}, {'from':name, 'name':adj['name'], 'role':adj['role'], 'score':adj['score']}, True)
	return redirect('/adjs/')

@app.route('/teams/')
def teams_callback():
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	data = sort_by_timediff(tolist(round_db('teams', round_n).find()))
	return render_template('teams.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n, data=data, timediff2str=timediff2str)

@app.route('/teams/<name>/cancel/<int:round_n>')
def teams_edit_cancel_callback(name, round_n):
	if timediff_of('teams', name, round_n) == -1:
		past_status = 'unsaved'
	else:
		past_status = 'saved'
	status_of('teams', name, round_n, past_status)
	return redirect('/teams/')

@app.route('/teams/<name>/', methods=['GET'])
def teams_edit_callback(name):
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
	data = request.get_json()
	timer = config_team_timer()
	round_n = config_round_n()
	if data is not None:
		status_of('teams', name, round_n, 'saved')
		if timer is None:
			config_team_timer(time())
			timediff_of('teams', name, round_n, 0)
		else:
			if timediff_of('teams', name, round_n) == -1:
				now = time()
				timediff = int(now - timer)
				timediff_of('teams', name, round_n, timediff)
	for item in round_db('adjs', round_n).find({'name':data['name']}):
		role = item['role']
	result_db('adjs', round_n).update({'from':name}, {'from':name, 'name':data['name'], 'role':role, 'score':data['score']}, True)
	return redirect('/teams/')

@app.route('/admin/')
@app.route('/admin/home/')
def admin_callback():
	tournament_name = config_tournament_name(CODENAME)
	tournament_name = config_tournament_name(CODENAME)
	round_n = config_round_n()
	return render_template('admin.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, round_n=round_n)

@app.route('/admin/config/', methods=['GET'])
def admin_config_callback():
	tournament_name = config_tournament_name(CODENAME)
	data = db.config.find_one()
	return render_template('admin_config.html', PROJECT_NAME=CODENAME, tournament_name=tournament_name, data=data)

@app.route('/admin/config/', methods=['POST'])
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
def admin_rollback_round_callback(n):
	round_n = config_round_n()
	db.general.update({'round_n':round_n}, {'$set':{'round_n':n}})
	return redirect('/admin/')
@app.route('/admin/data-importer/<int:n>', methods=['POST'])
def admin_proceed_round_callback(n):
	round_n = config_round_n()
	files = request.files
	if files['teams_data'] and files['draw_data']:
		if import_data(files['teams_data'], files['draw_data'], n):
			config_round_n(n)
			
			return redirect('/admin/')
	return redirect('/admin/#dialog')

def import_data(teams_data, draw_data, next_round):
	teams = csv_reader(teams_data, lambda _, r: {'name':r[0], 'speakers':r[1:3], 'institution_scale':r[3], 'institutions':r[4:]})
	#draw = csv_reader(draw_data, lambda _, r: {'name':r[0]})
	draw = [
		{'venue': '512', 'gov':'Tokyo A', 'opp': 'Tokyo B', 'chair':['Adj1'], 'panel':['Adj2', 'Adj3'], 'trainee':[]},
		{'venue': '513', 'gov':'Tokyo C', 'opp': 'Tokyo D', 'chair':['Adj4'], 'panel':[], 'trainee':['Adj5']},
		{'venue': '514', 'gov':'Tokyo E', 'opp': 'Tokyo F', 'chair':['Adj6'], 'panel':['Adj7', 'Adj8'], 'trainee':['Adj9']},
	]
	
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
		round_db('teams', next_round).remove()
		round_db('teams', next_round).insert(data_teams)
		db.general.remove()
		db.general.insert({'round_n':next_round, 'adj_timer':None, 'team_timer':None})
		result_db('adjs', next_round).remove()
		result_db('teams', next_round).remove()
		return True
	return False

def csv_writer(data):
	csv_file = cStringIO.StringIO()
	csv.writer(csv_file, quoting=csv.QUOTE_NONNUMERIC).writerows(data)
	return csv_file.getvalue()

def make_csv_response(data, filename="data.csv"):
	response = make_response()
	response.data = csv_writer(data)
	response.headers['Content-Type'] = 'application/octet-stream'
	response.headers['Content-Disposition'] = u'attachment; filename={0}'.format(filename)
	return response

@app.route('/data/round<int:n>/ballots.csv')
def data_ballots_csv_callback(n):
	data = []
	return make_csv_response(data, 'ballots.csv')

@app.route('/data/round<int:n>/feedbacks.csv')
def data_feedbacks_csv_callback(n):
	data = []
	return make_csv_response(data, 'feedbacks.csv')

if __name__ == '__main__':
	app.run(debug=True)
