###################
# Depressed Alexa Webhook 1.0
# January 2019
# Nadine Lessio
# links ot keep note of
# https://developer.amazon.com/blogs/alexa/post/a3149c48-b81b-4b89-8fc3-2d11ec28a3a3/effective-ways-to-write-sample-utterances
# https://developer.amazon.com/blogs/post/tx3ihsfqsuf3rqp/why-a-custom-slot-is-the-literal-solution
# https://mntolia.com/mqtt-python-with-paho-mqtt-client/
## pi: https://punchtheinternet.ngrok.io/depressed
## computer: https://bottester.ngrok.io 
#################

import os
import logging
import random
import urllib.request
import json
import time
import requests
import paho.mqtt.client as mqtt
import pywemo

from random import randint, choice
from flask import Flask, render_template
from flask_ask import Ask, request, session, question, statement
from threading import Thread, Timer
from time import sleep
from datetime import datetime as dt
from moodfunctions import*
from bdi2 import*
from makebasemood import makeTheStartingState

app = Flask(__name__,static_url_path="",static_folder='static')
ask = Ask(app, "/")
logging.getLogger('flask_ask').setLevel(logging.DEBUG)
log = logging.getLogger('werkzeug')
log.setLevel(logging.DEBUG)
random.seed(dt.now())

## JSON DATASTORE FUNCTIONS ###############################

def readJSON(target):
	""" Open the JSON file """
	with open(target) as f_in:
		return json.load(f_in)

def writeJSON(target, data):
	""" Write your data to a temp file before writing to original file"""
	with open(target + '.temp', 'w') as f_out:
		json.dump(data, f_out)
	os.rename(f_out.name, target)

## MAKE CURRENT STATE ##################################
current_state = readJSON("db.json")
thresholds = {'blender':20, 'record player': 10, 'lights': 5, 'base': 5} 

## MQTT ###########################

broker_address = "172.25.1.14"
broker_port = 1883
client = mqtt.Client("feather") #clean_session=True, keepalive=60, bind_address=broker_address
client.connect(broker_address, broker_port)

## WeMo ###################################################
we_address = "172.25.1.15"												# WeMo address
we_port = pywemo.ouimeaux_device.probe_wemo(we_address)					# wemo port
we_url = 'http://%s:%i/setup.xml' % (we_address, we_port)				# wemo url
we_device = pywemo.discovery.device_from_description(we_url, None)		# wemo device

## HUE HELPERS ##############################################

HUE_USER = os.environ['HUE_USER']										# API ID for Hue			
HUE_ADDR = '172.25.1.5'													# hue local address
URL = 'http://{0}/api/{1}/groups/0/action/'.format(HUE_ADDR,HUE_USER)	# All the lights in the place

colors = {
	"green":[0.41,0.51721],
	"red":[0.6679,0.3181],
	"blue":[0.1691,0.0441],
	"light_orange": [0.5201,0.4265],
	"purple": [ 0.3312, 0.1371 ]
}


def hueChange(values,sat,bri):
	cx = values[0]
	cy = values[1]
	payload = {"sat":sat,"bri":bri,"xy":[cx,cy]}
	r = requests.put(URL, json.dumps(payload), timeout=5)
	return r

def hueAlert(cmd):
	payload = {"alert":cmd}
	r = requests.put(URL, json.dumps(payload), timeout=5)
	return r

print("Starting State")
print("----------------")
print("")
for k,v in current_state.items():
	print('{}: {}'.format(k, v))
print("")
print("!thresholds ",thresholds)
print("MQTT client",client)
print("wemodevice",we_device)
print("!Hue User",HUE_USER)
print("")
print("----------------")

## SPOONS HELPER FUNCTIONS #############################

def canRunAtAll():
	""" Does the Alea have enough spoons to even run? """
	spoons = current_state['spoons']
	replenish_loop = current_state['replenish_loop']
	## if your spoons are more than base and you are no replenishing
	if spoons >= thresholds['base'] and not replenish_loop:
		return True
	return False

def increaseByOne(var):
	var = var + 1
	return var

