import struct
import copy
from time import sleep
import os, sys 
import logging

import tkinter as Tk
from tkinter import ttk
import sys
import math
from time import sleep
import numpy as np
import argparse

from collections import deque
from  controller_if import ControllerInterface
from valve_message_handler import ValveMessageHandler

canvas_size = 450

# map val to a color string in the '#FFFFFFFF' format. val should be [0-32767]
def get_color( val ):

    max = 32767.0
    red = 0
    green = 0
    blue = 0

    if val < 0:
        val = 0
    
    val = float( val )
    if val > max:
        val = max
        
    # red
    if val < max/2:
        half = max/2.0
        red = (half-val) / half
        red *= 255
    else:
        half = max/2.0
        red = (val-half) / half
        red *= 255
        red = 0
        
    # green
    if val < max/2:
        blue = 255
    else:
        half = max/2.0
        blue = 1.0 - ( (val-half)/half ) 
        blue *= 255
        
    if val < max/2:
        half = max/2.0
        green = 1.0 - val/half
        green *= 255
    else:
        green = 0
        
    red = val / max
    red *= 255
#    green = red
    
#    blue = red + 32
#    if blue > 255:
#        blue = 255
        
    string = '#{0:02x}{1:02x}{2:02x}'.format( int(red), int(green), int(blue), width=2 )
    return string

def compute_z_val( total_mag, radius ):
    curve_pts = [ 1000, 1000, 930, 840, 620, 350 ]
    max_total_mag = 13000
    correction_vals = map( lambda x: max_total_mag*(x/1000.0), curve_pts )
    
    num_steps = 5
    max_radius = 16384
    radius_per_step = float( max_radius/num_steps )
    
    for i in range(num_steps):
        if (i+1) * radius_per_step > radius:
            break
            
    # lerp the correction
    t = (radius-(i*radius_per_step)) / radius_per_step
    
    correction = correction_vals[i] + t*(correction_vals[i+1] - correction_vals[i])
    
    return total_mag - correction

