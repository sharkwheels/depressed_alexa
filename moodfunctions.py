###################
# mood builder 1.0 for depressed alexa
# January  2019
# Nadine Lessio
#################

from __future__ import print_function

import datetime
import itertools 
import json
import logging
import os
import random
import re
import requests
import time
import urllib.request

from collections import Counter
from collections import defaultdict
from collections import OrderedDict
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from random import randint, choice

###### Helper Functions for making Stress / PS / Mood etc ################################

def getWeather():
	""" Get the current weather from weather underground and return it in a list."""
	f = urllib.request.urlopen('http://api.wunderground.com/api/054a6723c3f6af43/geolookup/conditions/q/CWZG.json')
	json_string = f.read().decode('utf-8')
	parsed_json = json.loads(json_string)

	location = parsed_json['location']['city'].lower()
	temp_c = parsed_json['current_observation']['temp_c']
	weather = parsed_json['current_observation']['weather'].lower()
	humidity = parsed_json['current_observation']['relative_humidity'].lower()
	feels_like = parsed_json['current_observation']['feelslike_c']
	weather_list = [location, temp_c, weather, humidity,feels_like]
	f.close()
	return weather_list

def getArticles():
	""" Scrapes a bunch of news articles from a news API source."""
	#url = ('https://newsapi.org/v2/top-headlines?sources=cnn&apiKey=4bf91627cb324746b765ef1068a861e8')
	url = ('https://newsapi.org/v2/top-headlines?'
		'country=us&'
		'apiKey=4bf91627cb324746b765ef1068a861e8')
	data = requests.get(url)
	json_object = data.json()
	articles = json_object['articles']
	#print(json_object['articles'][2]['title'])
	a = []
	for i in articles:
		t = i['title'].split(" |", 1)[0]
		a.append(t.lower())  ## <-- skeeeeeetchy, but fuck it. I hate regex so... ;) 
	#print(a)
	return a


def searchArticles():
	""" Searches articles for specific keywords around things that will stress me the fuck out. """
	news_keywords = ['trump','mueller','russia','wall','repbulicans','putin','border']
	article_list = getArticles()	
	a = []
	for x in set(news_keywords):
		a.append([x, sum([article_list[i].count(x) for i in range(len(article_list))])])
	#print(a)
	return a

def getEvents():
	"""Grabs my current calendar events for the next two days for the busy score. """
	SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
	store = file.Storage('token_cal.json')
	creds = store.get()
	if not creds or creds.invalid:
		flow = client.flow_from_clientsecrets('credentials_cal.json', SCOPES)
		creds = tools.run_flow(flow, store)
	service = build('calendar', 'v3', http=creds.authorize(Http()))

	# Call the Calendar API
	days = 2
	now = datetime.datetime.now().isoformat() + 'Z' # 'Z' indicates UTC time
	t = datetime.datetime.now() + datetime.timedelta(days=days)
	then = t.isoformat() + 'Z'

	#print('Getting events for the next {0} days'.format(days))
	
	events_result = service.events().list(calendarId='primary', timeMin=now,
										timeMax=then, singleEvents=True,
										orderBy='startTime').execute()
	events = events_result.get('items', [])
	if not events:
		print('No upcoming events found.')
		return 0
	else:
		e = len(events)
		#for event in events:
		#    start = event['start'].get('dateTime', event['start'].get('date'))
		#    print(start, event['summary'])
		return e



def getEmails():
	""" Grabs my current unread email messages to make the busy score."""
	# If modifying these scopes, delete the file token.json.
	SCOPES = 'https://www.googleapis.com/auth/gmail.readonly'
	store = file.Storage('token_gmail.json')
	creds = store.get()
	if not creds or creds.invalid:
		flow = client.flow_from_clientsecrets('credentials_gmail.json', SCOPES)
		creds = tools.run_flow(flow, store)
	service = build('gmail', 'v1', http=creds.authorize(Http()))
	results = service.users().labels().get(userId='me',id='UNREAD').execute() ## <--JFC why is that NOWHERE in the docs that the ID is just id?????
	#print(results)
	u = results['messagesUnread']
	print("unread msgs: ",u)
	if not u:
		print("no unread messages")
		return 0
	else:
		print("returning unread messages")
		return u