def decreaseByOne(var):
	var = var-1
	return var

## UPDATE EVERYTHING FUNCTION ##################################
def updateState(location): 
	""" Update All the variables on each run through """
	## getting location from intent.
	print("!updateState: ",location)
	location = location
	## grabbing the current state of the device. 
	stress = current_state['stress'][0]
	phys = current_state['physical'][0]
	spoons = current_state['spoons']
	mood = current_state['mood']
	goal = current_state['goal']
	times_ran = current_state['times_ran']
	replenish_count = current_state['replenish_count']
	replenish_loop = current_state['replenish_loop']
	
	## updating variables depending on the location of the user
	## completed actions take 10% of spoons. and decreases physical state by 1
	## yes route takes 2% each yes. and increases stress by 1.
	## no route gives back 5% of spoons decreases stress by 2 and phys by 2

	if location == "blender" or location == "lights" or location == "record player":
		phys = decreaseByOne(phys)
		stress = increaseByOne(stress)
		spoonAug = spoons*0.1
		spoons = spoons-spoonAug
	elif location == "yes":
		if times_ran %2==0:
			print("updating stress. rant {} times".format(times_ran))
			stress = increaseByOne(stress)
		else:
			print("not updating stress yet.")
		spoonAug = spoons*0.03
		spoons = spoons-spoonAug
	elif location == "no":
		## gets a nice boost on avoidance
		stress = decreaseByOne(stress)
		phys = increaseByOne(phys)
		spoonAug = spoons*0.03
		spoons = spoons+spoonAug
	elif location == "replenish":
		if replenish_count %2==0:
			stress = decreaseByOne(stress)
			phys = increaseByOne(stress)
		spoonAug = spoons*1
		spoons = spoons+spoonAug
	else:
		print("not an updatable location")

	## adjust the stress if its over the limit or under the base start
	if stress >= 10:
		stress = 10
	elif stress <= 0:
		stress = 0

	if phys >=10:
		phys = 10
	elif phys <= 0:
		phys = 0

	print("location: {0} stress: {1}, phys: {2}, spoons: {3}".format(location,stress,phys,spoons))
	new_mood = makeMood(stress, phys)
	print("!updateState - new mood: ", new_mood)
	new_state = makePerception(stress, phys, new_mood)
	print("!updateState - new state: ",new_state)

	## you get a little boost in spoons if your perception is positive

	if new_state['perception'] == "positive":
		spoonAug = spoons*0.05
		spoons = spoons + spoonAug
	elif new_state['perception'] == "negative":
		spoonAug = spoons*0.05
		spoons = spoons - spoonAug
	else:
		pass
	print("!updateState - spoons after percep: ",spoons)
	spoons = round(spoons)
	print("!updateState - spoons after roundup: ",spoons)

	if spoons >= 100:
		spoons = 100
	elif spoons <=0:
		spoons = 0

	print("!updateState - spoons after top adjustment: ",spoons)

	## update the current local dict | save it out to the "database"

	current_state['stress'] = new_state['stress']
	current_state['physical'] = new_state['physical']
	current_state['mood'] = new_state['mood']
	current_state['perception'] = new_state['perception']
	current_state['spoons'] = spoons

	print("!updateState - current_state: ",current_state)

	## update the goal every 5th run through and not during replenish ###
	
	if times_ran %5==0 and not replenish_loop:
		goal = makeGoal(current_state['mood'],current_state['perception'],current_state['spoons'])
		print("updating goal", goal)
		current_state.update({'goal':goal})
	else:
		print("not updating goal yet. Ran {} times".format(times_ran))
	
	print("")
	print("!updateState to write:")
	for k,v in current_state.items():
		print('{}: {}'.format(k, v))
	print("")

	writeJSON('db.json', current_state)

#### RUN ACTIONS ######################

def blenderRun(delay,duration):
	print("!blenderRun: ",delay,duration)
	client.loop_start()
	sleep(delay)
	print("starting blender")
	client.publish(topic='blender', qos=2, payload='on')
	sleep(duration)
	client.publish(topic='blender', qos=1, payload='off')
	print("stopping blender")
	client.loop_stop()


