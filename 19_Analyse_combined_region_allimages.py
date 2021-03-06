# -*- coding: utf-8 -*-
"""
Created on Tue Jul 31 09:01:51 2018

@author: z3439910
"""

import numpy as np
import xarray as xr
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from decimal import Decimal
import glob,os
import time
from matplotlib import colors
import numba
from numba import vectorize, float64, int16, guvectorize, jit
import pickle
import h5py



WORKPLACE = r"C:\Users\z3439910\Documents\Kien\1_Projects\2_Msc\1_E1\5_GIS_project\IR_Dorina"
IRDIR = WORKPLACE + r"\IRimages_remap_region"
SAVDIR = WORKPLACE + r"\Figures\180803_3flags_allimages"
DTB = WORKPLACE + r"\Python_codes\Pickle_database"
os.chdir(IRDIR)


#%% Best track
# get TC estimated centers
Btracks = xr.open_dataset(WORKPLACE+"\\"+"2013204N11340.ibtracs.v03r10.nc")

# extract variables into arrays
Btime = Btracks['time'].values
Byear = pd.to_datetime(Btime).year
Bmonth = pd.to_datetime(Btime).month
Bday = pd.to_datetime(Btime).day
Bhour = pd.to_datetime(Btime).hour
Blat = Btracks['lat_for_mapping'].values
Blon = Btracks['lon_for_mapping'].values

# interpolate best track lat long to 0.5-hour intervals
df = pd.DataFrame({'time':Btime,'lat':Blat,'lon':Blon})
df = df.set_index('time')
df_reindexed = df.reindex(pd.date_range(start=Btime[0],end=Btime[len(Btime)-1],freq='0.5H'))
df_reindexed = df_reindexed.interpolate(method='time')
df_reindexed.index.name = 'time'
df_reindexed.reset_index(inplace = True)

#%% Calculate distance
def calcdistance_km(latA,lonA,latB,lonB):
    dist = np.sqrt(np.square(latA-latB)+np.square(lonA-lonB))*111
    return np.int(dist)
#    return True
#%% Create a HDF5 file
Hfile_label = h5py.File('TCDORIAN_label.h5','w')
#Hfile_label.close()

#% Generate label matrices in the HDF5 file, then close it
Hfile_imag = h5py.File('TCDORIAN.h5','r')
dim_lat = np.shape(Hfile_imag['latitude'])[0]
dim_lon = np.shape(Hfile_imag['longitude'])[0]
dim_time = np.shape(Hfile_imag['time'])[0]

Hfile_label = h5py.File('TCDORIAN_label.h5','r+')
Hfile_label.create_dataset('label_TC', shape = (dim_lat,dim_lon,dim_time),chunks=True)
Hfile_label.create_dataset('label_nonTC', shape = (dim_lat,dim_lon,dim_time),chunks=True)
Hfile_label.create_dataset('label_BG', shape = (dim_lat,dim_lon,dim_time),chunks=True)
#%
Hfile_imag.close()
Hfile_label.close()

#%% OPEN HDF5 FILES
Hfile_imag = h5py.File('TCDORIAN.h5','r')
Hfile_label = h5py.File('TCDORIAN_label.h5','r+')  
C_label_TC = Hfile_label['label_TC']
C_label_BG = Hfile_label['label_BG']
C_label_nonTC = Hfile_label['label_nonTC']

#%% CLOSE HDF5 FILES
Hfile_imag.close()
Hfile_label.close()
          
#%% Run full algorithm for the whole first image
#%%  core detection         
##%% load the scene
#Clat = Hfile_imag['latitude'][:]
#Clon = Hfile_imag['longitude'][:]
#imag_px_w = np.shape(Clon)[0]
#imag_px_h = np.shape(Clat)[0]
#imag_res = 4 #km
#
## load all file with '2013*'
#keys = Hfile_imag.keys()
#files = [key for key in keys if key.startswith('2013')]
#
## first image
#C_i = 0
#C_label_TC[:,:,C_i] = np.zeros([dim_lat,dim_lon])
#filename = files[C_i]
#C_btemp = Hfile_imag[filename][:]
#C_flag = C_label_TC[:,:,C_i][:]
#
## load best track centre
#BT_cen = df_reindexed.iloc[C_i]
#BT_lat = BT_cen.lat
#BT_lon = BT_cen.lon
#
## define search boundry
#S_bound_km = 300 #km
#S_bound_deg = S_bound_km/111 #convert km to deg
#S_no_px = np.round(S_bound_km/imag_res)
#
## 
#box_i_w = [i_w for i_w,x_w in enumerate(Clon) if abs(BT_lon-x_w) < S_bound_deg]
#box_i_h = [i_h for i_h,x_h in enumerate(Clat) if abs(BT_lat-x_h) < S_bound_deg]
#
##
#for i_w in box_i_w:
#    for i_h in box_i_h:
#        t_lat = Clat[i_h]
#        t_lon = Clon[i_w]
#        t_btemp = C_btemp[i_h,i_w]
#        if (calcdistance_km(BT_lat, BT_lon, t_lat, t_lon) < S_bound_km) and (np.int(t_btemp)) < 200:
#            C_flag[i_h,i_w] = 1
#            print ('found at ' + str(i_w) + ' and ' + str(i_h))
#%% spreading the core
Clat = Hfile_imag['latitude'][:]
Clon = Hfile_imag['longitude'][:]
imag_px_w = np.shape(Clon)[0]
imag_px_h = np.shape(Clat)[0]
imag_res = 4 #km

