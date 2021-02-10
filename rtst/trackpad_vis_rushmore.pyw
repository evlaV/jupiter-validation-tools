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

canvas_size = 250

# map val to a color string in the '#FFFFFFFF' format. val should be [0-32767]
def get_color( val ):
    max = 2 * 32767.0

    if val < 0:
        val = 0
    
    val = float( val )
    if val > max:
        val = max      
    
    red = val / max
    red *= 255
    green = red
    blue = min(red + 32, 255)

    return  '#{0:02x}{1:02x}{2:02x}'.format( int(red), int(green), int(blue), width=2 )

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
        self.middle_out = 4 #eights

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
        
        self.vals_x_text = [[0 for x in range(self.num_x)] for y in range(self.num_pads)] 
        self.vals_y_text = [[0 for x in range(self.num_x)] for y in range(self.num_pads)] 
        
        self.pos_history = []
        self.pos_history.append( deque() )
        self.pos_history.append( deque() )
      
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
        self.sensor_vals_canvas = {}
        self.canvas = {}
        self.logfile = None

        self.last_x_vals = [0, 0, 0, 0, 0, 0, 0, 0]
        self.last_y_vals = [0, 0, 0, 0, 0, 0, 0, 0]

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
        #############################################################################################################################
        ## Draw left and right sides
        #############################################################################################################################
        for pad_num in range(self.num_pads):
            x_base = self.slice_width_x*2
            y_base = 10
    
            # This divisor sets the scale.  Go figure.
            self.graph_height = 32767
            self.graph_cavnas_size = self.canvas_size
            
            self.canvas[pad_num] = Tk.Canvas( self.grid_frame,
                                              height=self.graph_cavnas_size+40,
                                              width=self.graph_cavnas_size+15,
                                              bg='#171737', bd=-2,
                                              highlightthickness=0  )
            canvas = self.canvas[pad_num]
            canvas.grid( row=0, column=pad_num, padx=5, pady=5 )
        
            #############################################################################################################################
            ## X shaded squares
            #############################################################################################################################
            for x in range(self.num_x):
                self.x_boxes[pad_num].append( canvas.create_rectangle( x_base, y_base, x_base+self.slice_width_x, y_base+self.slice_width_y, fill='white', outline='#707090' ) ) 
                x_base += self.slice_width_x

            x_base = 10
            y_base = self.slice_width_y*2
        
            box_size = self.total_width / self.num_y
            
            #############################################################################################################################
            ## Y shaded squares
            #############################################################################################################################
            for y in range(self.num_y):
                self.y_boxes[pad_num].append( canvas.create_rectangle( x_base, y_base, x_base+self.slice_width_x, y_base+self.slice_width_y, fill='white', outline='#707090' ) )
                
                y_base += self.slice_width_y
                
            # Draw the sums of the rows and colums as a grid
            x_base = self.slice_width_x*2
            y_base = self.slice_width_y*2
            
            #############################################################################################################################
            ## X by Y grid values
            #############################################################################################################################
            for x in range(self.num_x):
                for y in range(self.num_y):
                    self.grid_boxes[pad_num].append( canvas.create_rectangle( x_base, y_base, x_base+self.slice_width_x, y_base+self.slice_width_y, fill='white', outline='#707090' ) )
                
                    y_base += self.slice_width_y
                    
                x_base += self.slice_width_x
                y_base = self.slice_width_y*2

            x_base = 2*self.slice_width_x
            y_base = 15 + self.slice_width_y*10

            #############################################################################################################################
            ## Lines and fill polygons for X, Y values
            #############################################################################################################################            
            #draw a line graph of each axis
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


            #############################################################################################################################
            ## NEXT
            #############################################################################################################################

            self.sensor_vals_canvas[pad_num] = Tk.Canvas(self.grid_frame,
                                                     height=self.graph_cavnas_size,
                                                     width=self.graph_cavnas_size,
                                                     bg='#171737', bd=-2,
                                                     highlightthickness=0)
            vals_canvas = self.sensor_vals_canvas[pad_num]
            vals_canvas.grid( row=2, column=pad_num, padx=5, pady=5 )
            
            vals_canvas.create_rectangle( 0, 0, self.canvas_size, self.canvas_size, fill='#202040' )

            x_delta = 20
            y_delta = 20
            for i in range(self.num_x):
                vals_canvas.create_text( 60 + i * x_delta, 20, justify=Tk.LEFT, text='X{}'.format(i), fill='#707090')
                self.vals_x_text[pad_num][i] = vals_canvas.create_text( 60 + i*x_delta, 35, justify=Tk.LEFT, text="00", fill='#707090') 

                vals_canvas.create_text( 30, 60 + i * y_delta, justify=Tk.LEFT, text='Y{}'.format(i), fill='#707090')
                self.vals_y_text[pad_num][i] = vals_canvas.create_text( 50, 60 + i*y_delta, justify=Tk.LEFT, text="00", fill='#707090') 

    def weighted_average(self, vals):
        div = np.sum(vals)*(len(vals) - 1)
        if div == 0:
            return 0.0
        
        return sum([vals[i]*i for i in range(len(vals))]) / div

    def draw_grid(self, pad_num, raw_x_values, raw_y_values):
        for i in range(len(self.grid_boxes[pad_num])):
            box = self.grid_boxes[pad_num][i]
          
            val = raw_x_values[int( i/ self.rank)] * raw_y_values[i % self.rank]
            self.canvas[pad_num].itemconfig(box, fill=get_color(val*40))

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

    def compute_pos(self, pad_num):

        x_val = self.rescale_value(self.weighted_average(self.x_vals), .01, .99)
        y_val = self.rescale_value(self.weighted_average(self.y_vals), .01, .99)
        
        self.x_pos = 2.0*(x_val - 0.5)*32767.0
        self.y_pos = 2.0*(y_val - 0.5)*32767.0
        
        self.raw_z_val = np.sum(self.x_vals) + np.sum(self.y_vals)

        self.radius = math.sqrt(self.x_pos**2 + self.y_pos**2)

  #      self.log_trackpads();

    def draw_collapsed_xy(self, pad_num):
        # draw the collapsed X and Y boxes in the top graph
        for i in range(self.num_x):
            box = self.x_boxes[pad_num][i]
            self.canvas[pad_num].itemconfig(box, fill=get_color(self.x_vals[i]*8))
        for i in range( self.num_y ):
            box = self.y_boxes[pad_num][i]
            self.canvas[pad_num].itemconfig(box, fill=get_color(self.y_vals[i]*8))

    def draw_pos_dot(self, pad_num):
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

    def get_index_position(self, index, num_vals):
        return (float(index)/num_vals)*self.graph_cavnas_size #+ (self.graph_cavnas_size/num_vals)/2

    def calc_index(self, pos, num_vals):
        return math.floor((pos/self.graph_cavnas_size)*num_vals)

    def draw_line_graphs(self, pad_num, x_vals, y_vals):
        # Zero values below threshold
        x_vals = x_vals*(x_vals >= 0)
        y_vals = y_vals*(y_vals >= 0)
        
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

    def compute_z_corrected_val(self, pad_num):

        total_mag_thresh = 1000

        if self.total_mag < total_mag_thresh:
            self.corrected_z_val = -10000
        else:
            self.corrected_z_val = self.total_mag


            #curve_pts = [ 1000, 1000, 950, 825, 550, 175 ]
            #max_total_mag = 20000
            #correction_vals = map( lambda x: max_total_mag*(x/1000.0), curve_pts )

            #num_steps = 5
            #max_radius = 32767
            #radius_per_step = float( max_radius/num_steps )

            #for i in range(num_steps):
            #    if (i+1) * radius_per_step > self.radius:
            #        break

            ##print "slice: ", radius / radius_per_step, " percent: ", total_mag/float(max_total_mag)

            ## lerp the correction
            #t = (self.radius-(i*radius_per_step)) / radius_per_step

            #correction = correction_vals[i] + t*(correction_vals[i+1] - correction_vals[i])

            #self.corrected_z_val = self.total_mag # - correction

            #print "radius: ", self.radius, "correction:", correction, "total_mag:", self.total_mag

        # keep a history of the last few z values so we can graph them 
        self.z_val_history[pad_num].append(self.corrected_z_val)
        if len(self.z_val_history[pad_num]) > self.z_val_line_count:
            self.z_val_history[pad_num].popleft()

    def compute_finger_down(self, pad_num, raw_x_values, raw_y_values):

        if np.sum(raw_x_values) + np.sum(raw_y_values) > 60:
            self.finger_down[pad_num] = True
        else:
            self.finger_down[pad_num] = False
        return

    def compute_total_mag(self, pad_num):
        self.total_mag = np.sum(self.x_vals) + np.sum(self.y_vals)

    def draw_vals_text(self, pad_num, raw_x_values, raw_y_values):
        for i in range( self.num_x ):
            self.sensor_vals_canvas[pad_num].itemconfig(self.vals_x_text[pad_num][i], text = int(raw_x_values[i]))
            self.sensor_vals_canvas[pad_num].itemconfig(self.vals_y_text[pad_num][i], text = int(raw_y_values[i]))

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

                if not ('pad_raw_0') in device_data:
                    continue

                # Values .
                raw_x_values = np.array( [device_data['pad_raw_%d' % (i)] for i in range(0,  self.rank, 1)],  dtype=np.float32)
                raw_y_values = np.array( [device_data['pad_raw_%d' % (i)] for i in range(self.rank, 2 *self.rank, 1)],  dtype=np.float32)

                if self.logfile:
                    packet_num = device_data['last_packet_num']
                    if packet_num != self.last_packet_num:
    #                   self.logfile.write( 'raw_vals, ' )
                        self.logfile.write( '{0}, '.format(device_data['last_packet_num']) )
                        for val in raw_x_values:
                            self.logfile.write( '{0}, '.format( val ) )  
                        for val in raw_y_values:
                            self.logfile.write( '{0}, '.format( val ) )

                        self.logfile.write('\n')
                    self.last_packet_num = packet_num
                    self.tick_job = self.root.after( self.args.tick, self.tick )        
                    return

                avg_x = np.sum(raw_x_values) / self.num_x
                avg_y = np.sum(raw_y_values) / self.num_y

                raw_x_values = np.subtract(raw_x_values, avg_x * self.middle_out / 8 )
                raw_y_values = np.subtract(raw_y_values, avg_y * self.middle_out / 8 )

                centroid_threshold = 11 

                raw_x_values[raw_x_values < centroid_threshold] = 0
                raw_y_values[raw_y_values < centroid_threshold] = 0

                for i in range(0, self.rank, 1):
                    raw_x_values[i] = ((self.rank - 1) * self.last_x_vals[i] + raw_x_values[i]) / self.rank
                    raw_y_values[i] = ((self.rank - 1) * self.last_y_vals[i] + raw_y_values[i]) / self.rank

                    self.last_x_vals[i] = raw_x_values[i];
                    self.last_y_vals[i] = raw_y_values[i];


                self.x_vals = raw_x_values * 256
                self.y_vals = raw_y_values * 256

   
                self.compute_total_mag(pad_num)
                self.compute_pos(pad_num)
                self.compute_finger_down(pad_num, raw_x_values, raw_y_values)
            # Drawing
                self.draw_grid(pad_num, raw_x_values, raw_y_values)
                self.draw_collapsed_xy(pad_num)
                self.draw_pos_dot(pad_num)
                self.draw_line_graphs(pad_num, self.x_vals, self.y_vals)


                self.draw_vals_text(pad_num, raw_x_values, raw_y_values)
            #   if self.logfile:
            #       self.logfile.write( '\n' )
                                        
        self.tick_job = self.root.after( self.args.tick, self.tick )        

