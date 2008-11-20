"""
@file    network.py
@author  Yun-Pang.Wang@dlr.de
@date    2007-12-25
@version $Id$

This script is to retrive the network data, the district data and the vehicle data, generated by SUMO, from the respective XML files.
Besides, the class 'Net' is also definded here.

Copyright (C) 2008 DLR/TS, Germany
All rights reserved
"""

import os, string, sys, datetime, math, operator
from xml.sax import saxutils, make_parser, handler
from elements import Predecessor, Vertex, Edge, Vehicle, Path, TLJunction, Signalphase, DetectedFlows
from dijkstra import dijkstraPlain, dijkstraBoost

# Net class stores the network (vertex and edge collection). 
# Moreover, the methods for finding k shortest paths and for generating vehicular releasing times
#  are also in this class.

class Net:
    def __init__(self):
        self._vertices = []
        self._edges = {}
        self._fullEdges = {}
        self._startVertices = []
        self._endVertices = []
        self._paths = {}
        self._junctions = {}
        self._detectedLinkCounts = 0.
        
    def newVertex(self):
        v = Vertex(len(self._vertices))
        self._vertices.append(v)
        return v

    def getEdge(self, edgeLabel):
        return self._edges[edgeLabel]

    def addEdge(self, edgeObj):
        edgeObj.source.outEdges.add(edgeObj)
        edgeObj.target.inEdges.add(edgeObj)
        if edgeObj.kind == "real":
            self._edges[edgeObj.label] = edgeObj
        self._fullEdges[edgeObj.label] = edgeObj

    def addIsolatedRealEdge(self, edgeLabel):
        self.addEdge(Edge(edgeLabel, self.newVertex(), self.newVertex(),
                          "real"))
                                                   
    def initialPathSet(self):
        for startVertex in self._startVertices:
            self._paths[startVertex] = {}
            for endVertex in self._endVertices:
                self._paths[startVertex][endVertex] = []
    
    def cleanPathSet(self):
        for startVertex in self._startVertices:
            for endVertex in self._endVertices:
                self._paths[startVertex][endVertex] = []
                
    def addTLJunctions(self, junctionObj):
        self._junctions[junctionObj.label] = junctionObj
        
    def getJunction(self, junctionlabel):
        return self._junctions[junctionlabel]
        
    def linkReduce(self):
        toRemove = []
        for node in self._vertices:
            split = True
            candidates = []
            if len(node.inEdges) == 1:
                for edge in node.outEdges:
                    if edge.kind != "real" and len(edge.target.inEdges) == 1:
                        candidates.append(edge)
            else:
                for edge in node.inEdges:
                    if edge.kind != "real" and len(edge.source.outEdges) == 1:
                        candidates.append(edge)
                        split = False
            for edge in candidates:
                if split:
                    for link in edge.target.outEdges:
                        node.outEdges.add(link)
                        link.source = node
                    node.outEdges.remove(edge)
                    del self._fullEdges[edge]
                    toRemove.append(edge.target)   
                else:
                    for link in edge.source.inEdges:
                        node.inEdges.add(link)
                        link.target = node
                    node.inEdges.remove(edge)
                    del self._fullEdges[edge]
                    toRemove.append(edge.source)
            
        for node in toRemove:
            self._vertices.remove(node)

    def reduce(self):
        visited = set()
        for link in self._edges.itervalues():
            if link.target in visited:
                continue
            sourceNodes = set([link.target])
            targetNodes = set()
            pendingSources = [link.target]
            pendingTargets = []
            stop = False
            while not stop and (pendingSources or pendingTargets):
                if pendingSources:
                    source = pendingSources.pop()
                    for out in source.outEdges:
                        if out.kind == "real":
                            stop = True
                            break
                        if out.target not in targetNodes:
                            targetNodes.add(out.target)
                            pendingTargets.append(out.target)
                if not stop and pendingTargets:
                    target = pendingTargets.pop()
                    for incoming in target.inEdges:
                        if incoming.kind == "real":
                            stop = True
                            break
                        if incoming.source not in sourceNodes:
                            sourceNodes.add(incoming.source)
                            pendingSources.append(incoming.source)
            if stop:
                continue
            visited.update(sourceNodes)
            complete = True
            for source in sourceNodes:
                if len(source.outEdges) < len(targetNodes):
                    complete = False
                    break
            if complete:
                for target in targetNodes:
                    for edge in target.outEdges:
                        link.target.outEdges.add(edge)
                        edge.source = link.target
                for source in sourceNodes:
                    for edge in source.inEdges:
                        link.target.inEdges.add(edge)
                        edge.target = link.target

    def createBoostGraph(self):
        from boost.graph import Digraph
        self._boostGraph = Digraph()
        for vertex in self._vertices:
            vertex.boost = self._boostGraph.add_vertex()
            vertex.boost.partner = vertex
        self._boostGraph.add_vertex_property('distance')
        self._boostGraph.add_vertex_property('predecessor')
        for edge in self._fullEdges.itervalues():
            edge.boost = self._boostGraph.add_edge(edge.source.boost, edge.target.boost)
            edge.boost.weight = edge.actualtime

    def checkSmallDiff(self, ODPaths, helpPath, helpPathSet, pathcost):
        for path in ODPaths:
            if path.edges == helpPath:
                return False, False
            else:
                sameEdgeCount = 0
                sameTravelTime = 0.0
                for edge in path.edges:
                    if edge in helpPathSet:
                        sameEdgeCount += 1 
                        sameTravelTime += edge.actualtime
                if abs(sameEdgeCount - len(path.edges))/len(path.edges) <= 0.1 and abs(sameTravelTime/3600. - pathcost) <= 0.05:
                    return False, True
        return True, False
                        
    def findNewPath(self, startVertices, endVertices, newRoutes, matrixPshort, gamma, lohse):
        """
        This method finds the new paths for all OD pairs.
        The Dijkstra algorithm is applied for searching the shortest paths.
        """
        newRoutes = 0
        for start, startVertex in enumerate(startVertices):
            endSet = set()
            for end, endVertex in enumerate(endVertices):
                if matrixPshort[start][end] > 0. and str(startVertex) != str(endVertex):
                    endSet.add(endVertex)
            if options.boost:
                D,P = dijkstraBoost(self._boostGraph, startVertex.boost)
            else:          
                D,P = dijkstraPlain(startVertex, endSet)
            for end, endVertex in enumerate(endVertices):
                if matrixPshort[start][end] > 0. and str(startVertex) != str(endVertex):
                    helpPath = []
                    helpPathSet = set()
                    pathcost = D[endVertex]/3600.
                    ODPaths = self._paths[startVertex][endVertex]
                    for path in ODPaths:
                        path.currentshortest = False
                        
                    vertex = endVertex
                    while vertex != startVertex:
                        if P[vertex].kind == "real":
                            helpPath.append(P[vertex])
                            helpPathSet.add(P[vertex])
                        vertex = P[vertex].source
                    helpPath.reverse()
    
                    newPath, smallDiffPath = self.checkSmallDiff(ODPaths, helpPath, helpPathSet, pathcost)

                    if newPath:
                        newpath = Path(startVertex, endVertex, helpPath)
                        ODPaths.append(newpath)
                        newpath.getPathLength()
                        for route in ODPaths:
                            route.updateSumOverlap(newpath, gamma)
                        if len(ODPaths)> 1:
                            for route in ODPaths[:-1]:
                                newpath.updateSumOverlap(route, gamma)
                        if lohse:
                            newpath.pathhelpacttime = pathcost
                        else:    
                            newpath.actpathtime = pathcost
                        for edge in newpath.edges:
                            newpath.freepathtime += edge.freeflowtime
                        newRoutes += 1
                    elif not smallDiffPath:
                        if lohse:
                            path.pathhelpacttime = pathcost
                        else:
                            path.actpathtime = pathcost
                        path.usedcounts += 1
                        path.currentshortest = True
        return newRoutes

