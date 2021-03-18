#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Eclipse SUMO, Simulation of Urban MObility; see https://eclipse.org/sumo
# Copyright (C) 2008-2021 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    runner.py
# @author  Jakob Erdmann
# @date    2017-01-23


from __future__ import print_function
from __future__ import absolute_import
import os
import sys

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import traci  # noqa
import sumolib  # noqa
import traci.constants as tc  # noqa


sumoBinary = sumolib.checkBinary('sumo')
traci.start([sumoBinary,
             "-n", "input_net4.net.xml",
             "-r", "input_routes.rou.xml",
             "--no-step-log",
             "--vehroute-output", "vehroutes.xml",
             "--vehroute-output.write-unfinished",
             "--tripinfo-output", "tripinfos.xml",
             "--stop-output", "stops.xml",
             "--device.taxi.dispatch-algorithm", "traci",
             ] + sys.argv[1:])


traci.simulationStep()

def dispatch():
    fleet = traci.vehicle.getTaxiFleet(0)
    taxiID = fleet[0]
    print("taxiFleet", fleet)
    reservations = traci.person.getTaxiReservations(0)
    print("reservations", reservations)

    reservation_ids = [r.id for r in reservations]
    b, c = reservation_ids
    # plan the following stops
    # (a was removed)
    # pickup b
    # pickup c, dropoff b
    # dropoff c
    traci.vehicle.dispatchTaxi(taxiID, [b, c, b, c])
    print("currentCustomers", traci.vehicle.getParameter(taxiID, "device.taxi.currentCustomers"))

print("%s reservations %s" % (
    traci.simulation.getTime(),
    traci.person.getTaxiReservations(0)))
traci.person.removeStages("a")
while traci.simulation.getMinExpectedNumber() > 0 or traci.simulation.getTime() < 400:
    traci.simulationStep()
    if traci.simulation.getDepartedNumber() > 0:
        print("%s reservations %s" % (
            traci.simulation.getTime(),
            traci.person.getTaxiReservations(0)))
        dispatch()
traci.close()
