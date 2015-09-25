import json
import csv

FILENAME = "r3.json"

def read_teams(filename):
	f = open(filename, 'r')
	reader = csv.reader(f)
	header = next(reader)
	Teams = []
	for team_id, row in enumerate(reader):
		if row[0] != '':
			Teams.append([row[0], row[1], row[2], row[3], row[4:], team_id])#=>team_name, institution, member1, member2
	return Teams

def read_matchups(filename):
	govopp = []
	f = open(filename, 'r')
	reader = csv.reader(f)
	header = next(reader)
	for team_id, row in enumerate(reader):
		if row[0] != '':
			govopp.append([row[0], row[1]])#=>team_name, institution, member1, member2
	return govopp

with open(FILENAME, "r") as f:
	a = json.load(f)

	data = []
	for item in a:
		if item['side'] == 'gov':
			data.append([item['name'], item['pm']['name'], item['pm']['score'], item['mg']['name'], item['mg']['score'], item['gr']['name'], item['gr']['score'], item['win'], item['side']])
		elif item['side'] == 'opp':
			data.append([item['name'], item['lo']['name'], item['lo']['score'], item['mo']['name'], item['mo']['score'], item['or']['name'], item['or']['score'], item['win'], item['side']])

for d in data:
	for a in d:
		print a

teams = read_teams("teams2015.csv")
match = read_matchups("matchups_for_round_3.csv")
necessary = []

##team_name, name, r01st, r02nd, r0rep, win?, opponent, gov?

with open("results/results3.csv", "w") as g:
	rrrr = []
	writer = csv.writer(g)
	writer.writerow([])
	for row in data:
		rrr = []
		win = 1 if row[7] else 0
		side = 1 if row[8] == "gov" else 0
		opponent = None
		for mat in match:
			if mat[0] == row[0]:
				opponent =  mat[1]
				break
			elif mat[1] == row[1]:
				opponent =  mat[0]
				break
			elif mat[1] == row[0]:
				opponent =  mat[0]
				break
			elif mat[1] == row[0]:
				opponent =  mat[1]
				break
		writer.writerow([row[0], row[1], row[2], "0", row[6], win, opponent, side])
		writer.writerow([row[0], row[3], "0", row[4], "0", win, opponent, side])