# load all file with '2013*'
keys = Hfile_imag.keys()
files = [key for key in keys if key.startswith('2013')]

# define some variables
Tb_thres = 280
start_time_overall = time.time()
# define search boundry
S_bound_km = 300 #km
S_bound_deg = S_bound_km/111 #convert km to deg
S_no_px = np.round(S_bound_km/imag_res)

S_bound_tot_km = 1110 #km
S_bound_tot_deg = S_bound_tot_km/111 #convert km to deg
S_no_size_px = np.round(S_bound_tot_km/imag_res)

#%% start sprading algorithm

C_min_prev_mask_val = np.zeros(dim_time) #store all cores taken from previous mask

#C_i = 1
for C_i in range(0,dim_time):
    C_label_TC[:,:,C_i] = np.zeros([dim_lat,dim_lon])
    filename = files[C_i]
    C_btemp = Hfile_imag[filename][:]
    C_flag = C_label_TC[:,:,C_i][:]
    
    # load best track centre
    BT_cen = df_reindexed.iloc[C_i]
    BT_lat = BT_cen.lat
    BT_lon = BT_cen.lon
    
    if C_i == 0:    
        # 
        box_i_w = [i_w for i_w,x_w in enumerate(Clon) if abs(BT_lon-x_w) < S_bound_deg]
        box_i_h = [i_h for i_h,x_h in enumerate(Clat) if abs(BT_lat-x_h) < S_bound_deg]
        
        #
        for i_w in box_i_w:
            for i_h in box_i_h:
                t_lat = Clat[i_h]
                t_lon = Clon[i_w]
                t_btemp = C_btemp[i_h,i_w]
                if (calcdistance_km(BT_lat, BT_lon, t_lat, t_lon) < S_bound_km) and (np.int(t_btemp)) < 200:
                    C_flag[i_h,i_w] = 1
                    print ('found at ' + str(i_w) + ' and ' + str(i_h))
    else:
        C_flag_prev = C_label_TC[:,:,C_i-1][:]
        idx_prv = np.where(C_flag_prev == 2)
        idx_prv_y = idx_prv[0]
        idx_prv_x = idx_prv[1]
        min_prv_mask_val = 9999
        min_prv_mask_idx = 0
        min_prv_mask_idy = 0
        for i in range(0,np.shape(idx_prv)[1]-1):
            if (min_prv_mask_val > C_btemp[idx_prv_y[i],idx_prv_x[i]]) and (calcdistance_km(BT_lat, BT_lon, Clat[idx_prv_y[i]], Clon[idx_prv_x[i]])<200):
                min_prv_mask_val  = C_btemp[idx_prv_y[i],idx_prv_x[i]]
                min_prv_mask_idx = idx_prv_x[i]
                min_prv_mask_idy = idx_prv_y[i]
    
        C_min_prev_mask_val[C_i] =  min_prv_mask_val
        C_flag[min_prv_mask_idy,min_prv_mask_idx] = 1
        C_flag[min_prv_mask_idy,min_prv_mask_idx+1] = 1
        C_flag[min_prv_mask_idy,min_prv_mask_idx-1] = 1
        C_flag[min_prv_mask_idy+1,min_prv_mask_idx] = 1
        C_flag[min_prv_mask_idy-1,min_prv_mask_idx] = 1
        C_flag[min_prv_mask_idy,min_prv_mask_idx+2] = 1
        C_flag[min_prv_mask_idy,min_prv_mask_idx-2] = 1
        C_flag[min_prv_mask_idy+2,min_prv_mask_idx] = 1
        C_flag[min_prv_mask_idy-2,min_prv_mask_idx] = 1
        print("Previous mask min at value " + str(min_prv_mask_val) + " K")
    
    stop_flag = 0
    iteration = 1
    while stop_flag == 0:
        start_time_itr = time.time()
        stop_flag = 1
        idx_flag = np.where(C_flag==1)
        
        for i in range(0,np.shape(idx_flag)[1]-1):
                idx_h = idx_flag[0][i]
                idx_w = idx_flag[1][i]
                C_flag[idx_h,idx_w] = 2
                for jy in range (0,5):
                    for jx in range (0,5):
                        idx_hj = idx_h + jy
                        idx_wj = idx_w + jx
                        if (calcdistance_km(BT_lat, BT_lon, Clat[idx_h], Clon[idx_w]) < S_bound_tot_km) and (C_btemp[idx_hj,idx_wj]<=Tb_thres) and (C_flag[idx_hj,idx_wj]==0):
                                C_flag[idx_hj,idx_wj]=1
                                stop_flag = 0
                        
                        idx_hj = idx_h + jy
                        idx_wj = idx_w - jx
                        if (calcdistance_km(BT_lat, BT_lon, Clat[idx_h], Clon[idx_w]) < S_bound_tot_km) and (C_btemp[idx_hj,idx_wj]<=Tb_thres) and (C_flag[idx_hj,idx_wj]==0):
                                C_flag[idx_hj,idx_wj]=1
                                stop_flag = 0
                        
                        idx_hj = idx_h - jy
                        idx_wj = idx_w + jx
                        if (calcdistance_km(BT_lat, BT_lon, Clat[idx_h], Clon[idx_w]) < S_bound_tot_km) and (C_btemp[idx_hj,idx_wj]<=Tb_thres) and (C_flag[idx_hj,idx_wj]==0):
                                C_flag[idx_hj,idx_wj]=1
                                stop_flag = 0      
                        
                        idx_hj = idx_h - jy
                        idx_wj = idx_w - jx
                        if (calcdistance_km(BT_lat, BT_lon, Clat[idx_h], Clon[idx_w]) < S_bound_tot_km) and (C_btemp[idx_hj,idx_wj]<=Tb_thres) and (C_flag[idx_hj,idx_wj]==0):
                                C_flag[idx_hj,idx_wj]=1
                                stop_flag = 0
                        
        elapsed_time_itr = time.time() - start_time_itr
        print ('Layer ' + str(C_i) + ' Interation ' + str(iteration) + ' done in ' +  time.strftime("%H:%M:%S", time.gmtime(elapsed_time_itr)))
        iteration = iteration + 1
        
    
    
    C_label_TC[:,:,C_i] = C_flag    