def makeBusy():
	"""This combines messages and events into just an int, to give you
	a basic count of things that need your attention
	"""
	messages = getEmails()
	events = getEvents()
	#print(messages,events)
	if messages and events:
		busy_score = int(messages + events)
		return busy_score
	else:
		return messages


### MAKE AND MANAGE STRESS ##############################

def makeBaseStress():
	""" The lower your stress the better it is """

	random.seed()
	baseStress = random.randint(1,9) 
	print("starting stress: {}".format(baseStress))

	## make sum/count variables for news
	ns = 0

	## grab your data
	news_results = searchArticles()
	weather_results = getWeather()
	busy_results = makeBusy()
	#print("news: {}, weather {}, busy {}".format(news_results,weather_results,busy_results))

	## filter and count the news articles. 
	for i in news_results:
		ns += i[1]
	
	print("number of articles w/ shit keywords: {}".format(ns))

	if ns <=2:
		baseStress -=2
	if ns >2 and ns <=3:
		baseStress -=1
	elif ns >3 and ns <= 6:
		baseStress +=1
	elif ns >6 and ns <= 8:
		baseStress +=2
	elif ns >8:
		baseStress +=3
	
	print("stress after news: {}".format(baseStress))

	## parse the weather data you need
	temp = weather_results[1]
	conditions = weather_results[2]
	feelslike = weather_results[4]

	uppers = ["mostly sunny","clear","sunny","bright","calm","overcast","cloudy","mostly cloudy","partly cloudy"]
	downers = ["freezing rain","sleet","squals","ice pellets","rain","snow"]

	if any(w in conditions for w in uppers):
		baseStress -= 1
	elif any(w in conditions for w in downers):
		baseStress += 1
	else:
		pass

	print("stress after weather: {}".format(baseStress))

	if temp < -20:
		baseStress +=2 
	elif temp > -20 and temp <= 0:
		baseStress += 1
	elif temp > 0 and temp < 24:
		baseStress -= 2
	elif temp > 24 and temp < 30:
		baseStress += 1 
	elif c_temp > 30:
		baseStress += 2

	print("stress after temp: {}".format(baseStress))

	if busy_results > 10:
		baseStress += 1
	elif busy_results < 10:
		baseStress -= 1
	
	print("stress after busy: {}".format(baseStress))

	## keep baseStress between 0 and 10
	if baseStress >= 10:
		baseStress = 10
	elif baseStress <= 0:
		baseStress = 0

	print("stress final: {}".format(baseStress))
	return baseStress


def makePhysicalState(baseStress):
	""" the higher your physical state the better it its"""
	
	print("!makePS base stress: {}".format(baseStress)) ## stress level should affect the outcome of physical state in this regard. 

	random.seed()
	basePS = random.randint(4,6) ## a little wiggle room but nothing massive
	print("starting PS: {}".format(basePS))

	illness = random.randint(1,10)
	sleep = random.randint(1,10)

	print("illness: {0}, sleep: {1}".format(illness,sleep))

	if illness <= 3:
		basePS += 2 
	elif illness > 2 and illness <=5:
		basePS +=1
	elif illness >5 and illness <= 8:
		basePS -= 1
	elif illness > 8:
		basePS -=2

	print("PS after illness: {}".format(basePS))

	if sleep < 7:
		basePS -= 2
	elif sleep > 7:
		basePS += 2

	print("PS after sleep: {}".format(basePS))

	if baseStress <= 3:
		basePS += 2
	elif baseStress >3 and baseStress <= 7:
		basePS -= 1
	elif baseStress >7:
		basePS -= 2
	
	if basePS >= 10:
		basePS = 10
	elif basePS <= 1:
		basePS = 1

	print("PS after stress overall: {}".format(basePS))
	return basePS


