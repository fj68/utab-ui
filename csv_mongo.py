#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import locale
locale.setlocale(locale.LC_ALL, '')

import csv, rym
from itertools import chain
from werkzeug.datastructures import FileStorage

# utility
def printer(a):
	print a
	return a

def file_open(filename, method='r', fun=lambda f: None):
	_ = None
	with open(filename, method) as f:
		_ = fun(f)
	return _

def flatten(l):
	return list(chain.from_iterable(l))

# interface

class CSVDataImporter(object):
	def __init__(self, file_teams=None, file_venues=None, file_adjudicators=None):
		self.teams = None
		self.venues = None
		self.adjudicators = None
		self.debaters = None
		
		if file_teams:
			self.read_teams(file_teams)
			self.read_debaters()
		if file_venues:
			self.read_venues(file_venues)
		if file_adjudicators:
			self.read_adjudicators(file_adjudicators)
		if self.teams and self.venues and self.adjudicators:
			self.validate()
	def read_teams(self, f):
		self.teams = self.__read_helper(f, rym.read_teams)
		if self.teams:
			rym.check_teams(self.teams)
			self.read_debaters()
		return self.teams
	def read_debaters(self):
		if self.teams:
			self.debaters = flatten([team.team_member for team in self.teams])
		return self.debaters
	def read_venues(self, f):
		self.venues = self.__read_helper(f, rym.read_venues)
		return self.venues
	def read_adjudicators(self, f):
		self.adjudicators = self.__read_helper(f, rym.read_adjudicators)
		if self.adjudicators:
			rym.check_adjudicators(self.adjudicators)
		return self.adjudicators
	def validate(self):
		if len(self.venues) < len(self.teams)/2:
			raise rym.ValidationError("too few rooms")
		if len(self.teams)/2 > len(self.adjudicators):
			raise rym.ValidationError("too few adjudicators")
	def __read_helper(self, f, fun):
		if isinstance(f, str):
			return file_open(f, 'r', fun)
		elif isinstance(f, (file, FileStorage)):
			return fun(f)
	def __str__(self):
		teams = len(self.teams) if self.teams else None
		debaters = len(self.debaters) if self.debaters else None
		venues = len(self.venues) if self.venues else None
		adjudicators = len(self.adjudicators) if self.adjudicators else None
		return '<CSVDataImporter: teams={0}, debaters={1}, venues={2}, adjudicators={3}>'.format(teams, debaters, venues, adjudicators)
	def __repr__(self):
		return self.__str__()

if __name__ == '__main__':
	FILENAME_TEAMS = "debater2014.csv"
	#FILENAME_TEAMS = "Teams.csv"
	FILENAME_VENUES = "venue2014.csv"
	FILENAME_ADJUDICATORS = "Adjudicators.csv"
	
	print CSVDataImporter(FILENAME_TEAMS, FILENAME_VENUES, FILENAME_ADJUDICATORS)