#    find the k shortest paths for each OD pair. The "k" is defined by users.
    def calcKPaths(self, verbose, kPaths, newRoutes, startVertices, endVertices, matrixPshort, gamma):
        if verbose:
            foutkpath = file('kpaths.xml', 'w')
            print >> foutkpath, """<?xml version="1.0"?>
<!-- generated on %s by $Id$ -->
<routes>""" % datetime.datetime.now()
        for start, startVertex in enumerate(startVertices):
            for vertex in self._vertices:
                vertex.preds = []
                vertex.wasUpdated = False
            startVertex.preds.append(Predecessor(None, None, 0))
            updatedVertices = [startVertex]

            while len(updatedVertices) > 0:
                vertex = updatedVertices.pop(0)
                vertex.wasUpdated = False
                for edge in vertex.outEdges:
                    if edge.target != startVertex and edge.target.update(kPaths, edge):
                        updatedVertices.append(edge.target)
    
            for end, endVertex in enumerate(endVertices):
                ODPaths = self._paths[startVertex][endVertex]
                if str(startVertex) != str(endVertex) and matrixPshort[start][end] != 0.:
                    for startPred in endVertex.preds:
                        temppath = []
                        temppathcost = 0.
                        pred = startPred
                        vertex = endVertex
                        while vertex != startVertex:
                            if pred.edge.kind == "real":
                                temppath.append(pred.edge)
                                temppathcost += pred.edge.freeflowtime
                            vertex = pred.edge.source
                            pred = pred.pred
                        
                        if len(ODPaths) > 0:
                            minpath = min(ODPaths, key=operator.attrgetter('freepathtime'))
                            if minpath.freepathtime*1.4 < temppathcost/3600.:
                                break
                        temppath.reverse()
                        newpath = Path(startVertex, endVertex, temppath)
                        newpath.getPathLength()
                        ODPaths.append(newpath)
                        for route in ODPaths:
                            route.updateSumOverlap(newpath, gamma)
                        if len(ODPaths)> 1:
                            for route in ODPaths[:-1]:
                                newpath.updateSumOverlap(route, gamma)
                        newpath.freepathtime = temppathcost/3600.
                        newpath.actpathtime = newpath.freepathtime
                        newRoutes += 1
                        if verbose:
                            foutkpath.write('    <path id="%s" source="%s" target="%s" pathcost="%s">\n' %(newpath.label, newpath.source, newpath.target, newpath.actpathtime))  
                            foutkpath.write('        <route>')
                            for edge in newpath.edges[1:-1]:
                                foutkpath.write('%s ' %edge.label)
                            foutkpath.write('</route>\n')
                            foutkpath.write('    </path>\n')
        if verbose:
            foutkpath.write('</routes>\n')
            foutkpath.close()
            
        return newRoutes

    def printNet(self, foutnet):
        foutnet.write('Name\t Kind\t FrNode\t ToNode\t length\t MaxSpeed\t Lanes\t CR-Curve\t EstCap.\t Free-Flow TT\t Weight\t Connection\n')
        for edgeName, edgeObj in self._edges.iteritems():
            foutnet.write('%s\t %s\t %s\t %s\t %s\t %s\t %s\t %s\t %s\t %s\t %s\t %d\n' 
            %(edgeName, edgeObj.kind, edgeObj.source, edgeObj.target, edgeObj.length, 
              edgeObj.maxspeed, edgeObj.numberlane, edgeObj.CRcurve, edgeObj.estcapacity, edgeObj.freeflowtime, edgeObj.weight, edgeObj.connection))
     