def key_cb( event ):
    if event.char == 'm':
        vioos.args.mode += 1
        if vioos.args.mode > 2:
            vioos.args.mode = 0

        cntrlr_mgr.set_setting( 6, 4 + vioos.args.mode )

        for l in vioos.prev_x_values:
            del l[:]
        for l in vioos.prev_y_values:
            del l[:]
        for l in vioos.prev_raw_values:
            del l[:]
    elif event.char == 'a':
        cntrlr_mgr.capsense_calibrate_trackpad(0)
        cntrlr_mgr.capsense_calibrate_trackpad(1)
    elif event.char == 'o':
        vioos.middle_out = vioos.middle_out + 1
        if vioos.middle_out >= 8:
            vioos.middle_out = 0
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
    cntrlr_mgr.set_imu_mode(1)

    #Lower Frame rate
    cntrlr_mgr.sys_set_framerate(12)

    # Enable right trackpad data
    cntrlr_mgr.trackpad_set_raw_data_mode(2)

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
parser.add_argument('-t', '--tick', type=int, default=1,
                    help='The tick rate in ms (Default: 1)')
parser.add_argument('-v', '--verbose', action='store_true', default=False,
                    help='Log debug information to console')
args = parser.parse_args()

def SetDebugMode( cntrlr_mgr ):
    global args
    
    # set debug usb mode
    cntrlr_mgr.set_setting( 6, 6 )

    # remove all the default mappings
    cntrlr_mgr.clear_mappings()

    # set both pads to 'none' mode
    cntrlr_mgr.set_pad_mode( 'left', 7 )

    # set both pads to 'none' mode
    cntrlr_mgr.set_pad_mode( 'right', 7 )

cntrlr_mgr = ControllerInterface( ep_lists[0][1], connect_cb)

top_frame = Tk.Frame( root, width=canvas_size*2, height=canvas_size*4, bg = 'black' )
top_frame.pack_propagate(0)
top_frame.pack( side = Tk.TOP )

vioos = TrackpadVis( top_frame, cntrlr_mgr, args )

root.bind("<Key>", key_cb)

Tk.mainloop()

cntrlr_mgr.shutdown()