#%
    C_flag_BG = np.where(C_btemp<280,0,C_btemp)
    C_flag_BG = np.where(C_flag_BG>0,4,C_flag_BG)
    C_flag_nonTC = np.zeros([dim_lat,dim_lon])
    C_flag_nonTC = np.where(C_flag_BG < 4,3,C_flag_nonTC)
    C_flag_nonTC = np.where(C_flag >0,0,C_flag_nonTC)
    #im2 = plt.imshow(a, cmap='Greys',origin='lower',alpha=0.4)
    
    C_label_TC[:,:,C_i] = C_flag #flag=2
    C_label_nonTC[:,:,C_i] = C_flag_nonTC #flag=3
    C_label_BG[:,:,C_i] = C_flag_BG #flag=4

#% Plot image
#flag_pos = np.where(c_flag==1)
    C_mask_TC = np.where(C_flag == 0, np.NaN , C_flag)
    C_mask_nonTC = np.where(C_flag_nonTC == 0, np.NaN , C_flag_nonTC)
    C_mask_BG = np.where(C_flag_BG == 0, np.NaN , C_flag_BG)
    #mask_pos = np.where(c_mask>0)
    #c_Tb = Cdataset.Tb[C_i,:,:].values
    
    #% plot IR image and the center point
    fig = plt.figure()
    lat_max = np.round(np.max(Clat),1)
    lat_min = np.round(np.min(Clat),1)
    lon_max = np.round(np.max(Clon),1)
    lon_min = np.round(np.min(Clon),1)
    
    im = plt.imshow(C_btemp, extent = (lon_min, lon_max, lat_min, lat_max),  cmap='Greys',origin='lower')
    
    im2 = plt.imshow(C_mask_TC, extent = (lon_min, lon_max, lat_min, lat_max), cmap=colors.ListedColormap(['yellow']),origin='lower',alpha=0.3)
    im3 = plt.imshow(C_mask_nonTC, extent = (lon_min, lon_max, lat_min, lat_max), cmap=colors.ListedColormap(['red']),origin='lower',alpha=0.3)
    im4 = plt.imshow(C_mask_BG, extent = (lon_min, lon_max, lat_min, lat_max), cmap=colors.ListedColormap(['blue']),origin='lower',alpha=0.3)
#    cb = fig.colorbar(im, orientation='vertical')
#    cb.set_label('Brightness Temperature(K)')
    ax = plt.gca()
    ax.set_title('TC DORIAN    '+files[C_i].replace(".nc",""))
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    
    # BT centre
    plt.plot(BT_lon,BT_lat,'or', markersize = 2)  
    # centre of the spreading core
    if C_i>0:
        plt.plot(Clon[min_prv_mask_idx],Clat[min_prv_mask_idy],'co', markersize = 2)
    fig.savefig(SAVDIR + "\\" + filename +".png",dpi=1000)
    plt.close()
#    plt.plot(BT_lon,BT_lat,'or', markersize = 2)            

    elapsed_time_overall = time.time() - start_time_overall
    print ('Cloud extraction for all done in ' +  time.strftime("%H:%M:%S", time.gmtime(elapsed_time_overall)))

#% CLOSE HDF5 FILES
Hfile_imag.close()
Hfile_label.close()
#%%
#################################################################################################
##%%           TEST SITE