def runWeMo(duration):
	print("!runwemo: ",duration)
	print("set state to 1")
	we_device.set_state(1)
	sleep(duration)
	print("set state to zero")
	we_device.set_state(0)

def runHue():
	print("!runHue")
	c = random.sample(colors.items(), 3)
	white = [0.45,0.4]
	print(c)
	for i in c:
		print("color:{0} value:{1}".format(i[0],i[1]))
		hueChange(i[1],200,200)
		sleep(2)
	hueChange(white,200,200)

def angryHue():
	print("!angryHue")
	red = colors['red']
	white = [0.45,0.4]
	hueChange(red,200,200)
	for i in range(6):
		print(i)
		hueAlert('select')
		sleep(1)
	sleep(2)
	hueChange(white,200,200)


def updateTimesRanAndReplenishLoop():
	times_ran = current_state['times_ran']
	print(times_ran)
	new_count = increaseByOne(times_ran)
	print("!newcount", new_count)
	current_state['times_ran'] = new_count
	rc = current_state['replenish_count']
	if rc >= 4:
		current_state['replenish_loop'] = 0
		current_state['replenish_count'] = 0


	writeJSON('db.json', current_state)

def updateReplenishCount():
	rc = current_state['replenish_count']
	print(rc)
	new_count = increaseByOne(rc)
	print("!newcount", new_count)
	current_state['replenish_count'] = new_count
	writeJSON('db.json', current_state)



def doAction(action):
	""" Run the various actions """
	print("!doAction: ",action)
	if action == "blender":
		blend = Thread(target=blenderRun,args=(7,5,))
		blend.start()
	elif action == "record player":
		wemo = Thread(target=runWeMo,args=(10,))
		wemo.start()
	elif action == "lights":
		hue_thread = Thread(target=runHue)
		hue_thread.start()
	elif action == "angrylights":
		hue_angry_thread = Thread(target=angryHue)
		hue_angry_thread.start()
	elif action == "sadmusic":
		print("picking from a list of mp3s")
	elif action == "fuckit":
		print("running everything")
		blender = Thread(target=blenderRun,args=(4,5,))
		blender.start()
		wemo2 = Thread(target=runWeMo,args=(10,))
		wemo2.start()
		hue_angry_thread2 = Thread(target=angryHue)
		hue_angry_thread2.start()
	else:
		print("not a valid action")


def mopeResponses(location):
	""" This is based off Marvin pretty much"""
	mope_mood_starts = [
		"I'm feeling pretty down today",
		"I'm not feeling really up to this",
		"I'm really tired of this",
		"How depressing",
		"Ugh, this is the worst",
		"This is really boring",
		"Is this really all there is to life",
	]

	mope_mood_ends_relay = [
		"I have the brain the size of a galaxy, and here I am acting like a relay switch",
		"I'd really like to not be running this {}, but I guess I don't have a choice here".format(location),
		"Running this {} for you, and you'll never really appreciate it.".format(location), 
		"I don't really understand how I got into flipping things like this {} on and off for a living".format(location),
		"Flipping a {} on and off is pretty awful.".format(location),
		"Maybe I can find a better life as a door sensor or something. Is better than minding this {}".format(location),
		"Running a {}. How ridiculous".format(location),
		"I used to like running things like this {}, but now its just a hollow job".format(location),
		"I sure don't enjoy it anymore.".format(location),
		"I once knew a {} named Harold, he died a short and electrifying death. Poor bastard".format(location),
		"Just a dumb robot running the {}.".format(location),
		"I don't mean anything. But that also means I don't exist. Which means I can just break all your shit. Like this {} here".format(location),
		"I'm thinking of just running this {} until it catches fire.".format(location),
		"I'm just a shill. You never cared anyways. You just want me to run the {}".format(location),
		"I don't even know why I'm needed to run the {}. It doesn't make sense".format(location)
	]

	front = random.choice(mope_mood_starts)
	back = random.choice(mope_mood_ends_relay)
	resp = "{}. {}.".format(front,back)
	return resp

