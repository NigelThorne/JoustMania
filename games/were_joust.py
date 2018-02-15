import os
import random
import time
from math import sqrt
from multiprocessing import Process, Value, Array

import numpy
import psmove

import colors
import common
from piaudio import Audio

# How fast/slow the music can go
SLOW_MUSIC_SPEED = 0.7
#this was 0.5
FAST_MUSIC_SPEED = 1.5

# The min and max timeframe in seconds for
# the speed change to trigger, randomly selected
MIN_MUSIC_FAST_TIME = 4
MAX_MUSIC_FAST_TIME = 8
MIN_MUSIC_SLOW_TIME = 10
MAX_MUSIC_SLOW_TIME = 23

END_MIN_MUSIC_FAST_TIME = 6
END_MAX_MUSIC_FAST_TIME = 10
END_MIN_MUSIC_SLOW_TIME = 8
END_MAX_MUSIC_SLOW_TIME = 12

#Default Sensitivity of the contollers
#These are changed from the options in common
SLOW_MAX = 1
SLOW_WARNING = 0.28
FAST_MAX = 1.8
FAST_WARNING = 0.8

#Sensitivity of the werewolf contollers
WERE_SLOW_MAX = 1.4
WERE_SLOW_WARNING = 0.5
WERE_FAST_MAX = 2.3
WERE_FAST_WARNING = 1.2

#How long the speed change takes
INTERVAL_CHANGE = 1.5

#How long the winning moves shall sparkle
END_GAME_PAUSE = 6
KILL_GAME_PAUSE = 4


def track_move(move_serial, move_num, team, team_color_enum, dead_move, force_color, music_speed, werewolf_reveal, show_team_colors, red_on_kill):
    no_rumble = time.time() + 1
    move_last_value = None
    move = common.get_move(move_serial, move_num)
    my_team_colors = team_color_enum.value
    werewolf = False
    vibrate = False
    change_arr = [0,0,0]
    vibration_time = time.time() + 1
    flash_lights = True
    flash_lights_timer = 0
    if team < 0:
        werewolf = True

    #keep on looping while move is not dead
    while True:
        if show_team_colors.value == 1:
            move.set_leds(*my_team_colors)
            move.update_leds()
        elif sum(force_color) != 0:
            time.sleep(0.01)
            move.set_leds(*force_color)

            if sum(force_color) > 75:
                if werewolf:
                    move.set_rumble(80)
            else:
                if sum(force_color) == 30:
                    if werewolf:
                        move.set_leds(*colors.Colors.Blue40.value)
                    else:
                        move.set_leds(*colors.Colors.Black.value)
                move.set_rumble(0)
            move.update_leds()
            no_rumble = time.time() + 0.5
        elif dead_move.value == 1 and werewolf_reveal.value > 0:   
            if move.poll():
                ax, ay, az = move.get_accelerometer_frame(psmove.Frame_SecondHalf)
                total = sqrt(sum([ax**2, ay**2, az**2]))
                if move_last_value is not None:
                    change_real = abs(move_last_value - total)
                    change_arr[0] = change_arr[1]
                    change_arr[1] = change_arr[2]
                    change_arr[2] = change_real
                    change = (change_arr[0] + change_arr[1]+change_arr[2])/3
                    speed_percent = (music_speed.value - SLOW_MUSIC_SPEED)/(FAST_MUSIC_SPEED - SLOW_MUSIC_SPEED)
                    if werewolf:
                        warning = common.lerp(WERE_SLOW_WARNING, WERE_FAST_WARNING, speed_percent)
                        threshold = common.lerp(WERE_SLOW_MAX, WERE_FAST_MAX, speed_percent) 
                    else:
                        warning = common.lerp(SLOW_WARNING, FAST_WARNING, speed_percent)
                        threshold = common.lerp(SLOW_MAX, FAST_MAX, speed_percent)



                    if vibrate:
                        flash_lights_timer += 1
                        if flash_lights_timer > 7:
                            flash_lights_timer = 0
                            flash_lights = not flash_lights
                        if flash_lights:
                            move.set_leds(*colors.Colors.Black.value)
                        else:
                            if werewolf_reveal.value == 2 and werewolf:
                                move.set_leds(*colors.Colors.Blue40.value)
                            else:
                                move.set_leds(*colors.Colors.White40.value)
                        if time.time() < vibration_time - 0.22:
                            move.set_rumble(110)
                        else:
                            move.set_rumble(0)
                        if time.time() > vibration_time:
                            vibrate = False

                    else:
                        if werewolf_reveal.value == 2 and werewolf:
                            move.set_leds(*colors.Colors.Blue40.value)
                        else:
                            move.set_leds(*colors.Colors.White40.value)


                    if change > threshold:
                        if time.time() > no_rumble:
                            if red_on_kill:
                                move.set_leds(*colors.Colors.Red.value)
                            else:
                                move.set_leds(*colors.Colors.Black.value)
                            move.set_rumble(90)
                            dead_move.value = 0

                    elif change > warning and not vibrate:
                        if time.time() > no_rumble:
                            vibrate = True
                            vibration_time = time.time() + 0.5

                move_last_value = total
            move.update_leds()
        
        elif dead_move.value < 1:
            time.sleep(0.5)