class TrackpadVis():
    def __init__( self, root, cntrlr_mgr, args ):
        self.root = root
        self.cntrlr_mgr = cntrlr_mgr
        self.args = args

        self.trackpad = 1  # right

        self.last_packet_num = 0

        self.rank =  8
        self.num_x = self.rank
        self.num_y = self.rank    
        self.num_pads = 1

        # Params to tune tracking algos.
        self.min_cell_z_value = 25

        self.x_boxes = []
        self.x_boxes.append( [] )
        self.x_boxes.append( [] )

        self.y_boxes = []
        self.y_boxes.append( [] )
        self.y_boxes.append( [] )
        
        self.grid_boxes = []
        self.grid_boxes.append( [] )
        self.grid_boxes.append( [] )
 
        self.z_val_lines = []
        self.z_val_lines.append( [] )
        self.z_val_lines.append( [] )
        
        self.z_val_dots = []
        self.z_val_dots.append( [] )
        self.z_val_dots.append( [] )
        
        self.z_val_history = []
        self.z_val_history.append( deque() )
        self.z_val_history.append( deque() )

        #self.vals_x_text = [[0 for x in range(self.num_x)] for y in range(self.num_pads)] 
        #self.vals_y_text = [[0 for x in range(self.num_x)] for y in range(self.num_pads)] 
        
        self.pos_history = []
        self.pos_history.append( deque() )
        self.pos_history.append( deque() )
      

        self.z_min_text = {}
        self.z_max_text = {}
        self.z_delta_text = {}

        self.radius_text = {}
        self.smooth_graph_line_x = {}
        self.smooth_graph_line_y = {}
        self.graph_line_x = {}
        self.graph_line_y = {}

        self.collapsed_dot = {}
        self.x_dots = {}
        self.y_dots = {}
        self.bounding_points = {}
        for i in range(self.num_pads):
            self.x_dots[i] = list()
            self.y_dots[i] = list()
            self.bounding_points[i] = []

        self.pos_dot = {} 
        self.vert_line = {}
        self.horiz_line = {}
        self.graph_canvas = {}
        self.z_graph_canvas = {}

        self.canvas = {}
        self.logfile = None

        self.create_panel()
        self.tick_job = self.root.after( self.args.tick, self.tick )
        
        while not self.cntrlr_mgr.is_open():
            sleep( 0.1 )
            
        self.pos_history_count = 50
        self.finger_down = [ False, False ]
        self.last_finger_pos = [ [0,0], [0,0] ]
        self.finger_delta = [ [0,0], [0,0] ]
       
    def get_logging_state( self ):
        if self.logfile is not None:
            return True
        else:
            return False
        
    def set_logging_state( self, state ):
        if state and not self.logfile:
            self.logfile = open( "trackpad_vis_rushmore_log.csv", 'w' )

        elif not state and self.logfile:
            self.logfile.close()
            self.logfile = None  

    def create_panel( self ):
        self.instruction_string = 'Trackpad Vis'

        self.grid_frame = Tk.Frame( self.root, bg = 'black' )
        self.grid_frame.grid( row=0, column=0 )

        self.canvas_size = canvas_size
            
        self.total_width = self.canvas_size
        
        self.slice_width_x = self.total_width / (self.num_x+2)
        self.slice_width_y = self.total_width / (self.num_y+2)
        
        # shrink the cells a bit so they have a border
        self.slice_width_y *= 0.95
        
        box_size = self.total_width / self.num_x
        
        for pad_num in range(self.num_pads):
            x_base = self.slice_width_x*2
            y_base = 10
    
            self.graph_height = 32767/3
            self.graph_cavnas_size = self.canvas_size
            
            self.canvas[pad_num] = Tk.Canvas( self.grid_frame,
                                              height=self.graph_cavnas_size+40,
                                              width=self.graph_cavnas_size+15,
                                              bg='#171737', bd=-2,
                                              highlightthickness=0  )
            canvas = self.canvas[pad_num]
            canvas.grid( row=0, column=pad_num, padx=5, pady=5 )
        
            # Draw the X baseline values
            for x in range(self.num_x):
                self.x_boxes[pad_num].append( canvas.create_rectangle( x_base, y_base, x_base+self.slice_width_x, y_base+self.slice_width_y, fill='white', outline='#707090' ) )
                
                x_base += self.slice_width_x

            x_base = 10
            y_base = self.slice_width_y*2
        
            box_size = self.total_width / self.num_y
            
            # Draw the Y baseline values
            for y in range(self.num_y):
                self.y_boxes[pad_num].append( canvas.create_rectangle( x_base, y_base, x_base+self.slice_width_x, y_base+self.slice_width_y, fill='white', outline='#707090' ) )
                
                y_base += self.slice_width_y
                
            # Draw the sums of the rows and colums as a grid
            x_base = self.slice_width_x*2
            y_base = self.slice_width_y*2
            
            for x in range(self.num_x):
                for y in range(self.num_y):
                    self.grid_boxes[pad_num].append( canvas.create_rectangle( x_base, y_base, x_base+self.slice_width_x, y_base+self.slice_width_y, fill='white', outline='#707090' ) )
                
                    y_base += self.slice_width_y
                    
                x_base += self.slice_width_x
                y_base = self.slice_width_y*2

  

            #draw a line graph of each axis
            vals = ( 0, 0, 0, 3100, 5414, 5708, 1118, 0, 0, 0, 0, 0, 0 )
            vert_list = []
            self.graph_canvas[pad_num] = Tk.Canvas(self.grid_frame,
                                                   height=self.graph_cavnas_size,
                                                   width=self.graph_cavnas_size,
                                                   bg='#171737', bd=-2,
                                                   highlightthickness=0)
            graph_canvas = self.graph_canvas[pad_num]            
            graph_canvas.grid( row=1, column=pad_num, padx=5, pady=5 )
            
            graph_canvas.create_rectangle( 0, 0, self.canvas_size, self.canvas_size, fill='#171737' )
            

            # add verts to the polygon, include two extras to close the poly back around at 0
            for i in range( self.num_x + 2 ):
                vert_list.append( (0, 0 ) )
            
            self.smooth_graph_line_x[pad_num] = graph_canvas.create_line( vert_list, smooth=1, width=5, fill='white' )
            self.graph_line_x[pad_num] = graph_canvas.create_polygon( vert_list, width=1, fill='#303050', outline='#707090' )

            # add verts to the polygon, include two extras to close the poly back around at 0
            for i in range( self.num_y+2 ):
                vert_list.append( (0, 0 ) )
            
            self.smooth_graph_line_y[pad_num] = graph_canvas.create_line( vert_list, smooth=1, width=5, fill='white' )
            self.graph_line_y[pad_num] = graph_canvas.create_polygon( vert_list, width=1, fill='#303050', outline='#707090' )
            
            # draw a dot a the average position
            self.vert_line[pad_num] = graph_canvas.create_line( ( (0,0), (1,1) ), fill='#a0a0c0', width=3 )
            self.horiz_line[pad_num] = graph_canvas.create_line( ( (0,0), (1,1) ), fill='#a0a0c0', width=3 )
            
            self.collapsed_dot[pad_num] = graph_canvas.create_oval( 0, 0, 0, 0, fill='#404040', outline='#d0d0f0', width=2 )

            for i in range(self.num_x):
                self.x_dots[pad_num].append(graph_canvas.create_oval( 0, 0, 0, 0, fill='#404040', outline='#e00000', width=2))
            for i in range(self.num_y):
                self.y_dots[pad_num].append(graph_canvas.create_oval( 0, 0, 0, 0, fill='#404040', outline='#00e000', width=2))

            self.pos_dot[pad_num] = graph_canvas.create_oval( 0, 0, 0, 0, fill='#404040', outline='#a0a0c0', width=2)

            # Create real-time Z value plots
            self.z_graph_canvas[pad_num] = Tk.Canvas(self.grid_frame,
                                                     height=self.graph_cavnas_size,
                                                     width=self.graph_cavnas_size,
                                                     bg='#171737', bd=-2,
                                                     highlightthickness=0)
            z_graph_canvas = self.z_graph_canvas[pad_num]
            z_graph_canvas.grid( row=2, column=pad_num, padx=5, pady=5 )
            
            z_graph_canvas.create_rectangle( 0, 0, self.canvas_size, self.canvas_size, fill='#202040' )
            
            self.z_val_line_count = 40
            self.z_val_dot_radius = 3
            self.z_val_graph_max = 80000
            self.z_val_graph_min = -20000
            self.z_val_graph_range = self.z_val_graph_max - self.z_val_graph_min
            self.z_val_tick_count = 10
            
            self.z_val_on = (-200, -2000) # left,right
            self.z_val_off = (-2100, -2100) # left,right

            for i in range( self.z_val_line_count ):
                self.z_val_lines[pad_num].append( z_graph_canvas.create_line( ( (-100,0), (-100,0) ), fill='#707090', width=3 ) )
                self.z_val_dots[pad_num].append( z_graph_canvas.create_oval( -100, 0, -100, 0, fill='#404040', outline='#707090', width=2 ) )
                
            for i in range( self.z_val_tick_count ):
                text = "{0}".format( int( self.z_val_graph_min + (i/float(self.z_val_tick_count)) * self.z_val_graph_range ) )
                x = self.canvas_size/2
                y = self.canvas_size - self.canvas_size*(float(i)/self.z_val_tick_count)
                gap = 20
                z_graph_canvas.create_text( x, y, justify=Tk.CENTER, text=text, fill='#707090') 
                z_graph_canvas.create_line( 0, y, x-gap, y, fill='#a0a0c0', width=1, dash=(3, 8) )
                z_graph_canvas.create_line( x+gap, y, self.canvas_size, y, fill='#a0a0c0', width=1, dash=(3, 8) )

            # draw the Z on and off lines
            x = self.canvas_size/2
            y = (float(self.z_val_on[pad_num])-self.z_val_graph_min) / self.z_val_graph_range
            y = self.canvas_size - self.canvas_size*y
            z_graph_canvas.create_line( 0, y, self.canvas_size, y, fill='#a0a0c0', width=3 )

            y = (float(self.z_val_off[pad_num])-self.z_val_graph_min) / self.z_val_graph_range
            y = self.canvas_size - self.canvas_size*y
            z_graph_canvas.create_line( 0, y, self.canvas_size, y, fill='#a0a0c0', width=3 )

                
            self.z_max_text[pad_num] = z_graph_canvas.create_text( 20, 10, justify=Tk.LEFT, text="max", fill='#707090') 
            self.z_min_text[pad_num] = z_graph_canvas.create_text( 80, 10, justify=Tk.LEFT, text="max", fill='#707090') 
            self.z_delta_text[pad_num] = z_graph_canvas.create_text( 140, 10, justify=Tk.LEFT, text="max", fill='#707090') 
            self.radius_text[pad_num] = z_graph_canvas.create_text( 200, 10, justify=Tk.LEFT, text="radius", fill='#707090')
    def weighted_average(self, vals):
        div = np.sum(vals)*(len(vals) - 1)
        if div == 0:
            return 0.0
        
        return sum([vals[i]*i for i in range(len(vals))]) / div

    def rescale_value(self, val, min_val, max_val):
        if val <= min_val:
            val = 0.0
        elif val >= max_val:
            val = 1.0
        else:
            val = (val - min_val)/(max_val - min_val)
        return val

    def log_trackpads(self):
        if not self.logfile:
            return

        self.logfile.write('x_vals, ')
        for val in self.x_vals:
            self.logfile.write('{0}, '.format(val))
        self.logfile.write('y_vals, ')
        for val in self.y_vals:
            self.logfile.write('{0}, '.format(val))
        
   #     self.logfile.write('raw_z_val, {0}, '.format(self.raw_z_val))

   #     self.logfile.write('x_pos, {0}, y_pos, {1}, radius, {2}, '.format(self.x_pos, self.y_pos, self.radius))
        self.logfile.write('\n')

    def get_index_position(self, index, num_vals):
        return (float(index)/num_vals)*self.graph_cavnas_size #+ (self.graph_cavnas_size/num_vals)/2

    def calc_index(self, pos, num_vals):
        return math.floor((pos/self.graph_cavnas_size)*num_vals)

    ################################################################################################
    ## Computes
    ################################################################################################
    def compute_z_corrected_val(self, pad_num, raw_values):
        total_mag_thresh = 1000

        if self.total_mag < total_mag_thresh:
            self.corrected_z_val = -10000
        else:

            curve_pts = [ 1000, 1000, 950, 825, 550, 175 ]
            max_total_mag = 20000
            correction_vals = map( lambda x: max_total_mag*(x/1000.0), curve_pts )

            num_steps = 5
            max_radius = 32767
            radius_per_step = float( max_radius/num_steps )

            for i in range(num_steps):
                if (i+1) * radius_per_step > self.radius:
                    break

            #print "slice: ", radius / radius_per_step, " percent: ", total_mag/float(max_total_mag)

            # lerp the correction
            t = (self.radius-(i*radius_per_step)) / radius_per_step

            clist = list(correction_vals)
            correction = clist[i] + t*(clist[i+1] - clist[i])

            self.corrected_z_val = self.total_mag - correction

            #print "radius: ", self.radius, "correction:", correction, "total_mag:", self.total_mag

        # keep a history of the last few z values so we can graph them 
        self.z_val_history[pad_num].append(self.corrected_z_val)
        if len(self.z_val_history[pad_num]) > self.z_val_line_count:
            self.z_val_history[pad_num].popleft()

    def compute_finger_down(self, pad_num, raw_values):

        max_cell = max( raw_values )

        #print "max_cell:",max_cell

        baseline_thresh = 1200
        hyst = 100

        release_thresh = baseline_thresh - hyst
        press_thresh = baseline_thresh + hyst

        radius_comp_max = 500
        radius_comp = radius_comp_max * self.radius / 32767.0

        max_cell = max_cell + radius_comp

        if self.finger_down[pad_num]:
            if max_cell < release_thresh:
                self.finger_down[pad_num] = False
        else:
            if max_cell > press_thresh:
                self.finger_down[pad_num] = True

        if self.finger_down[pad_num]:
            if self.corrected_z_val < self.z_val_off[pad_num]:
                self.finger_down[pad_num] = False
        else:
            if self.corrected_z_val > self.z_val_on[pad_num]:
                self.finger_down[pad_num] = True

    def compute_collapsed_values(self, pad_num, raw_values):
        # Zero values below threshold
        vals = raw_values*(raw_values >= self.min_cell_z_value)
        
        # Reshape into (num_x, num_y) 2D array.
        vals = vals.reshape([self.num_x, self.num_y])
        
        self.x_vals = np.sum(vals, axis=1)
        self.y_vals = np.sum(vals, axis=0)

    def compute_pos(self, pad_num, raw_values):

        x_val = self.rescale_value(self.weighted_average(self.x_vals), .1, .9)
        y_val = self.rescale_value(self.weighted_average(self.y_vals), .1, .9)
        

        self.x_pos = 2.0*(x_val - 0.5)*32767.0
        self.y_pos = 2.0*(y_val - 0.5)*32767.0
        
        self.raw_z_val = np.sum(self.x_vals) + np.sum(self.y_vals)
        self.radius = math.sqrt(self.x_pos**2 + self.y_pos**2)
