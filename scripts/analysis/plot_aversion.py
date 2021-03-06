import json
import math
import os.path
import datetime
import collections
import cPickle
import argparse

import numpy as np
import pandas as pd
import shapely.geometry as sg
import matplotlib.pyplot as plt
import matplotlib.patches

import roslib; roslib.load_manifest('flymad')
import flymad.madplot as madplot

def prepare_data(arena, path, smoothstr, smooth):

    dat = json.load(open(path))

    fly_data = dat['data']
    bpath = dat.get('_base',os.path.abspath(os.path.dirname(path)))

    pooled_on = {k:[] for k in "axbhwq"}
    pooled_off = {k:[] for k in "axbhwq"}
    pooled_lon = {k:[] for k in "axbhwq"}

    for exp in fly_data:

        geom, dfs = madplot.load_bagfile(
                                    madplot.get_path(path,dat,exp["bag"]),
                                    arena,
                                    smooth=smooth)
        l_df = dfs["targeted"]
        t_df = dfs["tracked"]
        h_df = dfs["ttm"]

        #find when the laser was on
        l_on = l_df[l_df['laser_power'] > 0]
        #time of first laser on
        l_on0 = l_df.index[0] + datetime.timedelta(seconds=30)

        #t_off = t_df.head(3000)
        #t_on = t_df.tail(3000)

        #fig = plt.figure()
        #ax = fig.gca()
        #t_df.plot(ax=ax)
        #fig.savefig("%s_%s.png" % (exp["bag"],exp["type"]), bbox_inches='tight')

        #the laser was off at the start and on at the end
        #tracking data when the laser was on 
        t_on = t_df[l_on0:]
        #tracking data when the laser was off
        t_off = t_df[:l_on0]

        pooled_on[exp["type"]].append(t_on)
        pooled_off[exp["type"]].append(t_off)
        pooled_lon[exp["type"]].append(l_on)

    cPickle.dump(pooled_on, open(os.path.join(bpath,'pooled_on_%s_%s.pkl' % (arena.unit,smoothstr)),'wb'), -1)
    cPickle.dump(pooled_off, open(os.path.join(bpath,'pooled_off_%s_%s.pkl' % (arena.unit,smoothstr)),'wb'), -1)
    cPickle.dump(pooled_lon, open(os.path.join(bpath,'pooled_lon_%s_%s.pkl' % (arena.unit,smoothstr)),'wb'), -1)

    return pooled_on, pooled_off, pooled_lon

def load_data(arena, path, smoothstr):
    dat = json.load(open(path))
    bpath = dat.get('_base',os.path.dirname(path))

    return (
        cPickle.load(open(os.path.join(bpath,'pooled_on_%s_%s.pkl' % (arena.unit,smoothstr)),'rb')),
        cPickle.load(open(os.path.join(bpath,'pooled_off_%s_%s.pkl' % (arena.unit,smoothstr)),'rb')),
        cPickle.load(open(os.path.join(bpath,'pooled_lon_%s_%s.pkl' % (arena.unit,smoothstr)),'rb'))
    )

def plot_data(arena, path, smoothstr, data):

    pooled_on, pooled_off, pooled_lon = data

    on_means = []
    off_means = []
    on_stds = []
    off_stds = []
    on_sems = []
    off_sems = []

    label_map = {'a':'Antenna','b':'Body','h':'Head','x':'Miss','w':'Non-TTM'}
    labels = []

    #keep the same order
    for k in [t for t in 'ahbxw' if len(pooled_on.get(t,[]))]:
        print "-- AVERSION N --------------\n\t%s = %s" % (k,len(pooled_on[k]))

        on = pd.concat(pooled_on[k])
        off = pd.concat(pooled_off[k])

        _on_std = on['v'].std()
        _off_std = off['v'].std()

        on_means.append( on['v'].mean() )
        off_means.append( off['v'].mean() )
        on_stds.append( _on_std )
        off_stds.append( _off_std )
        on_sems.append( _on_std / np.sqrt(on['v'].count()) )
        off_sems.append( _off_std / np.sqrt(off['v'].count()) )

        labels.append( label_map[k] )

    N = len(on_means)
    ind = np.arange(N)  # the x locations for the groups
    width = 0.35        # the width of the bars

    fig = plt.figure("Aversion %s" % smoothstr)
    ax = fig.add_subplot(1,1,1)

    rects1 = ax.bar(ind, on_means, width, color='b', yerr=on_sems, ecolor='k')
    rects2 = ax.bar(ind+width, off_means, width, color='r', yerr=off_sems, ecolor='k')

    ax.set_ylabel('Speed (%s/s) +/- SEM' % arena.unit)
    ax.set_xticks(ind+width)
    ax.set_xticklabels( labels )
    ax.spines['bottom'].set_color('none') # don't draw bottom spine

    ax.legend( (rects1[0], rects2[0]), ('Laser On', 'Laser Off'), loc='upper right' )

    ax.set_title("Aversion %s" % smoothstr)

    fig.savefig('aversion_%s.svg' % smoothstr, bbox_inches='tight')
    fig.savefig('aversion_%s.png' % smoothstr, bbox_inches='tight')
    print "wrote",'aversion_%s.png' % smoothstr

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs=1, help='path to json files')
    parser.add_argument('--only-plot', action='store_true', default=False)
    parser.add_argument('--show', action='store_true', default=False)
    parser.add_argument('--no-smooth', action='store_false', dest='smooth', default=True)

    args = parser.parse_args()
    path = args.path[0]

    smoothstr = '%s' % {True:'smooth',False:'nosmooth'}[args.smooth]

    arena = madplot.Arena('mm')

    if args.only_plot:
        data = load_data(arena, path, smoothstr)
    else:
        data = prepare_data(arena, path, smoothstr, args.smooth)

    plot_data(arena, path, smoothstr, data)

    if args.show:
        plt.show()

