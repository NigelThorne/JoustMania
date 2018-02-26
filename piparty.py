import glob
import os
import os.path
import random
import time
from enum import Enum
from multiprocessing import Process, Value, Array, Queue, Manager

import psmove
import yaml

import colors
import common
import pair
import webui
from games import ffa, zombie, commander, swapper, tournament, speed_bomb, fight_club, traitor, joustFFA, were_joust, \
    nonstop_joust, joust_random_teams, joust
from piaudio import Music, DummyMusic, Audio, InitAudio, DJ

TEAM_NUM = len(colors.team_color_list)
#TEAM_COLORS = colors.generate_colors(TEAM_NUM)


SENSITIVITY_MODES = 3

class Opts(Enum):
    alive = 0
    selection = 1
    holding = 2
    team = 3
    game_mode = 4
    random_start = 5

class Alive(Enum):
    on = 0
    off = 1

class Selections(Enum):
    nothing = 0
    change_mode = 1
    start_game = 2
    add_game = 3
    change_sensitivity = 4
    change_instructions = 5
    show_battery = 6

class Holding(Enum):
    not_holding = 0
    holding = 1

class Sensitivity(Enum):
    slow = 0
    mid = 1
    fast = 2


#run as a separate process
def track_move(serial, move_num, move_opts, force_color, battery, dead_count):
    move = common.get_move(serial, move_num)
    move.set_leds(0,0,0)
    move.update_leds()
    random_color = random.random()

    
    while True:
        time.sleep(0.01)
        if move.poll():
            game_mode = common.Games(move_opts[Opts.game_mode.value])
            move_button = common.Button(move.get_buttons())
            if move_opts[Opts.alive.value] == Alive.off.value:
                if move_button == common.Button.SYNC:
                    move_opts[Opts.alive.value] = Alive.on.value
                    dead_count.value = dead_count.value - 1
                time.sleep(0.1)
            else:
                if move_button == common.Button.SHAPES:
                    move_opts[Opts.alive.value] = Alive.off.value
                    dead_count.value = dead_count.value + 1
                    move.set_leds(0,0,0)
                    move.set_rumble(0)
                    move.update_leds()
                    continue

                #show battery level
                if battery.value == 1:
                    battery_level = move.get_battery()
                    #granted a charging move should be dead 
                    #so it won't light up anyway
                    if battery_level == psmove.Batt_CHARGING: 
                        move.set_leds(*colors.Colors.White20.value)

                    elif battery_level == psmove.Batt_CHARGING_DONE: 
                        move.set_leds(*colors.Colors.White.value)

                    elif battery_level == psmove.Batt_MAX: 
                        move.set_leds(*colors.Colors.Green.value)

                    elif battery_level == psmove.Batt_80Percent:
                        move.set_leds(*colors.Colors.Turquoise.value)

                    elif battery_level == psmove.Batt_60Percent:
                        move.set_leds(*colors.Colors.Blue.value)

                    elif battery_level == psmove.Batt_40Percent:
                        move.set_leds(*colors.Colors.Yellow.value)

                    else : # under 40% - you should charge it!
                        move.set_leds(*colors.Colors.Red.value)
                    
                #custom team mode is the only game mode that
                #can't be added to con mode
                elif game_mode == common.Games.JoustTeams:
                    if move_opts[Opts.team.value] >= TEAM_NUM:
                        move_opts[Opts.team.value] = 3
                    move.set_leds(*colors.team_color_list[move_opts[Opts.team.value]].value)
                    if move_button == common.Button.MIDDLE:
                        #allow players to increase their own team
                        if move_opts[Opts.holding.value] == Holding.not_holding.value:
                            move_opts[Opts.team.value] = (move_opts[Opts.team.value] + 1) % TEAM_NUM
                            move_opts[Opts.holding.value] = Holding.holding.value

                #set leds to forced color
                elif sum(force_color) != 0:
                    move.set_leds(*force_color)

                elif game_mode == common.Games.JoustFFA:
                    move.set_leds(*colors.Colors.Orange.value)
                            
                elif game_mode == common.Games.JoustRandomTeams:
                    color = time.time()/10%1
                    color = colors.hsv2rgb(color, 1, 1)
                    move.set_leds(*color)

                elif game_mode == common.Games.Traitor:
                    if move_num%4 == 2 and time.time()/3%1 < .15:
                        move.set_leds(*colors.Colors.Red80.value)
                    else:
                        color = 1 - time.time()/10%1
                        color = colors.hsv2rgb(color, 1, 1)
                        move.set_leds(*color)

                elif game_mode == common.Games.WereJoust:
                    if move_num <= 0:
                        move.set_leds(*colors.Colors.Blue40.value)
                    else:
                        move.set_leds(*colors.Colors.Yellow.value)

                elif game_mode == common.Games.Zombies:
                        move.set_leds(*colors.Colors.Zombie.value)

                elif game_mode == common.Games.Commander:
                    if move_num % 2 == 0:
                        move.set_leds(*colors.Colors.Orange.value)
                    else:
                        move.set_leds(*colors.Colors.Blue.value)

                elif game_mode == common.Games.Swapper:
                    if (time.time()/5 + random_color)%1 > 0.5:
                        move.set_leds(*colors.Colors.Magenta.value)
                    else:

                        move.set_leds(*colors.Colors.Green.value)
                        
                elif game_mode == common.Games.FightClub:
                        move.set_leds(*colors.Colors.Green80.value)
                        
                elif game_mode == common.Games.NonStop:
                        move.set_leds(*colors.Colors.Turquoise.value)

                elif game_mode == common.Games.Tournament:
                    if move_num <= 0:
                        color = time.time()/10%1
                        color = colors.hsv2rgb(color, 1, 1)
                        move.set_leds(*color)
                    else:
                        move.set_leds(*colors.Colors.Blue40.value)


                elif game_mode == common.Games.Ninja:
                    if move_num <= 0:
                        move.set_leds(random.randrange(100, 200),0,0)
                    else:
                        move.set_leds(*colors.Colors.Red60.value)


                elif game_mode == common.Games.Random:
                    
                        move.set_leds(0,0,255)
                if move.get_trigger() > 100:
                        move_opts[Opts.random_start.value] = Alive.off.value
                if move_opts[Opts.random_start.value] == Alive.off.value:
                        move.set_leds(255,255,255)
                    

                if move_opts[Opts.holding.value] == Holding.not_holding.value:
                    #Change game mode and become admin controller
                    if move_button == common.Button.SELECT:
                        move_opts[Opts.selection.value] = Selections.change_mode.value
                        move_opts[Opts.holding.value] = Holding.holding.value

                    #start the game
                    if move_button == common.Button.START:
                        move_opts[Opts.selection.value] = Selections.start_game.value
                        move_opts[Opts.holding.value] = Holding.holding.value

                    #as an admin controller add or remove game from convention mode
                    if move_button == common.Button.CROSS:
                        move_opts[Opts.selection.value] = Selections.add_game.value
                        move_opts[Opts.holding.value] = Holding.holding.value

                    #as an admin controller change sensitivity of controllers
                    if move_button == common.Button.CIRCLE:
                        move_opts[Opts.selection.value] = Selections.change_sensitivity.value
                        move_opts[Opts.holding.value] = Holding.holding.value

                    #as an admin controller change if instructions play
                    if move_button == common.Button.SQUARE:
                        move_opts[Opts.selection.value] = Selections.change_instructions.value
                        move_opts[Opts.holding.value] = Holding.holding.value

                    #as an admin show battery level of controllers
                    if move_button == common.Button.TRIANGLE:
                        move_opts[Opts.selection.value] = Selections.show_battery.value
                        move_opts[Opts.holding.value] = Holding.holding.value
                    

                if move_button == common.Button.NONE:
                    move_opts[Opts.holding.value] = Holding.not_holding.value


        move.update_leds()