def makeMood(baseStress,basePS):
	""" Figure out a base mood from a neutral starting mood of 5."""
	print("!makeMood baseStress:{} basePS:{}".format(baseStress,basePS))
	baseMood = 5 #random.randint(4,6) ## your mood always starts off as neutral. 

	print("starting mood: {}".format(baseMood))

	### calculate mood after stress lower stress = better

	if baseStress <= 3:
		baseMood += 2
	elif baseStress >3 and baseStress <= 5:
		baseMood += 1
	elif baseStress > 5 and baseStress <= 7:
		baseMood -=1
	elif baseStress > 7:
		baseMood -=2

	print("mood after stress: {}".format(baseMood))

	## calculate mood after physical state higher PS = better

	if basePS <=3:
		baseMood -=2
	elif basePS >3 and basePS <=5:
		baseMood -=1
	elif basePS > 5 and basePS <=8:
		baseMood +=1
	elif basePS > 8:
		baseMood +=2

	print("mood after ps: {}".format(baseMood))

	return baseMood


def makePerception(baseStress, basePS, baseMood):
	""" Perception is based on stress/physical/ mood. 
	This function also assigns a human readable. ie: good / bad / low etc 
	to the number values. Then wraps everythign up into a dict to send along to spoons. 
	"""

	### https://stackoverflow.com/questions/4527454/python-dictionary-contains-list-as-value-how-to-update
	print("!makePerception {} {} {}".format(baseStress,basePS,baseMood))
	perception = {'stress':[],'physical':[],'mood':[],'perception':'' }
	## where you can put the stresss high / low etc. 
	if baseStress < 1:
		stress = "great"
	elif baseStress == 1 or baseStress == 2:
		stress = "good"
	elif baseStress == 3 or baseStress == 4:
		stress = "ok"
	elif baseStress == 5 or baseStress == 6:
		stress = "low"
	elif baseStress == 7 or baseStress == 8:
		stress = "bad"
	elif baseStress > 8 and baseStress <=10:
		stress = "terrible"
	else:
		stress = "neutral"

	s = [baseStress,stress]
	for i in s:
		perception['stress'].append(i)
	

	if basePS < 1:
		ps = "terrible"
	elif basePS == 1 or basePS == 2:
		ps = "bad"
	elif basePS == 3 or basePS == 4:
		ps = "low"
	elif basePS == 5 or basePS == 6:
		ps = "ok"
	elif basePS == 7 or basePS == 8:
		ps = "good"
	elif basePS > 8 and basePS <=10:
		ps = "great"
	else:
		ps = "neutral"

	p = [basePS,ps]
	for i in p:
		perception['physical'].append(i)
	
	if baseMood < 1:
		mood = "terrible"
	elif baseMood == 1 or baseMood == 2:
		mood = "bad"
	elif baseMood == 3 or baseMood == 4:
		mood = "low"
	elif baseMood == 5 or baseMood == 6:
		mood = "ok"
	elif baseMood == 7 or baseMood == 8:
		mood = "good"
	elif baseMood == 9 or baseMood == 10:
		mood = "great"
	else:
		mood = "neutral"

	m = [baseMood,mood]
	for i in m:
		perception['mood'].append(i)

	## if majority of words in perception matches good / great / ok ...then overall perception is more positiive 
	## else if majority of words in perception are low / bad / very bad ....then overall perception is more negative.
	### dict {stress: ['low',1], physical : ['ok', 3], mood ['good',5], perception: 'more positive'}

	workingP = [stress,ps,mood]
	print(workingP)
	keywords = ['terrible','bad','low','good','great','ok']

	found = False
	f = ''
	## do a group iteration on the list of 3 from workingP, find if there are at least 2 of the same word. eg: 'good' 'good'
	## if so, make f that word. 
	## if not...do more comprehension
	for key, grp in itertools.groupby(workingP):
		#print('{}: {}'.format(key, list(grp)))
		k = key,len(list(grp))
		num = k[1]
		if num >=2:
			#print(k[0])
			f = k[0]
			found = True

	print("f: ",f)
	print(found)

	## if you found at least two of the terms, do this, otherwise check if at least two pos or neg terms exist in list.
	if found:
		if f == "low" or f == "bad" or f == "terrible":
			perception['perception'] = "negative"
		elif f == "ok":
			perception['perception'] = "neutral"
		elif f == "good" or f == "great":
			perception['perception'] = "positive"
	else:
		if 'great' in workingP and 'good' in workingP:
			perception['perception'] ="positive"
		elif 'bad' in workingP and 'terrible' in workingP:
			perception['perception'] = "negative"
		else:
			perception['perception'] = "neutral"

	print(perception)
	return perception

	
	
