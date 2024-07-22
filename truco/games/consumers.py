import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from games.models import Game, Player
from django.core import serializers
from games.gameHandler import GameHandler
import json
import random

group_count = {}

games = {}


class GameConsumer(WebsocketConsumer):
     
    # This Function will create a new player, place them on a team and then add them to the game state. Returns negative numbers on errors
    def createNewPlayer(self, game, username="AnonymousUser"):
        
        nameList = []
        for player in game.game_state["players"]:
            nameList = nameList + [player["username"]]

        # This condition is if the user is logged in, so we call pull their username from there
        if (str(self.user) != "AnonymousUser"):
            self.usernameSet = True
            self.username = str(self.user)
            self.player["username"] = self.username
        #This sees if a username parameter was supplied, if it wasnt then return WARNING: Bug when a user puts thier name as "AnonymousUser" add checks for that on serverside code
        elif (username == "AnonymousUser"):
            return -1
        #This is if a username parameter was supplied by the username input box on the client. Errors happen on certain conditions
        else:
            if (username == "" or username == "Player" or username in nameList):
                return -1
            self.usernameSet = True
            self.player["username"] = username
            

        #Call the sort teams method which will find a valid team to place the new player on, or potentially reject them if they are full.
        # returns what team too join, or -1 if the game is full
        teamToPlace = game.sortTeams()
        self.player["team"] = teamToPlace

        #Add player to the game state, and then send a socket to the player to identify themself
        #Then send a socket to everyone saying to add them to the list of players
        game.game_state["players"] += [self.player]
        print( game.game_state["players"])
        self.send(json.dumps({"code": "yourplayer", "player": self.player, "data": self.game.game_state}))
        async_to_sync(self.channel_layer.group_send)(
        self.game_group_name, {"type": "game.newplayer", "code": "newplayer", "player": self.player, "data": self.game.game_state}
        )
        return 1
        

    def connect(self):
        self.game_name = self.scope["url_route"]["kwargs"]["game_name"]
        self.game_group_name = f"game_{self.game_name}"
        self.user = self.scope["user"]
        self.username = ""
        self.usernameSet = False
        self.player = {
            "username":"Player",
            "isTurn": False,
            "hand": [],
            "team": 0
        }

        #Add game to the list of games or create new one if it doesn't exist and then set self.game to that game
        games[self.game_name] = games.get(self.game_name, GameHandler(self.game_name))
        self.game = games[self.game_name]
        
        #Accept the connection
        self.accept()

        #Join Group
        async_to_sync(self.channel_layer.group_add)(
            self.game_group_name, self.channel_name
        )
        
        # Accept the connection and add one to the socket count for this game
        self.send(json.dumps({"code": "start_state", "data": self.game.game_state}))
        self.createNewPlayer(self.game)
        group_count[self.game_group_name] = group_count.get(self.game_group_name, 0) + 1





    #Called when a socket disconnects
    #PUT CODE HERE TO HANDLE SOMEONE LEAVING DURING A GAME
    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.game_group_name, self.channel_name
        )
        #Remove one of the connected sockets, IN THE FUTURE put code for removing player from game
        group_count[self.game_group_name] = group_count[self.game_group_name] - 1
        
        #Find the player and remove them from the list
        playerIndex = self.game.findPlayer(self.player)
        if (playerIndex != -1):
            del self.game.game_state["players"][playerIndex]
        #This is here in case a player disconnects without typing in a name
        elif (self.player["username"] == "Player"):
            return

        else:
            print("MAJOR ISSUE")

        #This code will send out a message to all the other players saying that this guy disconnected
        async_to_sync(self.channel_layer.group_send)(
        self.game_group_name, {"type": "game.newplayer", "code": "playerleft", "player": self.player, "data": self.game.game_state}
        )


        #If there are no connected Sockets then delete the game
        if(group_count[self.game_group_name] == 0):
            deadGame = Game.objects.get(id=self.game_name)
            #This needs work that I will do later, currently causes the game to be deleted on a reload
            #deadGame.delete()
            #del group_count[self.game_name]
        




    # This is called when a message from a websocket is recieved from the server. This is where
    # Handling players moves and things like that should happen
    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        code = text_data_json["code"]
        currentState = self.game.game_state
        #This is where we will interpret the clients code that they sent and decide what to do with it.
        #For example, if it is "username" then we will set the persons username and make a player.
        #If it is "message" then we can further look into the message details, etc etc.
        if (code == "username"):
            #This is where we will create a player using the username, and potentially place them on a team/allow them to spectate.
            userCode = self.createNewPlayer(self.game, username=text_data_json["username"])
            if userCode < 0:
                self.send(json.dumps({"code": "error", "error": "invalidusername",  "data": self.game.game_state}))
        #This code will be called when a player sends the "start" command telling the server the player is ready to start the game
        elif (code == "start"):
            

            #In this if put all the conditions that could stop the game from starting 
            if len(currentState["players"]) < 4:
                async_to_sync(self.channel_layer.group_send)(
                self.game_group_name, {"type": "game.message", "code": "message", "data": "Conditions not met to start game"}
                )

            else:
                #This code prepares for the start of the game. First it sits the players every other
                #Then it shuffles the deck, and deals the cards
                #Then it makes the first player go first, and sets the game state to "roundstart"
                self.game.startGame()
                async_to_sync(self.channel_layer.group_send)(
                self.game_group_name, {"type": "game.sendState", "code": "start", "data": currentState}
             )
            
        
        elif (code == "swap"):
            index = self.game.findPlayer(text_data_json["player"])
            currentState["players"][index] = text_data_json["player"]
            async_to_sync(self.channel_layer.group_send)(
            self.game_group_name, {"type": "game.newplayer", "code": "swap", "player": text_data_json["player"], "data": currentState}
            )

        elif (code == "playCard"):
            curPlayer = text_data_json["player"]
            curCard = text_data_json["card"]
            playerLength = len(currentState["players"]) - 1
            playIndex = self.game.findPlayer(curPlayer)

            if (curCard in curPlayer["hand"] and curPlayer["isTurn"] and currentState["state"] == "inPlay"):
                currentState["board"]["cardsPlayed"] = currentState["board"]["cardsPlayed"] + [{"card":curCard, "player":curPlayer["username"]}]
                curPlayer["hand"].remove(curCard)
                curPlayer["isTurn"] = False
                currentState["players"][playIndex] = curPlayer
                if (playIndex == playerLength):
                    currentState["players"][0]["isTurn"] = True
                else:
                    currentState["players"][playIndex + 1]["isTurn"] = True
                if (len(currentState["board"]["cardsPlayed"]) == len(currentState["players"])):
                    print("made it here")
                    self.game.trickOver()

                async_to_sync(self.channel_layer.group_send)(
                self.game_group_name, {"type": "game.sendState", "code": "cardPlayed", "data": currentState}
                )
            else:
                self.send(json.dumps({"code": "error", "error": "invalidplay",  "data": self.game.game_state}))

        elif (code == "vote"):
            if (currentState["state"] != "truco"):
                self.send(json.dumps({"code": "error", "error": "notTruco",  "data": self.game.game_state}))
                return
            vote = text_data_json["vote"]
            curPlayer = text_data_json["player"]
            teamNum = curPlayer["team"]
            if (vote == "fold" and self.player["username"] not in self.game.trucoVote):
                self.game.trucoVote = self.game.trucoVote + [self.player["username"]]
            elif (vote == "play" and self.player["username"] not in self.game.trucoVote):
                handle = self.game.handleTruco("play")
                async_to_sync(self.channel_layer.group_send)(
                self.game_group_name, {"type": "game.sendState", "code": "trucoAccepted", "data": currentState}
                )
            elif (vote == "raise" and self.player["username"] not in self.game.trucoVote):
                curTeam = currentState["teams"][curPlayer["team"]]
                if (curTeam["calledTruco"] != False or currentState["board"]["pointsWorth"] >= 12 or currentState["board"]["at11"] == True):
                    self.send(json.dumps({"code": "error", "error": "invalidRaise",  "data": self.game.game_state}))
                    return
                self.game.trucoCalled(curPlayer)
                async_to_sync(self.channel_layer.group_send)(
                self.game_group_name, {"type": "game.truco", "code": "trucoCalled", "team":teamNum, "data": currentState}
                )

            if (len(self.game.trucoVote) == len(currentState["players"])/2):
                self.game.trucoVote = []
                teamWon = 0
                if (currentState["teams"][0]["calledTruco"] == True):
                    teamWon = currentState["teams"][0]
                else:
                    teamWon = currentState["teams"][1]
                self.game.roundOver(winner = teamWon)
                async_to_sync(self.channel_layer.group_send)(
                self.game_group_name, {"type": "game.sendState", "code": "trucoFolded", "data": currentState}
                )
            

        elif (code == "callTruco"):
            curPlayer = text_data_json["player"]
            curTeam = currentState["teams"][curPlayer["team"]]
            teamNum = curPlayer["team"]
            if (curPlayer["isTurn"] != True or curTeam["calledTruco"] != False or currentState["board"]["pointsWorth"] >= 12 or currentState["board"]["at11"] == True):
                self.send(json.dumps({"code": "error", "error": "invalidTruco",  "data": self.game.game_state}))
                return
            self.game.trucoCalled(curPlayer)
            async_to_sync(self.channel_layer.group_send)(
                self.game_group_name, {"type": "game.truco", "code": "trucoCalled", "team":teamNum, "data": currentState}
                )



        else:
            pass




    # This sends a message back to all the sockets connected
    #Should be used by the server to tell the sockets how it responds
    #To the socket that it recieved.
    def game_message(self, event):
        code = event["code"]
        message = event["message"]
        # Send message to WebSocket using the send method. Every socket in the group heard this event so it sends it to everyone, but send itself only sends to one client.
        self.send(text_data=json.dumps({"code": code, "data": message}))

    def game_error(self, event):
        code = event["code"]
        message = event["error"]
        # Send message to WebSocket using the send method. Every socket in the group heard this event so it sends it to everyone, but send itself only sends to one client.
        self.send(text_data=json.dumps({"code": code, "error": message}))


    def game_newplayer(self, event):
        code = event["code"]
        player = event["player"]
        data = event["data"]
        # Send message to WebSocket using the send method. Every socket in the group heard this event so it sends it to everyone, but send itself only sends to one client.
        self.send(text_data=json.dumps({"code": code, "player":player,"data":data}))

    def game_truco(self, event):
        code = event["code"]
        team = event["team"]
        data = event["data"]
        # Send message to WebSocket using the send method. Every socket in the group heard this event so it sends it to everyone, but send itself only sends to one client.
        self.send(text_data=json.dumps({"code": code, "team":team,"data":data}))

    def game_sendState(self, event):
        code = event["code"]
        data = event["data"]
        # Send message to WebSocket using the send method. Every socket in the group heard this event so it sends it to everyone, but send itself only sends to one client.
        self.send(text_data=json.dumps({"code": code, "data":data}))

    def game_play(self, event):
        code = event["code"]
        card = event["card"]
        data = event["data"]
        # Send message to WebSocket using the send method. Every socket in the group heard this event so it sends it to everyone, but send itself only sends to one client.
        self.send(text_data=json.dumps({"code": code, "card": card, "data":data}))
