#!/usr/bin/env python
##
# Copyright 2010-2015 Ghent University
#
# This file is part of mympingpong,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.ugent.be/hpcugent/mympingpong
#
# mympingpong is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# mympingpong is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with mympingpong. If not, see <http://www.gnu.org/licenses/>.
##

"""
@author: Stijn De Weirdt (Ghent University)

Generate the plots
"""

import sys,os,re
from vsc.mympingpong.log import initLog,setdebugloglevel
from vsc.mympingpong.mympi import mympi

class pingponganalysis:
    def __init__(self):
        self.log=initLog(name=self.__class__.__name__)

        try:
            global mp
            import matplotlib as mp
        except Exception, err:
            self.log.error("Failed to load matplotlib: %s"%err)

        try:
            global n
            import numpy as n
        except Exception, err:
            self.log.error("Failed to load numpy: %s"%err)

        self.data=None
        self.count=None
        self.fail=None
        self.nodemap=None

        ## use multiplication of 10e6 (ie microsec)
        self.scaling=1e6

        self.metatags=['totalranks','msgsize','nr_tests','iter',
                       'uniquenodes','pairmode','ppmode','ppgroup','ppnumber']
        self.meta=None

        self.cmap=None

    def collect(self,ppdata):
        """
        Data in pingpong format
        - list of dictionaries
        - each disctionay with own rank/hostname
        -- pairs : coordinates
        -- data : data
        """
        self.log.debug("collect ppdata %s"%ppdata)

        shortname=True
        
        meta={}
        for m in self.metatags:
            try:
                meta[m]=ppdata[0][m]
            except:
                meta[m]='UNKNOWN'

        meta['domain']='.'.join(ppdata[0]['name'].split('.')[1:])
        size=meta['totalranks']

        data=n.zeros((size,size),float)
        count=n.zeros((size,size),float)
        fail=n.zeros((size,1),float)
        nodemap=['']*size
        for el in ppdata:
            if shortname:
                nodemap[el['myrank']]=el['name'].split('.')[0]
            else:
                nodemap[el['myrank']]=el['name']
            for i in xrange(el['nr_tests']):
                ind=el['pairs'][i]
                if (-1 in ind) or (-2 in ind):
                    #self.log.debug("No valid data for pair %s"%ind)
                    fail[ind[n.where(ind > -1)[0][0]]]+=1
                    continue
                data[ind[0]][ind[1]]+=el['data'][i][0]
                count[ind[0]][ind[1]]+=1


        ## transform into array
        nodemap=n.array(nodemap)
        meta['uniquenodes']=n.unique(nodemap).size

        ## renormalise
        data=data*self.scaling
        data=data/n.where(count == 0,1,count)
        ## get rid of Nan?
        
        self.data=data
        self.log.debug("collect data:\n%s"%data)
        self.count=count
        self.log.debug("collect count:\n%s"%count)
        self.fail=fail
        self.log.debug("collect fail:\n%s"%fail)
        self.nodemap=nodemap
        self.log.debug("collect nodemap:\n%s"%nodemap)
        self.meta=meta
        self.log.debug("collect meta:\n%s"%meta)

    def addtext(self,meta,sub,fig):
        self.log.debug("addtext")
        import matplotlib.patches as patches

        sub.set_axis_off()

        # build a rectangle in axes coords
        left, width = .1, .9
        bottom, height = .1, .9
        right = left + width
        top = bottom + height
        
        cols=3
        tags=self.metatags
        nrmeta=len(tags)
        if nrmeta%cols == 1:
            nrmeta+=1
            tags.append(None)
        layout=n.array(tags).reshape(nrmeta/cols,cols)

        for r in xrange(nrmeta/cols):
            for c in xrange(cols):
                m=layout[r][c]
                if not (m and meta.has_key(m)): continue 
                val=meta[m]
                sub.text(left+c*width/cols, bottom+r*height/(nrmeta/cols), "%s: %s"%(m,val), horizontalalignment='left', verticalalignment='top',transform=sub.transAxes)

    def addcount(self,count,sub,fig):
        self.log.debug("addcount")
        from matplotlib.colorbar import Colorbar,make_axes
        
        cax=sub.imshow(count,cmap=self.cmap,interpolation='nearest')
        axlim=sub.axis()
        sub.axis(n.append(axlim[0:2],axlim[2::][::-1]))

        sub.set_title('Pair samples (#)')
        cb=fig.colorbar(cax)
        #cb.set_label('units')

    def adddata(self,data,sub,fig):
        self.log.debug("adddata")
        vmin=n.min(data[(data > 1/self.scaling).nonzero()])
        vmax=n.max(data[(data < 1.0*self.scaling).nonzero()])

        self.log.debug("adddata: normalize vmin %s vmax %s"%(vmin,vmax))

        cax=sub.imshow(data,cmap=self.cmap,interpolation='nearest',vmin=vmin,vmax=vmax)
        axlim=sub.axis()
        sub.axis(n.append(axlim[0:2],axlim[2::][::-1]))

        #sub.set_title('Latency (%1.0es)'%(1/self.scaling))
        sub.set_title(r'Latency ($\mu s$)')
        cb=fig.colorbar(cax)
        #cb.set_label("%1.0es"%(1/self.scaling))

    def addhist(self,data,sub,fig1):
        self.log.debug("addhist")
        """
        Prepare and filter out 0-data
        """
        d=data.ravel()
        d=d[(d > 1/self.scaling).nonzero()]
        vmin=n.min(d)
        d=d[(d < 1.0*self.scaling).nonzero()]
        vmax=n.max(d)
        
        
        (nn, bins, patches) = sub.hist(d,bins=50,range=(vmin,vmax))
        #sub.set_xlim(int(vmin-1),int(vmax+1))

        ## black magic: set colormap to histogram bars
        avgbins=(bins[1:]+bins[0:-1])/2
        newc=sub.pcolor(avgbins.reshape(avgbins.shape[0],1),cmap=self.cmap)
        sub.figure.canvas.draw()
        fcs=newc.get_facecolors()
        newc.set_visible(False)
        newc.remove()
        for i in xrange(avgbins.size):
            patches[i].set_facecolor(fcs[i])
        sub.figure.canvas.draw()

        

    def addcm(self):
        self.log.debug("addcm")
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore",category=DeprecationWarning)
            import matplotlib.cm as cm

        badalpha=0.25
        badcolor='grey'
        
        cmap=cm.jet
        cmap.set_bad(color=badcolor,alpha=badalpha)
        cmap.set_over(color=badcolor,alpha=badalpha)
        cmap.set_under(color=badcolor,alpha=badalpha)
        
        self.cmap=cmap


        
    def plot(self,data=None,count=None,meta=None):
        self.log.debug("plot")
        if not data:
            data=self.data
        if not count:
            count=self.count
        if not meta:
            meta=self.meta
        
        import matplotlib.pyplot as ppl
        
        # enable LaTeX processing. Internal mathtext should work fine too
        #mp.rcParams['text.usetex']=True
        mp.rcParams['mathtext.fontset']='custom'
        
        self.ppl=ppl
        
        ## set colormap
        self.addcm()
        
        # scale for ISO Ax
        from math import sqrt
        figscale=sqrt(2)
        # A4: 210 mm width 
        # 1 millimeter = 0.0393700787 inch
        mmtoin=0.0393700787
        figwa4=210*mmtoin
        figw=figwa4
        figh=figw*figscale
        fig1=self.ppl.figure(figsize=(figw,figh))
        fig1.show()
        
        def shrink(rec,s=None):
            if not s:
                s=0.1
            l,b,w,h=rec
            
            nl=l+w*s/2
            nb=b+h*s/2
            nw=(1-s)*w
            nh=(1-s)*h
            
            ans=[nl,nb,nw,nh]
            return ans
        
        
        texth=0.1
        subtext=fig1.add_axes(shrink([0,1-texth,1,texth]))
        self.addtext(meta,subtext,fig1)
        
        datah=1/figscale
        subdata=fig1.add_axes(shrink([0,1-texth-datah,1,datah]))
        self.adddata(data,subdata,fig1)

        histw=0.7
        subhist=fig1.add_axes(shrink([0,0,histw,1-datah-texth],0.3))
        self.addhist(data,subhist,fig1)

        
        subcount=fig1.add_axes(shrink([1-histw,0,histw,1-datah-texth],0.3))
        self.addcount(count,subcount,fig1)
        
        fig1.canvas.draw()
        
        self.ppl.show()


if __name__ == '__main__':
    import getopt
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dpmf:")
    except getopt.GetoptError, err:
        print str(err) # will print something like "option -a not recognized"
        sys.exit(2)
    
    fn='test2'
    debug=False
    debugplot=False
    debugmympi=False
    for o,a in opts:
        if o in ['-f']:
            fn=a
        if o in ['-d']:
            debug=True
            debugplot=True
            debugmympi=True
        if o in ['-p']:
            debugplot=True
        if o in ['-m']:
            debugmympi=True

    setdebugloglevel(debugmympi)
    m=mympi(nolog=False,serial=True)
    m.fn=fn
    data=m.read()
    #print data

    setdebugloglevel(debugplot)
    
    ppa=pingponganalysis()
    ppa.collect(data)
    ppa.plot()
    