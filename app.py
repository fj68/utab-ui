#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# todo
#  - proceed_round前にadjとteamのballotが全部入力済みか確認
#  - data-importer
#  - data-outputter
#  - teams_edit
#  - adjs_editを再編集の際に値が選ばれているようにする

import locale
locale.setlocale(locale.LC_ALL, '')

CODENAME="tab"

import os
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
	return str(m) + '\'' + str(s) + '\'\''

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
			return db.general.find_one()[key]
		else:
			db.general.update({}, {'$set': {key:value}})
	return _

config_round_n = config_function_factory('round_n')
config_adj_timer = config_function_factory('adj_timer')
config_team_timer = config_function_factory('team_timer')

def round_db_function_factory(key):
	def _(name, round_n, value=None):
		if value is None:
			return first(round_db(round_n).find({'name':name}))[key]
		else:
			round_db(round_n).update({'name':name}, {'$set':{key:value}})
	return _

timediff_of = round_db_function_factory('timediff')
status_of = round_db_function_factory('status')

def round_db(n):
	return db['round' + str(n)]

@app.route('/')
@app.route('/home/')
def index_callback():
	round_n = config_round_n()
	return render_template('index.html', PROJECT_NAME=CODENAME, round_n=round_n)

debug_data = [
	{'timediff':-1, 'status':'unsaved', 'name':'Adj1', 'role':'chair', 'round': {'venue': '512', 'gov':'Team A', 'opp': 'Team B', 'chair':['Adj1'], 'panel':['Adj2', 'Adj3'], 'trainee':[]}},
	{'timediff':-1, 'status':'unsaved', 'name':'Adj2', 'role':'panel', 'round': {'venue': '512', 'gov':'Team A', 'opp': 'Team B', 'chair':['Adj1'], 'panel':['Adj2', 'Adj3'], 'trainee':[]}},
	{'timediff':-1, 'status':'unsaved', 'name':'Adj3', 'role':'panel', 'round': {'venue': '512', 'gov':'Team A', 'opp': 'Team B', 'chair':['Adj1'], 'panel':['Adj2', 'Adj3'], 'trainee':[]}}
]
debug_is_first_visit = True

def debug_data_import():
	global debug_is_first_visit
	if debug_is_first_visit:
		debug_is_first_visit = False
		round_db(1).remove()
		round_db(1).insert(debug_data)
		db.general.remove()
		db.general.insert({'round_n':1, 'adj_timer':None, 'team_timer':None})

@app.route('/adjs/')
def adjs_callback():
	debug_data_import()
	round_n = config_round_n()
	data = sort_by_timediff(tolist(db['round' + str(round_n)].find()))
	return render_template('adjs.html', PROJECT_NAME=CODENAME, round_n=round_n, data=data, timediff2str=timediff2str)

@app.route('/adjs/<name>/cancel/<int:round_n>')
def adjs_edit_cancel_callback(name, round_n):
	if timediff_of(name, round_n) == -1:
		past_status = 'unsaved'
	else:
		past_status = 'saved'
	status_of(name, round_n, past_status)
	return redirect('/adjs/')

@app.route('/adjs/<name>/', methods=['GET'])
def adjs_edit_callback(name):
	round_n = config_round_n()
	data = first(round_db(round_n).find({'name':name}))
	status_of(name, round_n, 'editing')
	gov = {'name':'Team A', 'speakers': ['Sp1', 'Sp2']}
	opp = {'name':'Team B', 'speakers': ['Sp3', 'Sp4']}
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
	for treinee in data['round']['trainee']:
		if treinee != data['name']:
			other_adjs_trainee.append({'role':'trainee', 'name':trainee})
	other_adjs = []
	if data['role'] == 'chair':
		other_adjs = other_adjs_panel + other_adjs_trainee
	elif data['role'] == 'panel':
		other_adjs = other_adjs_chair
	return render_template('adjs_edit.html', PROJECT_NAME=CODENAME, frange=frange, round_n=round_n, data=data, gov=gov, opp=opp, score_range=score_range, reply_range=reply_range, feedback_range=feedback_range, other_adjs=other_adjs, pre_float_to_str=pre_float_to_str)

@app.route('/adjs/<name>/', methods=['POST'])
def adjs_edit_post_callback(name):
	data = request.get_json()
	timer = config_adj_timer()
	round_n = config_round_n()
	if data is not None:
		status_of(name, round_n, 'saved')
		if timer is None:
			config_adj_timer(time())
			timediff_of(name, round_n, 0)
		else:
			if timediff_of(name, round_n) == -1:
				now = time()
				timediff = int(now - timer)
				timediff_of(name, round_n, timediff)
	printer(tolist(round_db(round_n).find({'name':name})))
	return redirect('/adjs/')

@app.route('/admin/')
@app.route('/admin/home/')
def admin_callback():
	return render_template('admin.html', PROJECT_NAME=CODENAME, round_n=1)

@app.route('/admin/config/', methods=['GET'])
def admin_config_callback():
	data = db.config.find_one()
	return render_template('admin_config.html', PROJECT_NAME=CODENAME, data=data)

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

@app.route('/admin/data-importer/<int:n>', methods=['POST'])
def admin_proceed_round_callback(n):
	round_n = config_round_n()
	files = request.files
	if files['teams_data'] and files['draw_data']:
		data = DataImporter(files['teams_data'])
		teams = [{'name':team.team_name, 'member':[member.name for member in team.team_member.values()]} for team in data.teams]
		if data.teams:
			db.teams.remove()
			db.teams.insert(teams)
			
			config_round_n(n)
			return redirect('/admin/')
	return redirect('/admin/#dialog')

if __name__ == '__main__':
	app.run(debug=True)