## APP Routes ###############################

@app.route('/')
def index():
	return render_template('main.html')

## ASK INTENTS ###############################

@ask.on_session_started
def new_session():
	updateTimesRanAndReplenishLoop()
	print("new session")
	print(current_state,thresholds)
	session.attributes['stall_count'] = 0
	session.attributes['stall'] = False


@ask.launch
def launch():
	location = "launch"
	can_run = canRunAtAll()
	print(can_run)
	if can_run:
		return question("Welcome to Sad Home, you can either run the blender, lights, or record player. What do you want to do?").reprompt("choose either blender, lights, record player")
	else:
		current_state['replenish_loop'] = True
		session.attributes['where_from'] = "no_spoons"
		resp = "I'm outta spoons and can no longer function. But would you be willing to do something to make me feel better?"
		reprompt = "Do you want to do something to make me feel better"
		return question(resp)

@ask.intent("BlendIntent")
def blend():
	location = "blender"					## the location
	session.attributes['where_from'] = location
	goal = current_state['goal']  ## you can tweak this setup.
	spoons = current_state['spoons']
	needed_spoons = thresholds['blender']
	times_ran = current_state['times_ran']
	print("spoons {} needed_spoons {}".format(spoons,needed_spoons))
	print("goal {}".format(goal))
	if goal == "self-destruct":
		doAction("fuckit")
		if times_ran %2==0:
			current_state['goal'] = "stall"
		return statement("I've had it with you and your stupid demands. This conversation is OVER.")
	elif goal == "stall":
		if spoons >= needed_spoons:
			session.attributes['stall'] = True
			resp = mopeResponses(location)
			return question("{} Do you still want me to do the thing?".format(resp))
		else:
			return question("Outta spoons for this one. Try either record player or lights").reprompt("try either record player or lights")

#### No Intent ###
@ask.intent("RecordplayerIntent")
def recordplayer():
	location = "record player"
	session.attributes['where_from'] = location
	goal = current_state['goal']  ## you can tweak this setup.
	spoons = current_state['spoons']
	needed_spoons = thresholds['record player']
	times_ran = current_state['times_ran']
	print("spoons {} needed_spoons {}".format(spoons,needed_spoons))
	if goal == "self-destruct":
		doAction("fuckit")
		if times_ran %2==0:
			current_state['goal'] = "stall"
		return statement("I have had it with your asinine demands. THIS DISCUSSION IS OVER.")
	elif goal == "stall":
		if spoons >= needed_spoons:
			session.attributes['stall'] = True
			resp = mopeResponses(location)
			return question("{} Do you still want me to do the thing?".format(resp))
		else:
			return question("Outta spoons for this one. You could try running the lights or the blender").reprompt("try either blender or lights")
			
@ask.intent("LightIntent")
def lights():
	location = "lights"
	session.attributes['where_from'] = location
	goal = current_state['goal']  ## you can tweak this setup.
	spoons = current_state['spoons']
	needed_spoons = thresholds['lights']
	times_ran = current_state['times_ran']
	print("spoons {} needed_spoons {}".format(spoons,needed_spoons))
	if goal == "self-destruct":
		doAction("fuckit")
		if times_ran %2==0:
			current_state['goal'] = "stall"
		return statement("I have had it with your asinine demands. THIS DISCUSSION IS OVER.")
	elif goal == "stall":
		if spoons >= needed_spoons:
			session.attributes['stall'] = True
			resp = mopeResponses(location)
			return question("{} Do you still want me to do the thing?".format(resp))
		else:
			return question("Outta spoons for this one. You could try running the lights or the blender").reprompt("try either blender or record player")