class WereJoust():

    def __init__(self, moves, command_queue, ns, music, teams, game_mode):

        self.command_queue = command_queue
        self.ns = ns

        print(self.ns.settings)

        #save locally in case settings change from web
        self.play_audio = self.ns.settings['play_audio']
        self.sensitivity = self.ns.settings['sensitivity']
        self.color_lock = self.ns.settings['color_lock']
        self.color_lock_choices = self.ns.settings['color_lock_choices']
        self.random_teams = self.ns.settings['random_teams']
        self.red_on_kill = self.ns.settings['red_on_kill']

        self.move_serials = moves
        self.tracked_moves = {}
        self.dead_moves = {}
        self.music_speed = Value('d', SLOW_MUSIC_SPEED)
        self.running = True
        self.force_move_colors = {}
        self.teams = teams
        self.num_teams = len(colors.team_color_list)

        self.werewolf_timer = 35
        self.start_timer = time.time()
        self.audio_cue = 0
        self.num_dead = 0
        self.show_team_colors = Value('i', 0)
        
        self.non_stop_deaths = {}
        for move in self.move_serials:
            self.non_stop_deaths[move] = 0
        self.non_stop_time = time.time() + 150

        
        self.update_time = 0
        self.alive_moves = []

        print("speed is {}".format(self.sensitivity))
        global SLOW_MAX
        global SLOW_WARNING
        global FAST_MAX
        global FAST_WARNING

        SLOW_MAX = common.SLOW_MAX[self.sensitivity]
        SLOW_WARNING = common.SLOW_WARNING[self.sensitivity]
        FAST_MAX = common.FAST_MAX[self.sensitivity]
        FAST_WARNING = common.FAST_WARNING[self.sensitivity]

        print("SLOWMAX IS {}".format(SLOW_MAX))


        self.werewolf_reveal = Value('i', 2)

        self.werewolf_reveal.value = 0
        self.num_teams = 1

        print('HELLO THE NUMBER OF TEAMS IS %d' % self.num_teams)

        self.team_colors = colors.generate_team_colors(self.num_teams,self.color_lock,self.color_lock_choices)
        self.generate_random_teams(self.num_teams)


        were_num = int((len(moves)*7)/16)
        if were_num <= 0:
            were_num = 1
        self.choose_werewolf(were_num)

        if self.play_audio:
            self.start_beep = Audio('audio/Joust/sounds/start.wav')
            self.start_game = Audio('audio/Joust/sounds/start3.wav')
            self.explosion = Audio('audio/Joust/sounds/Explosion34.wav')
            self.revive = Audio('audio/Commander/sounds/revive.wav')
            self.audio = music

        self.speed_up = False
        self.currently_changing = False
        self.game_end = False
        self.winning_moves = []        
        


    def choose_werewolf(self, were_num):
        for were in range(were_num):
            werewolf = random.choice(self.move_serials)
            while self.teams[werewolf] < 0:
                werewolf = random.choice(self.move_serials)
            self.teams[werewolf] = (self.teams[werewolf] * -1) - 1

    def generate_random_teams(self, num_teams):
        if self.random_teams == False:
            players_per_team = (len(self.move_serials)//num_teams)+1
            team_num = [x for x in range(num_teams)]*players_per_team
            for num,move in zip(team_num,self.move_serials):
                self.teams[move] = num
        else:
            team_pick = list(range(num_teams))
            copy_serials = self.move_serials[:]

            while len(copy_serials) >= 1:
                serial = random.choice(copy_serials)
                copy_serials.remove(serial)
                random_choice = random.choice(team_pick)
                self.teams[serial] = random_choice
                team_pick.remove(random_choice)
                if not team_pick:
                    team_pick = list(range(num_teams))

    def track_moves(self):
        for move_num, move_serial in enumerate(self.move_serials):
            self.alive_moves.append(move_serial)
            time.sleep(0.1)
            dead_move = Value('i', 1)
            force_color = Array('i', [1] * 3)
            proc = Process(target=track_move, args=(move_serial,
                                                    move_num,
                                                    self.teams[move_serial],
                                                    self.team_colors[self.teams[move_serial]],
                                                    dead_move,
                                                    force_color,
                                                    self.music_speed,
                                                    self.werewolf_reveal,
                                                    self.show_team_colors,
                                                    self.red_on_kill))
            proc.start()
            self.tracked_moves[move_serial] = proc
            self.dead_moves[move_serial] = dead_move
            self.force_move_colors[move_serial] = force_color
            
    def change_all_move_colors(self, r, g, b):
        for color in self.force_move_colors.values():
            colors.change_color(color, r, g, b)

    #need to do the count_down here
    def count_down(self):
        self.change_all_move_colors(80, 0, 0)
        if self.play_audio:
            self.start_beep.start_effect()
        time.sleep(0.75)
        self.change_all_move_colors(70, 100, 0)
        if self.play_audio:
            self.start_beep.start_effect()
        time.sleep(0.75)
        self.change_all_move_colors(0, 70, 0)
        if self.play_audio:
            self.start_beep.start_effect()
        time.sleep(0.75)
        self.change_all_move_colors(0, 0, 0)
        if self.play_audio:
            self.start_game.start_effect()

    def get_change_time(self, speed_up):
        min_moves = len(self.move_serials) - 2
        if min_moves <= 0:
            min_moves = 1
        
        game_percent = (self.num_dead/min_moves)
        if game_percent > 1.0:
            game_percent = 1.0
        min_music_fast = common.lerp(MIN_MUSIC_FAST_TIME, END_MIN_MUSIC_FAST_TIME, game_percent)
        max_music_fast = common.lerp(MAX_MUSIC_FAST_TIME, END_MAX_MUSIC_FAST_TIME, game_percent)

        min_music_slow = common.lerp(MIN_MUSIC_SLOW_TIME, END_MIN_MUSIC_SLOW_TIME, game_percent)
        max_music_slow = common.lerp(MAX_MUSIC_SLOW_TIME, END_MAX_MUSIC_SLOW_TIME, game_percent)
        if speed_up:
            added_time = random.uniform(min_music_fast, max_music_fast)
        else:
            added_time = random.uniform(min_music_slow, max_music_slow)
        return time.time() + added_time

    def change_music_speed(self, fast):
        change_percent = numpy.clip((time.time() - self.change_time)/INTERVAL_CHANGE, 0, 1)
        if fast:
            self.music_speed.value = common.lerp(FAST_MUSIC_SPEED, SLOW_MUSIC_SPEED, change_percent)
        elif not fast:
            self.music_speed.value = common.lerp(SLOW_MUSIC_SPEED, FAST_MUSIC_SPEED, change_percent)
        self.audio.change_ratio(self.music_speed.value)

    def check_music_speed(self):
        if time.time() > self.change_time and time.time() < self.change_time + INTERVAL_CHANGE:
            self.change_music_speed(self.speed_up)
            self.currently_changing = True
        elif time.time() >= self.change_time + INTERVAL_CHANGE and self.currently_changing:
            self.music_speed.value = SLOW_MUSIC_SPEED if self.speed_up else FAST_MUSIC_SPEED
            self.speed_up =  not self.speed_up
            self.change_time = self.get_change_time(speed_up = self.speed_up)
            self.audio.change_ratio(self.music_speed.value)
            self.currently_changing = False

    def get_real_team(self, team):
        if team < 0:
            return -1
        else:
            return team

    def reveal(self):
        self.werewolf_reveal.value = 2

    def werewolf_audio_cue(self):
        if self.werewolf_timer - (time.time() - self.start_timer) <= 30 and self.audio_cue == 0:
            Audio('audio/Joust/sounds/30 werewolf.wav').start_effect()
            self.audio_cue = 1
        if self.werewolf_timer - (time.time() - self.start_timer) <= 10 and self.audio_cue == 1:
            Audio('audio/Joust/sounds/10 werewolf.wav').start_effect()
            self.audio_cue = 2
        if self.werewolf_timer - (time.time() - self.start_timer) <= 0 and self.audio_cue == 2:
            Audio('audio/Joust/sounds/werewolf reveal 2.wav').start_effect()
            self.reveal()
            self.audio_cue = 3
            self.change_time = time.time()-0.001
        elif self.audio_cue == 3:
            self.check_music_speed()
            
                

    def check_end_game(self):
        winning_team = -100
        team_win = True
        for move_serial, dead in self.dead_moves.items():
            #if we are alive
            if dead.value == 1:
                if winning_team == -100:
                    winning_team = self.get_real_team(self.teams[move_serial])
                elif self.get_real_team(self.teams[move_serial]) != winning_team:
                    team_win = False
            if dead.value == 0:
                #This is to play the sound effect
                self.num_dead += 1
                dead.value = -1
                self.non_stop_deaths[move_serial] += 1
                if self.play_audio:
                    self.explosion.start_effect()
            if dead.value == 2:
                dead.value = 1
                if self.play_audio:
                    self.revive.start_effect()
                

        if team_win:
            self.update_status('ending',winning_team)
            if self.play_audio:
                self.end_game_sound(winning_team)
            for move_serial in self.teams.keys():
                if self.get_real_team(self.teams[move_serial]) == winning_team:
                    self.winning_moves.append(move_serial)
            self.game_end = True

    def stop_tracking_moves(self):
        for proc in self.tracked_moves.values():
            proc.terminate()
            proc.join()
            time.sleep(0.02)

    def end_game(self):
        if self.play_audio:
            self.audio.stop_audio()
        end_time = time.time() + END_GAME_PAUSE
                
        h_value = 0

        while (time.time() < end_time):
            time.sleep(0.01)
            win_color = colors.hsv2rgb(h_value, 1, 1)
            for win_move in self.winning_moves:
                win_color_array = self.force_move_colors[win_move]
                colors.change_color(win_color_array, *win_color)
            h_value = (h_value + 0.01)
            if h_value >= 1:
                h_value = 0
        self.running = False

    def end_game_sound(self, winning_team):
        if winning_team == -1:
            team_win = Audio('audio/Joust/sounds/werewolf win.wav')
        else:
            team_win = Audio('audio/Joust/sounds/human win.wav')
        team_win.start_effect()

    def werewolf_intro(self):
        #don't wait so colors change during prompts
        Audio('audio/Joust/sounds/werewolf intro.wav').start_effect()
        time.sleep(3)
        self.change_all_move_colors(0,0,80)
        time.sleep(2)
        self.change_all_move_colors(0,0,30)
        time.sleep(14)
        self.change_all_move_colors(20, 20, 20)
        time.sleep(6)
        self.start_timer = time.time()
        

    def game_loop(self):
        self.track_moves()
        self.werewolf_intro()
        self.werewolf_reveal.value = 1
        self.show_team_colors.value = 0
        self.count_down()
        self.change_time = time.time() + 6
        time.sleep(0.02)
        if self.play_audio:
            self.audio.start_audio_loop()
            self.audio.change_ratio(self.music_speed.value)
        else:
            #when no audio is playing set the music speed to middle speed
            self.music_speed.value = (FAST_MUSIC_SPEED + SLOW_MUSIC_SPEED) / 2

            
        time.sleep(0.8)
        self.music_speed.value = SLOW_MUSIC_SPEED
        self.audio.change_ratio(self.music_speed.value)
        self.speed_up = False
        
        while self.running:
            #I think the loop is so fast that this causes 
            #a crash if done every loop
            if time.time() - 0.1 > self.update_time:
                self.update_time = time.time()
                self.check_command_queue()
                self.update_status('in_game')

            self.check_end_game()
            if self.play_audio:
                self.werewolf_audio_cue()
            if self.game_end:
                self.end_game()

        self.stop_tracking_moves()
         
    def check_command_queue(self):
        package = None
        while not(self.command_queue.empty()):
            package = self.command_queue.get()
            command = package['command']
        if not(package == None):
            # noinspection PyUnboundLocalVariable
            if command == 'killgame':
                self.kill_game()

    def update_status(self,game_status,winning_team=-1):
        data ={'game_status' : game_status,
               'game_mode' : "Werewolves",
               'winning_team' : winning_team}
        num = self.num_teams + 1
        data['winning_team'] += 1

        team_alive = [0]*num
        team_total = [0]*num

        for move in self.move_serials:
            team = self.teams[move]
            team += 1 #shift so bad guy team is 0
            if team < 0:
                team = 0
            team_total[team] += 1
            if self.dead_moves[move].value == 1:
                team_alive[team] += 1
        team_comp = list(zip(team_total,team_alive))
        data['team_comp'] = team_comp
        data['team_names'] = ['Werewolves', 'Humans']

        thyme = int(self.werewolf_timer - (time.time() - self.start_timer))
        if thyme < 0:
            data['time_to_reveal'] = 0
        else:
            data['time_to_reveal'] = thyme

        self.ns.status = data

    def kill_game(self):
        try:
            self.audio.stop_audio()
        except:
            print('no audio loaded to stop')        
        self.update_status('killed')
        all_moves = [x for x in self.dead_moves.keys()]
        end_time = time.time() + KILL_GAME_PAUSE     
        
        bright = 255
        while (time.time() < end_time):
            time.sleep(0.01)
            color = (bright,0,0)
            for move in all_moves:
                color_array = self.force_move_colors[move]
                colors.change_color(color_array, *color)
            bright = bright - 1
            if bright < 10:
                bright = 10

        self.running = False
                
                
        
        

            
        

            
