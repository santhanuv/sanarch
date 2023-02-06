import curses
from curses import wrapper
import os

from lib.disk import blockdevice

class MenuItem:
    ESC = 27

    def __init__(self, key = None, value = None):
        self.key = key
        self.value = value

    def display(self, window, x_begin, y_begin):
        self.window.clear()
        
        max_y, max_x = window.getmaxyx()
        gap = max_x // 2 - 2

        window.addstr(y_begin, x_begin, f'{self.key}')
        window.addstr(y_begin, x_begin + gap, f'{self.value}')

        self.window.refresh()
       

class Menu:
    SELECT_WIN_HEIGHT = 1
    SELECT_WIN_WIDTH = 40
    
    MAIN_WIN_Y = 5
    MAIN_WIN_X = 3
    SELECT_WIN_Y = 5
    SELECT_WIN_X = 3
    #SELECT_WIN_Y_OFFSET = 4
    #SELECT_WIN_X_OFFSET = 0

    SELECT_ITEM_NAME_Y = 0
    SELECT_ITEM_NAME_X = 2

    SELECT_ITEM_VALUE_Y = 0
    SELECT_ITEM_VALUE_X = 25

    def __init__(self, blockdevs_info = None):
        self.selected = 0
        self.selection_stack = []
        self.main_str = "Confirm the installation profile: "
        self.blockdevs_info = blockdevs_info
        self.exit = False

    def handle_keypress(self, key):        
        handled = False

        # if key == 'KEY_UP' or key == 'k':
        #     self.seleted = (self.seleted - 1) % len(self.options)
        #     handled = True
        # elif key == 'KEY_DOWN' or key == 'j':
        #     self.seleted = (self.seleted + 1) % len(self.options)
        #     handled = True
        # elif key == 'KEY_LEFT' or key == 'h':
        #     if self.fullscreen:
        #         self.fullscreen = False
        #     else:
        #         self.exit = True
            
        #     handled = True
        # elif  key == '\n' or key == 'KEY_RIGHT' or key == 'KEY_ENTER' or key == '\r' or key == 'l':
        #     self.fullscreen = True
        #     handled = True

        return handled

    def display(self):
        # Set the esc key delay to 25 milliseconds
        os.environ.setdefault('ESCDELAY', '25')
        wrapper(self.main)

    def main(self, stdscr):
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        self.SELECTED_COLOR = curses.color_pair(1)

        bdev = BlockDeviceMenu(info=self.blockdevs_info)

        while True:
            bdev.display(stdscr, selected_color=self.SELECTED_COLOR)

            key = stdscr.getkey()
            if not bdev.handle_keypress(key):
                self.handle_keypress(key)





class BlockDeviceMenu(MenuItem):
    def __init__(self, info = None):
        self.heading = "Block Devices"
        
        super().__init__(self.heading)

        self.exit = False
        self.fullscreen = False

        if not info:
            self.exit = True
        else:
            self.info = info
            print(self.info)

        self.options = [bdev['name'] for bdev in self.info]
        self.seleted = 0

    def handle_keypress(self, key):  
        handled = True      
        try:
            if ord(key) == 27:
                self.fullscreen = False
                handled = True
            else:
                key = key.lower()
        except TypeError:
            pass

        
        if key == 'KEY_UP' or key == 'k':
            self.seleted = (self.seleted - 1) % len(self.options)
            handled = True
        elif key == 'KEY_DOWN' or key == 'j':
            self.seleted = (self.seleted + 1) % len(self.options)
            handled = True
        elif key == 'KEY_LEFT' or key == 'h':
            self.fullscreen = False
            handled = True
        elif  key == '\n' or key == 'KEY_RIGHT' or key == 'KEY_ENTER' or key == '\r' or key == 'l':
            self.fullscreen = True
            handled = True

        return handled


    def __show_options(self, left_win, selected_color):
        for idx, option in enumerate(self.options):
            selected_win = left_win.subwin(1, self.left_width, self.y_begin + idx, self.x_begin)
            selected_win.clear()
            
            if idx == self.seleted:
                selected_win.bkgd(' ', selected_color)
                selected_win.addstr(0, 2, f'{option}')
            else:
                left_win.addstr(self.curr_lwin_line, 2, f'{option}')

            self.curr_lwin_line += 1
        
        selected_win.refresh()


    def display(self, window, selected_color = None):
        max_y, max_x = window.getmaxyx()
        # Initial position of cursor
        self.y_begin, self.x_begin = 2,2

        # Calculate the height and width of left window
        self.left_height = max_y - (1 + self.y_begin)
        self.left_width = max_x // 4 - (1 + self.x_begin)

        # For right window
        self.right_height = self.left_height
        self.right_width = max_x - self.left_width - 4 

        # Divide the window into left and right
        left_win = window.subwin(self.left_height, self.left_width, self.y_begin, self.x_begin)
        right_win = window.subpad(self.right_height, self.right_width, self.y_begin, self.left_width + 4)


        window.clear()

        if self.exit:
            return

        #left_win.clear()
        #right_win.clear()
        right_win.border()
        right_win.addstr(0, 2, "Info")
        
        # Initialize current window line to 1
        self.curr_lwin_line = 0
        
        # Show options
        self.__show_options(left_win, selected_color)
        
        # Show information about the selected option
        for dev in self.info:
            if dev['name'] == self.options[self.seleted]:
                bdev = blockdevice.BlockDevice(dev["name"], dev["size"], dev["type"], dev["path"], dev["model"]) 
                
                if self.fullscreen:
                    bdev.display(window=window, fullscreen = True)
                else:
                    bdev.display(window=right_win)

                break

        
        left_win.refresh()
        right_win.refresh()
        window.refresh()


            # Listen to key press
            #key = window.getkey()
            #self.__handle_keypress(key)