# The class is for parsing the XML input file (network file). The data parsed is written into the net.
class NetworkReader(handler.ContentHandler):
    def __init__(self, net):
        self._net = net
        self._edge = ''
        self._maxSpeed = 0
        self._laneNumber = 0
        self._length = 0
        self._edgeObj = None
        self._junctionObj = None
        self._phaseObj = None
        self._chars = ''
        self._counter = 0
        self._turnlink = None

    def startElement(self, name, attrs):
        self._chars = ''
        if name == 'edge' and (not attrs.has_key('function') or attrs['function'] != 'internal'):
            self._edge = attrs['id']
            self._net.addIsolatedRealEdge(self._edge)
            self._edgeObj = self._net.getEdge(self._edge)
            self._edgeObj.source.label = attrs['from']
            self._edgeObj.target.label = attrs['to']
            self._maxSpeed = 0
            self._laneNumber = 0
            self._length = 0
        elif name == 'tl-logic':
            self._junctionObj = TLJunction()
            self._counter = 0
        elif name == 'phase':
            self._newphase = Signalphase(float(attrs['duration']), attrs['phase'], attrs['brake'], attrs['yellow'])
            self._junctionObj.phases.append(self._newphase)
            self._counter += 1
            self._newphase.label = self._counter
        elif name == 'succ':
            self._edge = attrs['edge']
            if self._edge[0]!=':':
                self._edgeObj = self._net.getEdge(self._edge)
                if self._edgeObj.junction == 'None':
                    self._edgeObj.junction = attrs['junction']
            else:
                self._edge = ""
        elif name == 'succlane' and self._edge!="":
            l = attrs['lane']
            if l != "SUMO_NO_DESTINATION":
                toEdge = self._net.getEdge(l[:l.rfind('_')])
                newEdge = Edge(self._edge+"_"+l[:l.rfind('_')], self._edgeObj.target, toEdge.source)
                self._net.addEdge(newEdge)
                self._edgeObj.finalizer = l[:l.rfind('_')]
                if attrs.has_key('tl'):
                    self._edgeObj.junction = attrs['tl']
                    self._edgeObj.junctiontype = 'signalized'
                    if attrs['dir'] == "r":
                        self._edgeObj.rightturn = attrs['linkno']
                        self._edgeObj.rightlink.append(toEdge)
                    elif attrs['dir'] == "s": 
                        self._edgeObj.straight = attrs['linkno']
                        self._edgeObj.straightlink.append(toEdge)
                    elif attrs['dir'] == "l": 
                        self._edgeObj.leftturn = attrs['linkno']
                        self._edgeObj.leftlink.append(toEdge)
                    elif attrs['dir'] == "t": 
                        self._edgeObj.uturn = attrs['linkno']
                else:
                    self._edgeObj.junctiontype = 'prioritized'
                    if attrs['dir'] == "r":
                        self._edgeObj.rightturn = attrs['state']
                        self._edgeObj.rightlink.append(toEdge)
                    elif attrs['dir'] == "s": 
                        self._edgeObj.straight = attrs['state']
                        self._edgeObj.straightlink.append(toEdge)
                    elif attrs['dir'] == "l": 
                        self._edgeObj.leftturn = attrs['state']
                        self._edgeObj.leftlink.append(toEdge)
                    elif attrs['dir'] == "t": 
                        self._edgeObj.uturn = attrs['state']
        elif name == 'lane' and self._edge != '':
            self._maxSpeed = max(self._maxSpeed, float(attrs['maxspeed']))
            self._laneNumber = self._laneNumber + 1
            self._length = float(attrs['length'])
      
    def characters(self, content):
        self._chars += content

    def endElement(self, name):
        if name == 'edge':
            self._edgeObj.init(self._maxSpeed, self._length, self._laneNumber)
            self._edge = ''
        elif name == 'key':
            if self._junctionObj:
                self._junctionObj.label = self._chars
                self._net.addTLJunctions(self._junctionObj)
                self._chars = ''
        elif name == 'phaseno':
            self._junctionObj.phaseNum = int(self._chars)
            self._chars = ''
        elif name == 'tl-logic':
            self._junctionObj = None