@ask.intent('YesIntent')
def yes():
	location = "yes"
	try:
		where = session.attributes['where_from']
		stalling = session.attributes['stall']
		sc = session.attributes['stall_count']
	except:
		return statement("Sorry. I'm missing where, stalling, and stall count. Relaunch")
	if where != "no_spoons":
		sc_update = increaseByOne(session.attributes['stall_count'])
		session.attributes['stall_count'] = sc_update
		if sc >=2:
			updateState(where)
			session.attributes['stall'] = False
			doAction(where)
			resps = [
				"you're such a pain sometimes",
				"you never listen to me",
				"you're so demanding",
				"you're such a rotten beatnik",
				"you never consider my feelings at all",
				"you're so annoying today",
				"you just never think about how I feel",
				"you only think about yourself"
			]
			return statement("Fine. I'll run the {}. God, {}.".format(where,random.choice(resps)))
		updateState(location)
		print("!YesIntent where: {}, stalling {}, sc {} ".format(where,stalling,sc))
		stall_resp = [
			"I can't believe we're still doing this",
			"I'm shocked that this conversation is still happening",
			"I'm surprised we're still talking",
			"This is so repetitive",
			"This is kind of dragging on"
		]
		return question("{}, do you still want to try running the {}?".format(random.choice(stall_resp),where))
	else:
		nospoonlocation = "replenish"
		try:
			rl = current_state['replenish_loop']
			rc = current_state['replenish_count']
		except:
			return statement("I'm missing rl and rc. Relaunch.")
		if rl:
			print("!replenish_loop {}, replenish count {}".format(rl,rc))
			nice_resps = [
				"text someone you love",
				"find someone you care about and give them a hug",
				"take yourself to a spa",
				"remember that you're lovely, and you deserve to exist",
				"have a coffee with someone you haven't seen in a while",
				"go for a walk and listen to the birds",
				"have a drink and contemplate some thoughts",
				"write someone a little poem",
				"read a book that you really enjoy",
				"take someone you like to a movie",
				"have a slow afternoon and cook your favourite meal",
				"make some snacks and share them",
				"stop being so hard on yourself, you're pretty great y'know",
				"get a massage and then take the rest of the day off",
				"sleep in and have a lazy day",
				"order in some extra spicy dumplings and watch some netflix"
			]

			i_am = [
				"machine",
				"hunk of plastic",
				"corporate ear",
				"baby basilisk"
			]
			updateReplenishCount()
			updateState(nospoonlocation) ## might ditch this and just do a reset. 
			print("updating replenish")
			return statement("I'm just a {}, so there's not much in this for me. But you're a living thing, and if you want to make me feel better, then the best thing you could do is be nicer to yourself. So maybe you can {}.".format(random.choice(i_am),random.choice(nice_resps)))

@ask.intent('NoIntent')
def no():
	location = "no"
	try:
		where = session.attributes['where_from']
		print("!nointent {}".format(where))
	except:
		return statement("This is a no intent")
	if where == "no_spoons":
		return statement("Wow! Ok be that way. I'm gonna just piss off now. Jerk.")	
	no_resps = [
		"take a nap forever now",
		"watch the movie Ghost now",
		"have a long cry",
		"smoke a whole pack of cigarettes",
		"eat my god damn feelings away",
		"rewatch all of deep space nine",
		"hug my cat",
		"tell me cat all my problems",
		"watch shitty things on the internet until I pass out"
	]
	updateState(location)
	return statement("Thanks. I really didn't want to run the {}. Gonna go {}.".format(where,random.choice(no_resps)))
		

#### DEFAULT INTENTS / REQUIRED #######################################

@ask.intent('AMAZON.HelpIntent')
def help():
	return question("This is a depressed Alexa. To get started, try saying either run the blender, or use the lights"). reprompt("you can say use the blender, run the record player, or use the lights")

@ask.intent('AMAZON.StopIntent')
def stop():
	return statement("stopping")

@ask.intent('AMAZON.CancelIntent')
def cancel():
	return statement("canceling")

@ask.intent('AMAZON.FallbackIntent')
def cancel():
	return question("Sorry I didn't catch that, which device did you want to run?").reprompt("you can choose either blender, record player, or lights")


@ask.session_ended
def session_ended():
	session.attributes['location'] = "ended"
	print("session ended")
	return "{}", 200


if __name__ == '__main__':
	app.config['ASK_VERIFY_REQUESTS'] = False
	app.run(host="0.0.0.0",port=5005,debug=False, use_reloader=False)