#        self.log_trackpads();


        #if pad_num==1:
        #    print self.raw_z_val, self.radius

    def compute_total_mag(self, pad_num, raw_values):
        self.total_mag = np.sum(self.x_vals) + np.sum(self.y_vals)

    ################################################################################################
    ## Drawing
    ################################################################################################
    def draw_z_history_text(self, pad_num, raw_values):

  
        if (len(self.z_val_history[pad_num])):
            maxz = max(self.z_val_history[pad_num])
            minz = min(self.z_val_history[pad_num])
            self.z_graph_canvas[pad_num].itemconfig(self.z_max_text[pad_num] , text=int(maxz))	
            self.z_graph_canvas[pad_num].itemconfig(self.z_min_text[pad_num] , text=int(minz))
            self.z_graph_canvas[pad_num].itemconfig( self.z_delta_text[pad_num] , text="[{0}]".format( int(maxz-minz) ) )
            self.z_graph_canvas[pad_num].itemconfig( self.radius_text[pad_num] , text="[{0}]".format( int(self.radius) ) )

    def draw_z_history_graph(self, pad_num, raw_values):
        # update the z_value graph dots and lines
        if self.finger_down[pad_num]:
            z_val_base = self.z_val_off[pad_num]
        else:
            z_val_base = self.z_val_on[pad_num]

        for i in range( len( self.z_val_history[pad_num] ) ):
            z = self.z_val_history[pad_num][i]
            x = i*self.graph_cavnas_size/float( len( self.z_val_lines[pad_num] ) )
            y_stop = (z-self.z_val_graph_min)/self.z_val_graph_range
            y_stop = self.graph_cavnas_size - self.graph_cavnas_size*y_stop

            y_start = (float(z_val_base)-self.z_val_graph_min)/self.z_val_graph_range
            y_start = self.graph_cavnas_size - self.graph_cavnas_size*y_start

            self.z_graph_canvas[pad_num].coords( self.z_val_lines[pad_num][i], x, y_start, x, y_stop )
            self.z_graph_canvas[pad_num].coords( self.z_val_dots[pad_num][i], x-self.z_val_dot_radius, y_stop-self.z_val_dot_radius, x+self.z_val_dot_radius, y_stop+self.z_val_dot_radius )

    def draw_line_graphs(self, pad_num, raw_values):
        # Zero values below threshold
        vals = raw_values*(raw_values >= self.min_cell_z_value)
        
        # Reshape into (num_x, num_y) 2D array.
        vals = vals.reshape([self.num_x, self.num_y])
        
        x_vals = np.sum(vals, axis=1)
        y_vals = np.sum(vals, axis=0)

        # Update the X graph
        vert_list = []
        for i in range( len( x_vals ) ):
            val = x_vals[i]
            vert_list.append( float(i)/float(len(x_vals)-1) * self.graph_cavnas_size )
            vert_list.append( (1.0-float(val)/self.graph_height) * self.graph_cavnas_size )
        vert_list.append( self.graph_cavnas_size )
        vert_list.append( self.graph_cavnas_size )
        vert_list.append( 0 )
        vert_list.append( self.graph_cavnas_size )
        self.graph_canvas[pad_num].coords( self.graph_line_x[pad_num], Tk._flatten( vert_list ) )

        # Update the Y graph
        vert_list = []
        for i in range( len( y_vals ) ):
            val = y_vals[i]
            vert_list.append( (float(val)/self.graph_height) * self.graph_cavnas_size )
            vert_list.append( float(i)/float(len(y_vals)-1) * self.graph_cavnas_size )
        vert_list.append( 0 )
        vert_list.append( self.graph_cavnas_size )
        vert_list.append( 0 )
        vert_list.append( 0 )
        self.graph_canvas[pad_num].coords( self.graph_line_y[pad_num], Tk._flatten( vert_list ) )

    def draw_pos_dot(self, pad_num, raw_values):
        if self.finger_down[pad_num]:
            canvas_x_pos = (self.x_pos/(2.0*32767.0)+0.5) * self.graph_cavnas_size
            canvas_y_pos = (self.y_pos/(2.0*32767.0)+0.5) * self.graph_cavnas_size

            self.graph_canvas[pad_num].coords( self.vert_line[pad_num], ( canvas_x_pos, 0, canvas_x_pos, self.graph_cavnas_size ) )
            self.graph_canvas[pad_num].coords( self.horiz_line[pad_num], ( 0, canvas_y_pos, self.graph_cavnas_size, canvas_y_pos ) )

            dot_size = 5

            self.graph_canvas[pad_num].coords( self.pos_dot[pad_num], canvas_x_pos-dot_size, canvas_y_pos-dot_size, canvas_x_pos+dot_size, canvas_y_pos+dot_size )

        else:
            self.graph_canvas[pad_num].coords( self.pos_dot[pad_num], -100, 0, -100, 0 )
            self.graph_canvas[pad_num].coords( self.horiz_line[pad_num], -100, 0, -100, 0 )
            self.graph_canvas[pad_num].coords( self.vert_line[pad_num], -100, 0, -100, 0 )

    def draw_collapsed_xy(self, pad_num, raw_values):
        # draw the collapsed X and Y boxes in the top graph
        for i in range(self.num_x):
            box = self.x_boxes[pad_num][i]
            self.canvas[pad_num].itemconfig(box, fill=get_color(self.x_vals[i]*8))
        for i in range( self.num_y ):
            box = self.y_boxes[pad_num][i]
            self.canvas[pad_num].itemconfig(box, fill=get_color(self.y_vals[i]*8))
 
    def draw_grid(self, pad_num, raw_values):
        for i in range(len(self.grid_boxes[pad_num])):
            box = self.grid_boxes[pad_num][i]
            val = raw_values[i]
            self.canvas[pad_num].itemconfig(box, fill=get_color(val*40))

    def draw_row_column_centroids(self, pad_num, vals):
        # Zero values below threshold
        vals = vals*(vals >= self.min_cell_z_value)
        
        # Reshape into (num_y, num_x) 2D array.
        vals = np.transpose(vals.reshape([self.num_y, self.num_x]))
        
        x_centers = [self.weighted_average(v)*self.graph_cavnas_size for v in vals]
        y_centers = [self.weighted_average(v)*self.graph_cavnas_size for v in np.transpose(vals)]

        first_x_index = -1
        first_y_index = -1

        canvas = self.graph_canvas[pad_num]
        
        for i in range(len(x_centers)):
            if x_centers[i]:
                # First row to have non-zero value.
                if first_y_index < 0:
                    first_y_index = i
                y_pos = self.get_index_position(i, self.num_y)
                canvas.coords( self.x_dots[pad_num][i],
                               x_centers[i]-2, y_pos-2,
                               x_centers[i]+2, y_pos+2, )
            else:
                canvas.coords( self.x_dots[pad_num][i], 0, 0, 0, 0, )

        for i in range(len(y_centers)):
            if y_centers[i]:
                # First column to have non-zero value.
                if first_x_index < 0:
                    first_x_index = i
                x_pos = self.get_index_position(i, self.num_x)
                canvas.coords( self.y_dots[pad_num][i],
                               x_pos-2, y_centers[i]-2,
                               x_pos+2, y_centers[i]+2, )
            else:
                canvas.coords( self.y_dots[pad_num][i], 0, 0, 0, 0, )

        x1 = x_centers[first_y_index]
        x_index = self.calc_index(x1, self.num_x)
        v = [vals[first_y_index-1][x_index], vals[first_y_index][x_index], vals[first_y_index+1][x_index]]
        y1 = self.get_index_position(first_y_index, self.num_y) + (self.graph_cavnas_size/self.num_y)*self.weighted_average(v)

        y2 = y_centers[first_x_index]
        y_index = self.calc_index(y2, self.num_y)
        v = [vals[y_index][first_x_index], vals[y_index][first_x_index+1]]
        x2 = self.get_index_position(first_x_index, self.num_x) + (self.graph_cavnas_size/self.num_x)*self.weighted_average(v)

        x_pos = (x1 + x2) / 2
        y_pos = (y1 + y2) / 2
        canvas.coords( self.pos_dot[pad_num],
                       x_pos-5, y_pos-5,
                       x_pos+5, y_pos+5, )

    def draw_bounding_points(self, pad_num, raw_x_data, raw_y_data):
        # Reshape into (num_x, num_y) 2D array.
  #      vals = raw_data.reshape([self.num_x, self.num_y])
  #      cells_included = vals >= self.min_cell_z_value

        points = []
        for yi in range(self.num_y):
            for xi in range(self.num_x):
                if xi == 0:
                    prxz = 0
                    prx = False
                else:
                    prxz = vals[xi-1][yi]
                    prx = cells_included[xi-1][yi]
                if yi == 0:
                    pryz = 0
                    pry = False
                else:
                    pryz = vals[xi][yi-1]
                    pry = cells_included[xi][yi-1]
                
                if cells_included[xi][yi]:
                    if not prx:
                        v = [(xi-1)*prxz, xi*vals[xi][yi]]
                        points.append([xi - 1 + self.weighted_average(v), yi])
                    if not pry:
                        v = [(yi-1)*pryz, yi*vals[xi][yi]]
                        points.append([xi, yi - 1 + self.weighted_average(v)])
    ############################################################################################################
    ## Main Tick
    ############################################################################################################
    def tick( self ):
        if self.cntrlr_mgr.is_open(): 
            for pad_num in range(self.num_pads):
                device_data = self.cntrlr_mgr.get_data()

                if not ('rushmore_raw_data') in device_data:
                    continue

                # Values come in reversed.
                raw_values = np.array( device_data['rushmore_raw_data'], dtype=np.float32)
                raw_values = raw_values[::-1]
                if self.logfile:
                    self.logfile.write( 'raw_vals, ' )
            
                    for val in raw_values:
                        self.logfile.write( '{0}, '.format( val ) )

                    self.last_packet_num = packet_num
                    self.tick_job = self.root.after( self.args.tick, self.tick )        
                    return

            self.compute_collapsed_values(pad_num, raw_values)
            self.compute_total_mag(pad_num, raw_values)
            self.compute_pos(pad_num, raw_values)
            self.compute_z_corrected_val(pad_num, raw_values)

            self.compute_finger_down(pad_num, raw_values)
            

            ## Drawing
            self.draw_grid(pad_num, raw_values)
            self.draw_collapsed_xy(pad_num, raw_values)
            self.draw_pos_dot(pad_num, raw_values)
            self.draw_line_graphs(pad_num, raw_values)
            self.draw_z_history_text(pad_num, raw_values)
            self.draw_z_history_graph(pad_num, raw_values)

                                      
        self.tick_job = self.root.after( self.args.tick, self.tick )        