# The class is for parsing the XML input file (districts). The data parsed is written into the net.
class DistrictsReader(handler.ContentHandler):
    def __init__(self, net):
        self._net = net
        self._StartDTIn = None
        self._StartDTOut = None
        self.I = 100

    def startElement(self, name, attrs):
        if name == 'district':
            self._StartDTIn = self._net.newVertex()
            self._StartDTIn.label = attrs['id']
            self._StartDTOut = self._net.newVertex()
            self._StartDTOut.label = self._StartDTIn.label
            self._net._startVertices.append(self._StartDTIn)
            self._net._endVertices.append(self._StartDTOut)
        elif name == 'dsink':
            sinklink = self._net.getEdge(attrs['id'])
            self.I += 1
            conlink = self._StartDTOut.label + str(self.I)
            newEdge = Edge(conlink, sinklink.target, self._StartDTOut, "real")
            self._net.addEdge(newEdge)
            newEdge.weight = attrs['weight']
            newEdge.connection = 1              
        elif name == 'dsource':
            sourcelink = self._net.getEdge(attrs['id'])
            self.I += 1
            conlink = self._StartDTIn.label + str(self.I)
            newEdge = Edge(conlink, self._StartDTIn, sourcelink.source, "real")
            self._net.addEdge(newEdge)
            newEdge.weight = attrs['weight']
            newEdge.connection = 2