class GameFactory():
    def __init__(self, command_queue, ns):
        self.ns = ns
        self.command_queue = command_queue
        # Ideally the games would register themselves with the GameFactory...
        self.games= {
            common.Games.JoustFFA: joustFFA.JoustFFA,
            common.Games.JoustTeams: joust.Joust,
            common.Games.JoustRandomTeams: joust_random_teams.JoustRandomTeams,
            common.Games.Traitor: traitor.Traitor,
            common.Games.WereJoust: were_joust.WereJoust,
            common.Games.Zombies: zombie.Zombie,
            common.Games.Commander: commander.Commander,
            common.Games.Swapper: swapper.Swapper,
            common.Games.FightClub: fight_club.Fight_club,
            common.Games.Tournament: tournament.Tournament,
            common.Games.NonStop: nonstop_joust.NonStopJoust,
            common.Games.Ninja: speed_bomb.Bomb,
            common.Games.Random: joust.Joust,
        }

    def create_game(self, game_mode, game_moves, fight_music, teams ):
        return self.games[game_mode](game_moves, self.command_queue, self.ns, fight_music, teams, game_mode)

class Menu():
    def __init__(self):

        self.command_queue = Queue()
        self.joust_manager = Manager()

        self.ns = self.joust_manager.Namespace()
        self.ns.status = dict()
        self.ns.settings = dict()
        self.ns.battery_status = dict()

        self.web_proc = Process(target=webui.start_web, args=(self.command_queue,self.ns))
        self.web_proc.start()

        self.dj = DJ()
        self.game_factory = GameFactory(self.command_queue, self.ns)

        self.command_from_web = ''
        self.initialize_settings()
        self.update_settings_file()

        #defined outside of ns.settings as it's a purely dev option
        self.experimental = False

        self.move_count = psmove.count_connected()
        self.dead_count = Value('i', 0)
        self.moves = [psmove.PSMove(x) for x in range(psmove.count_connected())]
        self.admin_move = None

        self.out_moves = {} #move controllers that have been taken out of play
        self.random_added = []
        self.rand_games_recently_played_list = []

        self.show_battery = Value('i', 0)
        
        self.pairing_currently = False #only allow one move to be paired at a time
        self.tracked_moves = {}
        self.force_color = {} #used to force the color change of a move

        self.paired_moves = []
        self.move_opts = {}
        self.teams = {}
        self.game_mode = common.Games.Random

        self.pair = pair.Pair()

        self.game_loop_iteration_counter = 0 # game_loop iteration count


    def refresh_out_moves(self):
        for move in self.moves:
            serial = move.get_serial()
            if serial in self.move_opts:
                if self.move_opts[serial][Opts.alive.value] == Alive.off.value:
                    self.out_moves[serial] = Alive.off.value
                else:
                    self.out_moves[serial] = Alive.on.value

    def check_for_new_moves(self):
        self.pair.enable_bt_scanning(True)
        #need to start tracking of new moves in here
        if psmove.count_connected() != self.move_count:
            self.moves = [psmove.PSMove(x) for x in range(psmove.count_connected())]
            self.move_count = len(self.moves)

    def pair_usb_move(self, move):
        if not self.pairing_currently:
            move_serial = move.get_serial()
            if move.connection_type == psmove.Conn_USB:
                if move_serial not in self.tracked_moves:
                    self.pair.pair_move_by_usb(move)
                    move.set_leds(255,255,255)
                    move.update_leds()

    def pair_move(self, move, move_num):
        """start a process to monitor the move controller and update it."""
        move_serial = move.get_serial()
        if move_serial not in self.tracked_moves:
            color = Array('i', [0] * 3)
            opts = Array('i', [0] * 6)
            if move_serial in self.teams:
                opts[Opts.team.value] = self.teams[move_serial]
            else:
                #initialize to team Yellow
                opts[Opts.team.value] = 3
            if move_serial in self.out_moves:
                opts[Opts.alive.value] = self.out_moves[move_serial]
            opts[Opts.game_mode.value] = self.game_mode.value

            #now start tracking the move controller
            proc = Process(target=track_move, args=(move_serial, move_num, opts, color, self.show_battery, self.dead_count))
            self.move_opts[move_serial] = opts
            self.force_color[move_serial] = color
            proc.start()
            self.tracked_moves[move_serial] = proc
        self.refresh_out_moves()

    def game_mode_announcement(self):
        if self.game_mode == common.Games.JoustFFA:
            Audio('audio/Menu/menu Joust FFA.wav').start_effect()
        if self.game_mode == common.Games.JoustTeams:
            Audio('audio/Menu/menu Joust Teams.wav').start_effect()
        if self.game_mode == common.Games.JoustRandomTeams:
            Audio('audio/Menu/menu Joust Random Teams.wav').start_effect()
        if self.game_mode == common.Games.Traitor:
            Audio('audio/Menu/menu Traitor.wav').start_effect()
        if self.game_mode == common.Games.WereJoust:
            Audio('audio/Menu/menu werewolfs.wav').start_effect()
        if self.game_mode == common.Games.Zombies:
            Audio('audio/Menu/menu Zombies.wav').start_effect()
        if self.game_mode == common.Games.Commander:
            Audio('audio/Menu/menu Commander.wav').start_effect()
        if self.game_mode == common.Games.Swapper:
            Audio('audio/Menu/menu Swapper.wav').start_effect()
        if self.game_mode == common.Games.Tournament:
            Audio('audio/Menu/menu Tournament.wav').start_effect()
        if self.game_mode == common.Games.Ninja:
            Audio('audio/Menu/menu ninjabomb.wav').start_effect()
        if self.game_mode == common.Games.Random:
            Audio('audio/Menu/menu Random.wav').start_effect()
        if self.game_mode == common.Games.FightClub:
            Audio('audio/Menu/menu FightClub.wav').start_effect()
        if self.game_mode == common.Games.NonStop:
            Audio('audio/Menu/menu NonStopJoust.wav').start_effect()

    def check_change_mode(self):
        change_mode = False
        for move, move_opt in self.move_opts.items():
            if move_opt[Opts.selection.value] == Selections.change_mode.value:
                #remove previous admin, and set new one
                if self.ns.settings['move_can_be_admin']:
                    if self.admin_move:
                        self.force_color[self.admin_move][0] = 0
                        self.force_color[self.admin_move][1] = 0
                        self.force_color[self.admin_move][2] = 0
                    self.admin_move = move
                    change_mode = True
                move_opt[Opts.selection.value] = Selections.nothing.value

        if self.command_from_web == 'changemode':
            self.command_from_web = ''
            change_mode = True

        if change_mode:
            self.game_mode = self.game_mode.next()
            self.reset_controller_game_state()
            if not self.ns.settings['play_audio']: #skip games that need sound
                if self.game_mode == common.Games.Commander:
                    self.game_mode = self.game_mode.next()
                if self.game_mode == common.Games.WereJoust:
                    self.game_mode = self.game_mode.next()
            for opt in self.move_opts.values():
                opt[Opts.game_mode.value] = self.game_mode.value
            if self.ns.settings['play_audio']:
                self.game_mode_announcement()
                
    #all controllers need to opt-in again in order for the game to start
    def reset_controller_game_state(self):
        for move_opt in self.move_opts.values():
            #on means off here
            move_opt[Opts.random_start.value] = Alive.on.value
        self.random_added = []

    def no_playstation_controllers_attached_to_usb(self):
        return "0" in os.popen('lsusb | grep "PlayStation Move motion controller" | wc -l').read()

    def menu_loop(self):
        self.menu_music_needs_playing = True
        while True:
            self.play_menu_music()
            self.game_loop_iteration_counter= self.game_loop_iteration_counter + 1

            if self.pairing_currently and self.no_playstation_controllers_attached_to_usb():
                self.pairing_currently = False

            if not self.pairing_currently:
                if self.has_untracked_controllers():
                    for move_num, move in enumerate(self.moves):
                        if move.connection_type == psmove.Conn_USB:
                            self.pair_usb_move(move)
                        else:
                            self.pair_move(move, move_num)
                self.check_for_new_moves()
                if self.has_tracked_controllers():
                    self.check_change_mode()
                    self.check_admin_controls()
                    self.check_start_game()
                self.check_command_queue()
            self.update_status('menu')

    def has_tracked_controllers(self):
        return len(self.tracked_moves) > 0

    def has_untracked_controllers(self):
        return psmove.count_connected() != len(self.tracked_moves)

    def play_menu_music(self):
        if self.menu_music_needs_playing:
            self.menu_music_needs_playing = False
            try:
                self.menu_music = Music(random.choice(glob.glob("audio/MenuMusic/*")))
                self.menu_music.start_audio_loop()
            except Exception:
                self.menu_music = DummyMusic()

    def should_show_battery(self):
        show_bat = False
        for move_opt in self.move_opts.values():
            if move_opt[Opts.selection.value] == Selections.show_battery.value and move_opt[Opts.holding.value] == Holding.holding.value:
                show_bat = True
        if show_bat:
            return 1
        else:
            return 0

    def check_admin_controls(self):
        self.show_battery.value = self.should_show_battery()

        # stop controller being admin if the setting says no admins.
        if not self.ns.settings['move_can_be_admin'] and self.admin_move != None:
            self.force_color[self.admin_move][0] = 0
            self.force_color[self.admin_move][1] = 0
            self.force_color[self.admin_move][2] = 0
            self.admin_move = None

        if self.admin_move:
            #you can't add custom teams mode to con mode, don't set colors
            admin_opt = self.move_opts[self.admin_move]

            #to play instructions or not
            if admin_opt[Opts.selection.value] == Selections.change_instructions.value:
                admin_opt[Opts.selection.value] = Selections.nothing.value
                self.update_setting('play_instructions', not self.ns.settings['play_instructions'])
                if self.ns.settings['play_audio']:
                    if self.ns.settings['play_instructions']:
                        Audio('audio/Menu/instructions_on.wav').start_effect()
                    else:
                        Audio('audio/Menu/instructions_off.wav').start_effect()

            #change sensitivity
            if admin_opt[Opts.selection.value] == Selections.change_sensitivity.value:
                admin_opt[Opts.selection.value] = Selections.nothing.value

                self.update_setting('sensitivity', (self.ns.settings['sensitivity'] + 1) %  SENSITIVITY_MODES)
                if self.ns.settings['play_audio']:
                    if self.ns.settings['sensitivity'] == Sensitivity.slow.value:
                        Audio('audio/Menu/slow_sensitivity.wav').start_effect()
                    elif self.ns.settings['sensitivity'] == Sensitivity.mid.value:
                        Audio('audio/Menu/mid_sensitivity.wav').start_effect()
                    elif self.ns.settings['sensitivity'] == Sensitivity.fast.value:
                        Audio('audio/Menu/fast_sensitivity.wav').start_effect()
                
            #no admin colors in con custom teams mode
            if self.game_mode == common.Games.JoustTeams or self.game_mode == common.Games.Random:
                self.force_color[self.admin_move][0] = 0
                self.force_color[self.admin_move][1] = 0
                self.force_color[self.admin_move][2] = 0
            else:
                #if game is in con mode, admin is green, otherwise admin is red
                if self.game_mode.name in self.ns.settings['random_modes']:
                    self.force_color[self.admin_move][0] = 0
                    self.force_color[self.admin_move][1] = 200

                else:
                    self.force_color[self.admin_move][0] = 200
                    self.force_color[self.admin_move][1] = 0

                #add or remove game from con mode
                if admin_opt[Opts.selection.value] == Selections.add_game.value:
                    admin_opt[Opts.selection.value] = Selections.nothing.value
                    if self.game_mode.name not in self.ns.settings['random_modes']:
                        temp_random_modes = self.ns.settings['random_modes']
                        temp_random_modes.append(self.game_mode.name)
                        self.update_setting('random_modes',temp_random_modes)
                        if self.ns.settings['play_audio']:
                            Audio('audio/Menu/game_on.wav').start_effect()
                    elif len(self.ns.settings['random_modes']) > 1:
                        temp_random_modes = self.ns.settings['random_modes']
                        temp_random_modes.remove(self.game_mode.name)
                        self.update_setting('random_modes',temp_random_modes)
                        if self.ns.settings['play_audio']:
                            Audio('audio/Menu/game_off.wav').start_effect()
                    else:
                        if self.ns.settings['play_audio']:
                            Audio('audio/Menu/game_err.wav').start_effect()
                    self.update_settings_file()
            
    def initialize_settings(self):
        #default settings
        temp_settings = ({ 
            'sensitivity': Sensitivity.mid.value,
            'play_instructions': True,
            #we store the name, not the enum, so the webui can process it more easily
            'random_modes': [
                common.Games.JoustFFA.name,
                common.Games.JoustRandomTeams.name
                #common.Games.WereJoust.name,
                #common.Games.Swapper.name
                ],
            'play_audio': True,
            'move_can_be_admin': True,
            'enforce_minimum': True,
            'red_on_kill': True,
            'random_teams': True,
            'color_lock': False,
            'color_lock_choices':{
                2: ['Magenta','Green'],
                3: ['Orange','Turquoise','Purple'],
                4: ['Yellow','Green','Blue','Purple']
            }
        })
        try:
            #if anything fails during the settings file load, ignore file and stick with defaults
            with open(common.SETTINGS_FILE,'r') as yaml_file:
                file_settings = yaml.load(yaml_file)

            temp_colors = file_settings['color_lock_choices']
            for key in temp_colors.keys():
                colorset = temp_colors[key]
                if len(colorset) != len(set(colorset)):
                    temp_colors[key] = temp_settings['color_lock_choices'][key]

            for setting in file_settings.keys():
                if setting not in common.REQUIRED_SETTINGS:
                    file_settings.pop(setting)

            for game in [common.Games.JoustTeams,common.Games.Random]:
                if game.name in file_settings['random_modes']:
                    file_settings['random_modes'].remove(game.name)

            for game in file_settings['random_modes']:
                if game not in [game.name for game in common.Games]:
                    file_settings['random_modes'].remove(game)

            if file_settings['random_modes'] == []:
                file_settings['random_modes'] = [common.Games.JoustFFA.name]

            temp_settings.update(file_settings)
            temp_settings['color_lock_choices'] = temp_colors

        except:
            pass

        #force these settings
        temp_settings.update({
            'play_audio': True,
            'move_can_be_admin': True,
            'enforce_minimum': True
        })
        self.ns.settings = temp_settings
    
    def update_settings_file(self):
        with open(common.SETTINGS_FILE,'w') as yaml_file:
            yaml.dump(self.ns.settings,yaml_file)
        #option to make file editable by non-root
        #let's leave it as root only, people shouldn't
        #mess with the config file for now
        #os.system('chmod 666 %s' % com mon.SETTINGS_FILE)

    def update_setting(self,key,val):
        temp_settings = self.ns.settings
        temp_settings[key] = val
        self.ns.settings = temp_settings
        self.update_settings_file()


    def check_command_queue(self):
        if not(self.command_queue.empty()):
            package = self.command_queue.get()
            command = package['command']
            if command == 'admin_update':
                self.web_admin_update(package['admin_info'])
            else:
                self.command_from_web = command

    def update_status(self,game_status):
        self.ns.status ={
            'game_status' : game_status,
            'game_mode' : self.game_mode.pretty_name,
            'move_count' : self.move_count,
            'alive_count' : self.move_count - self.dead_count.value,
            'ticker': self.game_loop_iteration_counter
        }

        battery_status = {}
        for move in self.moves:
            move.poll()
            battery_status[move.get_serial()] = move.get_battery()
        self.ns.battery_status = battery_status

        self.ns.out_moves = self.out_moves

    def stop_tracking_moves(self):
        for proc in self.tracked_moves.values():
            proc.terminate()
            proc.join()
            
    def check_start_game(self):
        self.refresh_out_moves()
        start_game = True
        for serial in self.move_opts.keys():
            #on means off here
            if self.out_moves[serial] == Alive.on.value and self.move_opts[serial][Opts.random_start.value] == Alive.on.value:
                start_game = False
            if self.move_opts[serial][Opts.random_start.value] == Alive.off.value and serial not in self.random_added:
                self.random_added.append(serial)
                if self.ns.settings['play_audio']:
                    Audio('audio/Joust/sounds/start.wav').start_effect()

        if start_game:
            if self.game_mode == common.Games.Random:
                self.start_game(random_mode=True)
            else:
                self.start_game()

        if self.command_from_web == 'startgame':
            self.command_from_web = ''
            self.start_game()

    def start_game(self, random_mode=False):
        self.pair.enable_bt_scanning(False)
        self.refresh_out_moves()
        self.stop_tracking_moves()
        time.sleep(1)
        self.teams = {serial: self.move_opts[serial][Opts.team.value] for serial in self.tracked_moves.keys() if self.out_moves[serial] == Alive.on.value}
        game_moves = [move.get_serial() for move in self.moves if self.out_moves[move.get_serial()] == Alive.on.value]
        game_moves_count = len(game_moves)
        try:
            self.menu_music.stop_audio()
        except:
            pass

        if game_moves_count < self.game_mode.minimum_players and self.ns.settings['enforce_minimum']:
            Audio('audio/Menu/notenoughplayers.wav').start_effect()
            self.tracked_moves = {}
            return
        self.update_status('starting')

        if random_mode:
            self.game_mode = self.select_random_game_mode(game_moves_count)

        if self.ns.settings['play_instructions'] and self.ns.settings['play_audio']:
            self.dj.read_instructions(self.game_mode.instructions)

        fight_music = self.dj.load_random_music(self.game_mode.music_folder)

        if self.game_mode == common.Games.JoustFFA and self.experimental:
            print("Playing EXPERIMENTAL FFA Mode.")
            moves = [ common.get_move(serial, num) for num, serial in enumerate(game_moves) ]
            game = ffa.FreeForAll(moves, fight_music)
        else:
            #may need to put in moves that have selected to not be in the game
            game = self.game_factory.create_game(self.game_mode, game_moves, fight_music, self.teams)
        game.game_loop()

        self.tracked_moves = {}
        if random_mode:
            self.game_mode = common.Games.Random
            if self.ns.settings['play_instructions']:
                if self.ns.settings['play_audio']:
                    Audio('audio/Menu/tradeoff2.wav').start_effect_and_wait()

        self.menu_music_needs_playing = True

        #turn off admin mode so someone can't accidentally press a button    
        self.admin_move = None
        self.random_added = []

    def select_random_game_mode(self, number_of_players):
        """
        Select a new game randomly from the list in the settings. "random_modes"
        Ignore moves without enough players if `enforce_minimum` is set
        Play Joust FFA if no modes have enough players
        Avoid playing the same game twice in a row if there are other options
        Try to play all random games before starting again.
            (uses self.rand_games_recently_played_list to hold random games recently played.)
        """

        good_random_modes = [common.Games[game] for game in self.ns.settings['random_modes']]

        if self.ns.settings['enforce_minimum']:
            good_random_modes = [game for game in good_random_modes if game.minimum_players <= number_of_players]

        if len(good_random_modes) == 0:
            return common.Games.JoustFFA  # force Joust FFA

        if len(good_random_modes) == 1:
            return good_random_modes[0]

        self.rand_games_recently_played_list.append(self.game_mode)
        unplayed_random_modes = [game for game in good_random_modes if game not in self.rand_games_recently_played_list]

        if len(unplayed_random_modes) == 0:
            # empty rand game list, append old game, to not play it twice
            self.rand_games_recently_played_list = [self.game_mode]
            unplayed_random_modes = [game for game in good_random_modes if game not in self.rand_games_recently_played_list]

        # At this point there will always be at least one game unplayed.
        return random.choice(unplayed_random_modes)


if __name__ == "__main__":
    InitAudio()
    piparty = Menu()
    piparty.menu_loop()