def makeSpoons(perception):
	
	## https://dev-notes.eu/2017/09/iterating-over-dictionary-in-python/
	
	print("!makeSpoons",perception)

	ps = perception['physical'][0]
	m = perception['mood'][0]
	mn = perception['mood'][1]
	st = perception['stress'][1]
	stn = perception['stress'][0]
	p = perception['perception']

	toAvg=[m,ps]
	print(toAvg)

	su = sum(toAvg)										## get the sum of mood + physical
	print("sum of mood + physical: ", su)
	spoons = (su/len(toAvg))*10							### get an average of mood and physical (this is the start of spoons)
	print("start of spoons: ", spoons)			

	
	## augment spoons based on stress value (I dunno it just makes sense ATM...oh right! stress goes opposite, so adding it didn't work. whatever.)
	## stress value augment of 5 percent
	## perception value augment of 5 percent

	stressAug = spoons*0.05
	print("stress aug: ", stressAug)
	if st == "good" or st == "great":
		spoons = spoons + stressAug
	elif st == "bad" or st == "low" or st == "terrible":
		spoons = spoons - stressAug

	print("spoons after stress: ", spoons)
	

	"""
	## augment spoons based on mood value (combo of ps and st)
	moodAug = spoons*0.05
	print("mood aug: ", moodAug)
	if mn == "good" or mn == "great":
		spoons = spoons + moodAug
	elif mn == "bad" or mn == "low" or mn == "terrible":
		spoons = spoons - moodAug

	print("spoons after mood aug: ", spoons)
	"""
	## next augment the new value of spoons based on your overall perception. I should call this outlook. 
	## negative down, positive up, neutral, nothing. 

	percepAug = spoons*0.05
	print(percepAug)

	if p == "positive":
		spoons = spoons + percepAug
	elif p == "negative":
		spoons = spoons - percepAug
	else:
		pass

	print("spoons after percep: ", spoons)
	## round up the spoons and call it a day. 

	spoons = round(spoons)
	print("spoonFinal: ", spoons)

	if spoons > 100:
		spoons = 100
	elif spoons < 0:
		spoons = 0

	print(spoons)
	theDay = perception
	print("theDay: ", theDay)
	theDay['spoons'] = spoons
	print("toReturn: ", theDay)
	return theDay

def makeTheDay():
	""" Makes The whole day. """
	baseStress = makeBaseStress()
	basePS = makePhysicalState(baseStress)
	baseMood = makeMood(baseStress,basePS)
	perception = makePerception(baseStress, basePS, baseMood)
	theDay = makeSpoons(perception)

	print("---------------------")
	print(" ")
	print("base stress level for the day: {}".format(baseStress))
	print("base Physical State for the day: {}".format(basePS))
	print("base mood for day: {}".format(baseMood))
	print("perception dict: {}".format(perception))
	#print("spoons: {}".format(spoons))
	print(" ")
	print("---------------------")
	return theDay
