import random
from random import choice

def makeGoal(mood,perception,spoons):
	""" Beleifs are the state of the world. These can be combined w/ stress, physical etc. later in intentions"""
	## mood and perception
	## might have to adjust this again.
	belief = {'self': '', 'world': ''}
	m = mood[1]
	p = perception

	if m == 'terrible' or m == 'bad' or m == 'low':
		belief['world'] = 'garbage'
	elif m == 'ok' or m =='neutral':
		belief['world'] = 'boring'
	elif m == 'good' or m == 'great':
		belief['world'] = 'fine'

	if p == 'positive':
		belief['self'] = 'adequate'
	elif p == 'negative':
		belief['self'] = 'useless'
	else:
		belief['self'] = 'incompetent'

	print('!makeGoal', belief)
	self = belief['self']
	world = belief['world']
	goal = ""

	## the world is garbage and I am useless. 
	## the world is boring and I am incompetent
	## the world is fine and I am adequate
	if world == "garbage" and self == "useless" and spoons <=20:
		## rude, self-gratification, anti-socialness, spiral
		goal = 'self-destruct'
	else:
		goal = 'stall'
	return goal