def key_cb( event ):
    if event.char == 'a':
        cntrlr_mgr.capsense_calibrate_trackpad(0)
        cntrlr_mgr.capsense_calibrate_trackpad(1)
    elif event.char == 'l':
        vioos.set_logging_state(not vioos.get_logging_state())
    elif event.char == 'r':
        cntrlr_mgr.restart()
    elif event.char == 's':
        vioos.trackpad = 1 - vioos.trackpad
        cntrlr_mgr.trackpad_set_raw_data_mode(1 << vioos.trackpad )
    elif event.char == 'q':
        root.destroy()

def connect_cb(hid_dev_mgr):
    global logger
    logger.info("CONNECT")

    # set debug usb mode
    cntrlr_mgr.set_setting(6, 0)
    # Turn off IMU
    cntrlr_mgr.set_imu_mode(0)

    #Lower Frame rate
    cntrlr_mgr.sys_set_framerate(8)

    # Enable raw data for Rushmore (only right trackpad)
    cntrlr_mgr.trackpad_set_raw_data_mode(4)

    # Enable status messages
    cntrlr_mgr.set_setting(49, 2)	

# Device endpoint filter lists (Name, (VID, PID))
ep_lists = (
    (
        'Wired',
        (
            (0x28DE, 0x1102),	#d0g
            (0x28DE, 0x1201),	#headcrab
            (0x28DE, 0x1203),	#Win: Steampal Neptune
            (0x28DE, 0x1204),	#Win: Steampal D21 / Jupiter
            (0x28DE, 0x1205),	#Win: Steampal D21 / Jupiter2
        )
    ),
    (
        'Wireless',
        (
            (0x28DE, 0x1142),
            (0x28DE, 0x1201), #headcrab
        )
    ),
)

