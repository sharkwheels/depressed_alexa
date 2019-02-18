import json
from moodfunctions import*
from bdi2 import*


def makeTheStartingState():
	global json
	current_state = makeTheDay()
	print(current_state)
	goal = makeGoal(current_state['mood'],current_state['perception'],current_state['spoons'])
	print(goal)
	current_state.update({'goal':goal})

	## set some vars that I need to calulate other behaviours.
	current_state.update({'times_ran':0})
	current_state.update({'replenish_count':0})
	current_state.update({'replenish_loop':0})
	print(current_state)

	## dump this to a JSON string / acting as a rough database
	json = json.dumps(current_state)
	f = open("db.json","w")
	f.write(json)
	f.close()
	print("savedTo db.json")

if __name__ == "__main__":
    makeTheStartingState()