## This class is for parsing the additional/updated information about singal timing plans
class ExtraSignalInformationReader(handler.ContentHandler):
    def __init__(self, net):
        self._net = net
        self._junctionlabel = None
        self._phaseObj = None
        self._chars = ''
        self._counter = 0

    def startElement(self, name, attrs):
        self._chars = ''
        if name == 'tl-logic':
            self._counter = 0
        elif name == 'phase':
            self._counter += 1
            junction = self._net.getJunction(self._junctionlabel)
            junction.phaseNum = self._counter
            for phase in junction.phases[:]:
                if phase.label == str(self._counter):
                    phase.duration = float(attrs['duration'])
                    phase.green = attrs['phase'][::-1]
                    phase.brake = attrs['brake'][::-1]
                    phase.yellow= attrs['yellow'][::-1]
      
    def characters(self, content):
        self._chars += content

    def endElement(self, name):
        if name == 'key':
            self._junctionlabel = self._chars
            self._chars = ''
        elif name == 'tl-logic':
            self._junctionObj = None
            
class DetectedFlowsReader(handler.ContentHandler):
    def __init__(self, net):
        self._net = net
        self._edge = ''
        self._edgeObj = None
        self._detectorcounts = 0.
        self._renew = False
        self._skip = False
    
    def startElement(self, name, attrs):
        if name == 'edge':
            if self._edge != '' and self._edge == attrs['id']:
                if self._edgeObj.detectorNum < float(attrs['detectors']):
                    self._edgeObj.detectorNum = float(attrs['detectors'])
                    self.renew = True
                elif self._edgeObj.detectorNum > float(attrs['detectors']):
                    self._skip = True
            else:
                self._edge = attrs['id']
                self._edgeObj = self._net.getEdge(self._edge)
                self._edgeObj.detectorNum = float(attrs['detectors'])
             
        elif name == 'flows':
            if self._renew == True:
                self._newdata.label = attrs['weekday-time']
                self._newdata.flowPger = float(attrs['passengercars'])
                self._newdawta.flowTruck = float(attrs['truckflows'])
    
            else:
                if not self._skip:
                    self._newdata = DetectedFlows(attrs['weekday-time'], float(attrs['passengercars']), float(attrs['truckflows']))
                    self._edgeObj.detecteddata[self._newdata.label]= self._newdata
                
    def endElement(self, name):
        if name == 'edge':
            self._renew = False
