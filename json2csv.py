#!/usr/bin/env python
# -*- coding: utf-8 -*-

# useage: python2.7 json2csv.py < Results0.json > Results0.csv

import locale
locale.setlocale(locale.LC_ALL, '')

import sys, json, csv, cStringIO, math
from collections import Counter
from operator import add, itemgetter

# utilities

Error = Exception

def load_file(filename):
	with open(filename, 'r') as f:
		data = f.read()
	return data

def save_file(filename, data, append=False):
	with open(filename, 'a' if append else 'w') as f:
		f.write(data)

def csv_reader(f, fun, skip_header=True):
	reader = csv.reader(f)
	if skip_header: next(reader)
	return [fun(i, row) for i, row in enumerate(reader)]

def csv_writer(data, header=None, **kwargs):
	csv_file = cStringIO.StringIO()
	cw = csv.writer(csv_file, **kwargs)
	if header: cw.writerow(header)
	cw.writerows(data)
	return csv_file.getvalue()

def dict2list(data, fn, header=None):
	return [fn(it) for it in data]

# core

def translater(it):
	# validation
	for n in ['side', 'from', 'name', 'total', 'win', 'opponent']:
		if n not in it:
			raise Error('Invalid json format: required field \'{0}\' is not implemented{1}.'.format(n, ' ({0})'.format(it['name']) if 'name' in it else ''))
	
	if it['side'] == 'gov':
		# validation
		for n in ['pm', 'mg', 'gr']:
			if n not in it:
				raise Error('Invalid json format: required field \'{0}\' is not implemented ({1}).'.format(n, it['name']))
			else:
				for m in ['name', 'score']:
					if m not in it[n]:
						raise Error('Invalid json format: required field \'{0}\' is not implemented ({1}@{2}).'.format(m, n, it['name']))
		
		data = [it['from'], it['name'], it['pm']['name'], it['pm']['score'], it['mg']['name'], it['mg']['score'], it['gr']['name'], it['gr']['score'], it['total'], it['win'], it['opponent'], it['side']]
	else:
		# validation
		for n in ['lo', 'mo', 'or']:
			if n not in it:
				raise Error('Invalid json format: required field \'{0}\' is not implemented ({1}).'.format(n, it['name']))
			else:
				for m in ['name', 'score']:
					if m not in it[n]:
						raise Error('Invalid json format: required field \'{0}\' is not implemented ({1}@{2}).'.format(m, n, it['name']))
		
		data = [it['from'], it['name'], it['lo']['name'], it['lo']['score'], it['mo']['name'], it['mo']['score'], it['or']['name'], it['or']['score'], it['total'], it['win'], it['opponent'], it['side']]
	return data

def list_translater(src):
	# src: from, team name, 1st name, 1st score, 2nd name, 2nd score, 3rd name, 3rd score, total, win, opponent, side
	# tmp_data: team name, 1st name, 1st score, 2nd name, 2nd score, 3rd name, 3rd score, win, opponent, side
	# data: team name, name, 1st score, 2nd score, 3rd score, win, opponent, side
	
	def get_by(_from, _fn):
		return [it for it in _from if _fn(it)]
	
	team_list = [it[1] for it in src]
	nodup_team_list = list(set(team_list))
	tmp_data = []
	data = []
	
	for team_name in nodup_team_list:
		data_list = get_by(src, lambda it: it[1] == team_name)
		num_of_dup = len(data_list)
		if num_of_dup == 1:
			# from, totalを削除
			d = data_list[0][1:]
			d.pop(7)
			tmp_data.append(d)
		else:
			item = data_list[0]
			first_score = reduce(add, [it[3] for it in data_list]) / num_of_dup
			second_score = reduce(add, [it[5] for it in data_list]) / num_of_dup
			third_score = reduce(add, [it[7] for it in data_list]) / num_of_dup
			win = reduce(add, [1 if it[9] else 0 for it in data_list]) > math.ceil(num_of_dup / 2)
			tmp_data.append([item[1], item[2], first_score, item[4], second_score, item[6], third_score, win, item[10], item[11]])
	
	store = {}
	nodup_tmp_data = []
	for item in tmp_data:
		for i in xrange(3):
			speaker_name = item[1+i*2]
			if speaker_name not in store:
				# store: [team_name, win, opponent, side], 1st score, 2nd score, 3rd score
				store[speaker_name] = [[item[0], item[7], item[8], item[9]], 0, 0, 0]
				
			store[speaker_name][1+i] = item[2+i*2]
	for speaker_name, store_value in store.items():
		pt = store_value[1:]
		item = store_value[0]
		data.append([item[0], speaker_name, pt[0], pt[1], pt[2], 1 if item[1] else 0, item[2], 1 if item[3] == 'gov' else 0])
	data.sort(key=itemgetter(0, 1))
	
	return data

def json2list(src):
	dest = dict2list(src, translater)
	data = list_translater(dest)
	return data

if __name__ == '__main__':
	header = ['team name', 'name', '1st score', '2nd score', '3rd score', 'win', 'opponent', 'side']
	json_src = sys.stdin.read()
	src = json.loads(json_src)
	data = json2list(src)
	csv_data = csv_writer(data, header)
	sys.stdout.write(csv_data)

