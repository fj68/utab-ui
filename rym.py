#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import locale
locale.setlocale(locale.LC_ALL, '')

import csv

# custom error & warning
class ValidationError(StandardError):pass
class FormatError(StandardError):pass

# data structures from tab_ver19.py

class Debater:
	def __init__(self, name):
		self.name = name
		self.scores = []
	def __str__(self):
		return self.name
	def __repr__(self):
		return "<rym.Debater: {0}>".format(self.__str__())

class Team:
	def __init__(self, team_name, member1, member2, institution_scale, institutions, team_id):
		self.team_name = team_name
		self.institutions = institutions
		self.team_member = {}
		self.team_id = team_id
		self.team_member[member1] = Debater(member1)
		self.team_member[member2] = Debater(member2)
		self.absent = False#absent?
		self.team_score = 0
		self.team_scores = []
		self.team_wins = []
		self.past_sides = []
		self.team_ranking = 0
		self.institution_scale = institution_scale
		self.past_opponents = []
		self.past_desirabilities = []
		self.side_rank = None
		self.unfairity = None
		self.side_priority = False
	def __str__(self):
		return self.team_name
	def __repr__(self):
		return "<rym.Team: {0}>".format(self.__str__())

class Venue:
	def __init__(self, name):
		self.name = name
		self.available = True
	def __str__(self):
		return self.name
	def __repr__(self):
		return "<rym.Venue: {0}>".format(self.__str__())

class Adjudicator:
	def __init__(self, name, reputation, judge_test, institutions, conflict_teams):
		self.name = name
		self.reputation = reputation
		self.judge_test = judge_test
		self.institutions = [institution for institution in institutions if institution != '']
		self.absent = False#absent?
		self.adj_score = 0
		self.adj_scores = []
		self.watched_debate_score = 0
		self.watched_debate_scores = []
		self.watched_debate_ranks = []
		self.watched_teams = []
		self.active_num = 0
		self.ranking = 0
		self.active = False
		self.evaluation = 0
		self.conflict_teams = [conflict_team for conflict_team in conflict_teams if conflict_team != '']
	def __str__(self):
		return self.name
	def __repr__(self):
		return "<rym.Adjudicator: {0}>".format(self.__str__())

# functions from tab_ver19.py (some has forked)

def read_adjudicators(f):
	return csv_reader(f, lambda _, row: Adjudicator(row[0], int(row[1]), int(row[2]), row[3:13], row[13:]))

def check_adjudicators(Adjudicators):
	adjudicators_names = [adjudicator.name for adjudicator in Adjudicators]
	for adjudicator_name in adjudicators_names:
		if adjudicators_names.count(adjudicator_name) > 1:
			raise ValidationError("same adjudicator appears : {0}".format(adjudicator_name))

def read_teams(f):
	return csv_reader(f, lambda i, row: Team(row[0], row[1], row[2], row[3], row[4:], i))

def check_teams(Teams):
	team_names = [team.team_name for team in Teams]
	for team_name in team_names:
		if team_names.count(team_name) > 1:
			raise ValidationError("same team appears :{0}".format(team_name))

	for team in Teams:
		if not(team.institution_scale == "large" or team.institution_scale == "small" or team.institution_scale == "middle"):
			raise FormatError("unknown team scale :{0}".format(team_name))

def read_venues(f):
	return csv_reader(f, lambda _, row: Venue(row[0]))

def read_results(f):
	return csv_reader(f, lambda _, row: [row[0], row[1], int(row[2]), int(row[3]), int(row[4]), int(row[5]), row[6], int(row[7])])

def csv_reader(f, fun):
	reader = csv.reader(f)
	next(reader)
	return [fun(i, row) for i, row in enumerate(reader)]