##########################################################################################################
## MAIN ENTRY
##########################################################################################################
parser = argparse.ArgumentParser()
args = parser.parse_args()

##########################################################################################################
## LOGGER SETUP
##########################################################################################################
logger=logging.getLogger('VIZ')
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('VIZ.log')
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)

# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

root = Tk.Tk()
root.wm_title("Valve Test")

parser = argparse.ArgumentParser(description='Valve Controller Trackpad Visualizer')
parser.add_argument('-m', '--mode', type=int, default=0,
                    help='The mode to execute (Default: 0)')
parser.add_argument('-t', '--tick', type=int, default=8,
                    help='The tick rate in ms (Default: 1)')
parser.add_argument('-v', '--verbose', action='store_true', default=False,
                    help='Log debug information to console')
args = parser.parse_args()

cntrlr_mgr = ControllerInterface( ep_lists[0][1], connect_cb)
logger.info("Awaiting connection")
top_frame = Tk.Frame( root, width=canvas_size*2, height=canvas_size*4, bg = 'black' )
top_frame.pack_propagate(0)
top_frame.pack( side = Tk.TOP )

vioos = TrackpadVis( top_frame, cntrlr_mgr, args )

root.bind("<Key>", key_cb)
Tk.mainloop()

cntrlr_mgr.shutdown()
