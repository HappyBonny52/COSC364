#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
import select
import socket
import threading
import random as rand
from threading import Timer, Lock
RECV_BUFFSIZE = 1024 

class Config:
    """
    Config object initialised with argument string that is the string representation
    of the config filepath for <obj> as initialised object name and <param> as the paramter in correct format
    each parameter's value can be accessed by <obj>.params["<param>"] and will give
    a list of string representation of the value/s
    
    """
    def __init__(self, path):
        """
        <path> : string representation of config location
        <params> : dict of key: parameter and value: value, all values are init as None
        <req_params> : set of strings of expected REQUIRED paramters in config file
        """
        self.path = path
        self.params = {
            'router-id':None,
            'input-ports':None,
            'outputs':None,
            'timers':None
        }
        self.__req_params = {'router-id', 'input-ports', 'outputs'}
        
    def __str__(self):
        return """Config path: {0}\nParamters: 
             router-id: {1}
             input-ports: {2}
             outputs: {3}
             timers: {4}\n""".format(self.path, self.params['router-id'],
                                                       self.params['input-ports'],
                                                       self.params['outputs'],
                                                       self.params['timers'],)
        
    def __isPortValid(self, port):
        """Checks if port is in range of 1024 <= port <= 64000
        returns True if in range and False otherwise"""
        return False if port < 1024 or port > 64000 else True
   
    def __isRouterIdValid(self, routerId):
        """Checks routerId is in range of 1 <= routerId <= 64000
        returns True if in range and False otherwise"""       
        return False if routerId < 1 or routerId > 64000 else True
        
    def unpack(self):
        """
        Function to unpack config parameters and stores them in their representative variables
        DOES NOT return anything. The values are stored as attributes of this class
        """
        config_file = open(self.path, "r")
        config = config_file.read().split('\n')
        config_file.close()
         
        for line in config:
            
            #checks if line is even worth further parsing ie. is a parameter line
            if line.split(' ', 1)[0] in self.params:
                
                try:
                    #parses the line, param is a string and value is a list of strings
                    param = line.split(' ', 1)[0]
                    value = line.split(' ', 1)[1].replace(' ', '').split(',')
                    
                    #error handles
                    if not value:
                        #no value
                        raise IndexError
                    
                    if param == "router-id":
                        if not self.__isRouterIdValid(int(value[0])):
                            #router-id is out of range
                            raise ValueError
                    
                    elif param == "input-ports":
                        for port in value:
                            if not self.__isPortValid(int(port)):
                                #input-ports is out of range
                                raise ValueError
                            
                    elif param == "outputs":
                        for output in value:
                            parsed = output.split("-")
                            if not self.__isRouterIdValid(int(parsed[2])):
                                #output router id is out of range
                                raise ValueError
                            if not self.__isPortValid(int(parsed[0])):
                                #output port is out of range
                                raise ValueError
                    
                    
                    #inserts the value in config file as the value for params dict for given key: param
                    self.params[param] = value
                    
                except(IndexError):
                    print("PARAMETER <{}> MISSING VALUES. PLEASE CHECK CONFIG".format(param))
                    sys.exit(1)
                except(ValueError):
                    print("PARAMETER <{}> INVALID VALUE. PLEASE CHECK CONFIG".format(param))
                    sys.exit(1)
                except:
                    #Uncatched error. Debug code if you see this prompted!!!
                    print("--FATAL INTERNAL ERROR--")
                    sys.exit(1)
                    
        #checks for missing required parameters by finding if any of the required fields are still None
        for param in self.params:
            if self.params[param] == None and param in self.__req_params:
                raise TypeError("PARAMETER <{}> MISSING. PLEASE CHECK CONFIG".format(param))    
        
class Router:
    """For this router to have its own information based on config file"""
    def __init__(self,  rtrId, inputs, outputs):
        
        self.rtr_id = rtrId # of type int
        self.inputs = inputs # list of input ports
        self.neighbor = self.decompose_output(outputs) # dictionary of peer routers
        #neighbor contains corresponding output port and link cost info)
    
    def decompose_output(self, outputs):
        """split output format by '-' and make dictionary"""
        #(peer's_input_port is equal to current router's output_port)
        #Output format : [peer's_input_port - metric(link cost) - peer's router id]
        #neighbor format : {dest_id: {'cost' : cost_val, 'output' : output_val}}
        neighbor = {}
        for output in outputs:
            neighbor[int(output.split('-')[2])] = {'cost': int(output.split('-')[1]), 
                                                   'output' : int(output.split('-')[0])}
        return neighbor 

    def display_table(self, contents, flag, timer):
        display = f"Routing table of router {self.rtr_id}\n"
        display += '+-----------------------------------------------------------------------+\n'
        display += '|  Destination  |  Next-hop  |  Cost  |  Route Change Flag  |   Timer   |\n'
        display += '+-----------------------------------------------------------------------+\n'
        for entry in contents:
            space1 = '  ' if contents[entry]['metric'] < 10 else ' ' #For drawing tidy table
            space2 = ' ' if flag[entry] else '' #For drawing tidy table
            display += "|    router {0}   |  router {1}  |   {2}{5}  |        {3}{6}        | {4} |\n".format(entry,
                                                                                                         contents[entry]['next-hop'],
                                                                                                         contents[entry]['metric'],
                                                                                                         flag[entry],
                                                                                                         timer[entry],
                                                                                                         space1, space2)
        display += '+-----------------------------------------------------------------------+\n'
        print(display)
        
    def generate_table(self, entry):
        content = {}
        dest, next_hop, metric = entry[0], entry[1], entry[2]
        for i in range(len(dest)):
            content[dest[i]] = {'next-hop' : next_hop[i], 'metric' : metric[i]}
        return content

    def add_entry(self, table, dst_rtr, next_hop, cost):
        table[dst_rtr] = {'next-hop' : next_hop , 'metric' : cost}
        return table

    def modify_entry(self, table, dst_rtr, next_hop, cost):
        table[dst_rtr]['next-hop'] = next_hop
        table[dst_rtr]['metric'] = cost 
        return table

class Demon:
    def __init__(self, Router, timers=None):
        if timers:
            self.timers = {'periodic':int(timers[0]),'timeout':int(timers[1]), 'garbage-collection':int(timers[2])}   
        else:
            self.timers = {'periodic':1, 'timeout':6, 'garbage-collection':4}
        self.router = Router
        self.route_change_flags = {self.router.rtr_id: False}
        self.timer_status = {self.router.rtr_id: "         "}
        self.timeouts, self.garbage_collects = {}, {}
        self.poison_reverse_needed, self.poison_entry_needed= set(), set()
        self.socket_list = self.create_socket()
        self.cur_table = self.router.generate_table([[self.router.rtr_id], [self.router.rtr_id], [0]])
        self.response_pkt = self.rip_response_packet(self.compose_rip_entry(self.cur_table))
        self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)
        self.update_periodic()
        self.packet_exchange()

    #______Process Packet__________________________________________________________________________________

    def create_socket(self):
        """Creating UDP sockets and to bind one with each of input_port"""
        socket_list = []
        for i in range(len(self.router.inputs)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', int(self.router.inputs[i]))) #bind with local host         
            socket_list.append(sock)
        return socket_list

    def compose_rip_entry(self, entry):
        """
        #   RIP ENTRY FORMAT
        #+--------------------------------------------------------------+
        #|  address family identifier(2 bytes) + must be zero (2 bytes) |
        #|                   IPv4 address (4 bytes)                     |
        #|                   must be zero (4 bytes)                     |
        #|                   must be zero (4 bytes)                     |
        #|                       metric(4 bytes)                        |
        #+--------------------------------------------------------------+
        #The number of rip entry can be up to 25(including)
        """
        rip_entry = bytearray()
        afi = 0 #afi = address family identifier
        must_be_zero = 0
        dest = list(entry)
        for i in range(len(entry)): #the item in range() will be replaced by lists of list entry contents
            #first 32 bits of rip entry
            rip_entry += afi.to_bytes(2, 'big')
            rip_entry += must_be_zero.to_bytes(2, 'big')
            # second to fifth of rip entry
            rip_entry += dest[i].to_bytes(4, 'big')
            rip_entry += must_be_zero.to_bytes(4, 'big')
            rip_entry += must_be_zero.to_bytes(4, 'big')
            rip_entry += entry[dest[i]]['metric'].to_bytes(4, 'big')
        return rip_entry

    def rip_response_packet(self, rip_entry):
        """
        #   RIP PACKET FORMAT
        #+--------------------------------------------------------------+
        #|  command(1 byte) + version (1 byte) +   must_be_zero(2bytes) |
        #|--------------------------------------------------------------|
        #|       rip entry(20 bytes) * the number of rip entry          |
        #+--------------------------------------------------------------+
        #The number of rip entry can be up to 25(including) 
        #rip entry will be received as an bytearray from compose_rip_entry() 
        #and is added to the end of rip packet.
        """
        #components of common header
        command, version, must_be_zero_as_rtr_id = 2, 2, self.router.rtr_id
   
        #create bytearray for response_packet
        resp_pkt = bytearray()

        #adding common header into response_packet(bytearray)
        resp_pkt += command.to_bytes(1, 'big')
        resp_pkt += version.to_bytes(1, 'big')
        resp_pkt += must_be_zero_as_rtr_id.to_bytes(2,'big')
        #adding rip entry into response_packet(bytearray)
        resp_pkt += rip_entry
        return resp_pkt

    def split_horizon_with_poison_reverse(self, peer_rtr, port):
        """Generate a customized packet with split_horizon allowing poison reverse"""
        filtered = {}
        for dest in self.cur_table:
            #posion_reverse
            if self.cur_table[dest]['metric'] > 15: 
                #not filtering entry as it has to be send to peer router 
                filtered[dest] = self.cur_table[dest] 
            else:
                #split_horizon
                if (self.cur_table[dest]['next-hop'] and dest) != peer_rtr:
                    #filter entry with not known information to peer router
                    filtered[dest] = self.cur_table[dest]
        return self.rip_response_packet(self.compose_rip_entry(filtered))
   
    def send_packet(self):
        peer = self.router.neighbor
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sending_socket:
                for i in range(len(peer)):
                    port = list(peer.values())[i]['output']
                    peer_rtr = list(peer)[i]
                    customized_pkt = self.split_horizon_with_poison_reverse(peer_rtr, port) #customized_packet for each output
                    sending_socket.sendto(customized_pkt, ('127.0.0.1', port)) 

    def receive_packet(self):
        while True:
            read_socket_lis, _, _ = select.select(self.socket_list, [], [])
            for read_socket in read_socket_lis:
                for i in range(len(self.router.inputs)):
                    receive_from = list(self.router.neighbor)[i]
                    if read_socket == self.socket_list[i]:
                        print(f'\nReceived packet from router {receive_from}')
                        if receive_from != self.router.rtr_id:
                            self.timer_timeout(receive_from) #This line will initiate timeout for the peer routers                             
                        resp_pkt, port = self.socket_list[i].recvfrom(RECV_BUFFSIZE)
                        checked_packet = self.is_packet_valid(resp_pkt, receive_from)
                        if  checked_packet:
                            self.response_pkt = resp_pkt
                            self.update_entry(checked_packet, receive_from)
                        else:
                            print(f"Received packet from router {receive_from} failed validity check!\nDrop this packet....")

    def packet_exchange(self):
        try:
            while True:
                self.receive_packet()
                raise KeyboardInterrupt

        except KeyboardInterrupt:
            print('Keyboard Interrupted!')
        sys.exit(1)

    def is_packet_valid(self, packet, receive_from):
        """Chekc if the received packet is valid return packet contents if True else return False """
        entry = {}
        command = int.from_bytes(packet[0:1], "big") #command should be 2
        version = int.from_bytes(packet[1:2], "big") #version should be 2
        rtr_id_as_ip_addr = int.from_bytes(packet[2:4], "big") #This should be in range of 1024 <= x <= 64000
        is_valid = True
        if command != 2:
            is_valid = False
            print("Packet Invalid : Wrong value of command")
        if  version != 2:
            is_valid = False
            print("Packet Invalid : Wrong value of version")
        if not (1 <= rtr_id_as_ip_addr <= 64000) : 
            is_valid = False
            print("Packet Invalid : Wrong value of router")

        for i in range((len(packet)-4)// 20):
            afi = (int.from_bytes(packet[4+20*i:6+20*i], "big")) #afi should be 0
            must_be_zeros = ( int.from_bytes(packet[6+20*i:8+20*i], "big") +  int.from_bytes(packet[12+20*i:20+20*i], "big") )
            dest_id = int.from_bytes(packet[(8+20*i):(12+20*i)], "big") #This should be in range of 1024 <= x <= 64000
            metric= int.from_bytes(packet[(20+20*i):(24+20*i)], "big") #This should be in range of 0 <= x <= 15
            if afi != 0:
                is_valid = False
                print("Packet Invalid : Wrong value of address family identifier")
            if must_be_zeros != 0:
                is_valid = False
                print("Packet Invalid : Wrong value of must_be_zero field")
            if not (1 <= dest_id <= 64000):
                is_valid = False
                print("Packet Invalid : Wrong value of destination router id")
            if not (0 <= metric <= 15):
                if metric > 15:
                    self.handle_received_poison(receive_from, dest_id)     
                else :
                    flag = False
                    print("Packet Invalid : Wrong value of metric")

            entry[dest_id] = {'next-hop': receive_from, 'metric': metric}
        self.handle_poison_reverse(receive_from, entry)
        return entry if is_valid else False

    #_____Timer Event_______________________________________________________________________________________

    def timer_timeout(self, dst_id):
        """For a given dst_id, it either adds a new Timer thread object that will eventually call garbage_collection(dst_id)
        OR 'Refreshes' the timer for given dst_id in self.timeouts dictionary by creating a new Timer thread object"""
        #it should be fine on memory because of python garbage collection 
        #as long as the old Timer thread object isn't referenced anywhere else    
        if self.timeouts.get(dst_id, None):
            self.timeouts[dst_id].cancel()
            del self.timeouts[dst_id]
        self.timeouts[dst_id] = Timer(self.timers['timeout'], lambda: self.timer_garbage_collection(dst_id))
        self.timeouts[dst_id].start()

    def timer_garbage_collection(self, dst_id):
        """Used for adding a Timer thread object that will eventually call event_remove(dst_id) for a given dst_id"""
        if self.timeouts.get(dst_id, None):
            del self.timeouts[dst_id]
        
        if not self.garbage_collects.get(dst_id, None):
            self.handle_crashed_link(dst_id)
            self.garbage_collects[dst_id] = Timer(self.timers['garbage-collection'], lambda: self.event_remove(dst_id))
            self.garbage_collects[dst_id].start()

    def timer_remove_garbage_collection(self, dst_id):
        """Used for removing the Timer thread object that will eventually call event_remove(dst_id) for a given dst_id"""
        if self.garbage_collects.get(dst_id, None) :
            self.garbage_collects[dst_id].cancel()
            self.timer_status[dst_id] = "         "
            del self.garbage_collects[dst_id]

    #_____Link change Event_________________________________________________________________________________

    def update_periodic(self):
        #Generates random float between [0.8*periodic time, 1.2*periodic time] and rounds to 2dp
        period = round(rand.uniform(0.8*self.timers['periodic'],1.2*self.timers['periodic']), 2)
        threading.Timer(period, self.update_periodic).start()

        print(f"Periodic Update : Sending packet ...... ")
        self.send_packet()                 
    
    def event_remove(self, dst_id):
        """Simply removes the first entry with matching dst_id field"""
        lis = []
        for dst in self.cur_table:
            if self.cur_table[dst]['metric']>15 or self.cur_table[dst]['metric'] == 0:
                lis.append(dst)
        #if the router becomes a stub_router
        if len(lis) == len(self.cur_table):
            self.remove_entry(dst_id, is_stub = True)

        #if the router is connected with one or more reachable routers
        if self.handle_collected_all_poison_reverse():
            self.remove_entry(dst_id, is_stub = False)

    def event_timeout(self, dst_id):
        if dst_id in self.cur_table:
            self.cur_table[dst_id]['metric']=16
            self.timer_status[dst_id]= "TIMED_OUT"
            self.route_change_flags[dst_id] = True 

    def remove_entry(self, dst_id, is_stub): 
        if self.garbage_collects.get(dst_id, None):
                del self.garbage_collects[dst_id]
            
        if self.cur_table.get(dst_id, None) and dst_id != self.router.rtr_id:
            print("All poison reverse received!") if not is_stub else print("As stubbed, remove unreachable ROUTE ", dst_id)
            self.cur_table.pop(dst_id)
            self.send_packet()
              
        print_lock = threading.Lock()
        print_lock.acquire()
        print(f"Removed entry for ROUTE : {dst_id} \n")
        self.timer_remove_garbage_collection(dst_id)
        self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)
        print_lock.release()

    def update_entry(self, new_entry, receive_from):
        select_route = False
        for new_dst in new_entry:
            #new_metric = cost received + connected link cost
            new_metric = new_entry[new_dst]['metric'] + self.router.neighbor[receive_from]['cost'] 
            # if new_dst not in known_dst in current routing table 
            if (new_dst not in self.cur_table) and new_entry[new_dst]['metric'] != 16:       
                self.timer_status[new_dst] = '         '
                self.route_change_flags[new_dst] = True
                print(f"******NOTICE : NEW ROUTE FOUND : ROUTER {new_dst} IS REACHABLE******" )
                self.cur_table = self.router.add_entry(self.cur_table, new_dst, receive_from, new_metric)
            else : # if new_dst in known_dst in current routing table    
                select_route = True
                route = self.handle_route_convergence(new_entry, new_metric, new_dst, receive_from)   
                                    
        self.response_pkt = self.rip_response_packet(self.compose_rip_entry(self.cur_table))
        self.handle_unreachable_route()
        if select_route :
            self.handle_route(route)
        print("\nUpdated Table")
        self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)

    def handle_route(self, route):
        better_route, poison_route = route[0], route[1]
        if better_route :
            print("Triggered update : Send packets due to the route change")
            self.send_packet()
        if poison_route:
            print("\nPosion received!")
            print("Updated poisoned_route\n")
            self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)

    def handle_crashed_link(self, dst_id):
        """Handler for router directly connected with crashed one"""
        print(f"Route for reaching * ROUTER {dst_id} * crashed!")
        for dst in self.cur_table:
            if not (self.cur_table[dst]['next-hop'] == dst_id):
                if dst in self.router.neighbor.keys() and dst != dst_id:
                    self.poison_reverse_needed.add(dst) # Add peer router for receiving poison_reverse
            else:
                self.poison_reverse_needed = set()
                self.poison_entry_needed = set()

        if dst_id in self.cur_table and dst_id != self.router.rtr_id:
            self.poison_entry_needed.add(dst_id)
            self.event_timeout(dst_id)

        self.handle_route_via_crashed_rtr(dst_id)

    def handle_poison_reverse(self, receive_from, entry):
        """Handle Event for router directly connected with crashed router
        As soon as it notices the peer router down, send poison to other alive peer routers. 
        This function is for processing with poison reverse from which it sent"""
        if receive_from in self.poison_reverse_needed:
            for new_dst in entry.copy():
                if new_dst in self.poison_entry_needed and entry[new_dst]['metric']>15 :
                    self.poison_entry_needed.remove(new_dst)
        if len(self.poison_entry_needed) == 0 and receive_from in self.poison_reverse_needed:
           self.poison_reverse_needed.remove(receive_from)

    def handle_received_poison(self, receive_from, dest_id):
        """Handle event for routers who didn't detect crashed router directly 
        but who has received info about crashed router from peer router"""
        if receive_from not in self.poison_reverse_needed: #router who didn't detect link crash directly
            if dest_id in self.cur_table and dest_id != self.router.rtr_id:
                self.event_timeout(dest_id)
                self.poison_entry_needed.add(dest_id)
                print(f"POISON REVERSE received : ROUTE to {dest_id}")
                for dst in self.cur_table:
                    if dst in self.router.neighbor.keys() and dst != dest_id:
                        self.poison_reverse_needed.add(dst) # Add peer router for receiving poison_reverse
                        #self.event_timeout(dst)
                self.send_packet()
        print("\nTriggered update")
        self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)

    def handle_route_convergence(self, new_entry, new_metric, new_dst, receive_from):
        better_route = False
        poison_route = False
        self.route_change_flags[new_dst] = False

        if new_entry[new_dst]['metric'] > 15:
            if new_dst != self.router.rtr_id:
                self.event_timeout(new_dst)
                poison_route = True
            else:
                if new_entry[new_dst]['metric']<=15 and new_dst not in self.poison_entry_needed:
                    #if new_dst in self.cur_table:
                    self.route_change_flags[new_dst] = False
                    if (new_metric < self.cur_table[new_dst]['metric']) and new_dst not in self.poison_reverse_needed and new_metric <=15:
                        better_route = True
                        print(f"******NOTICE : BETTER ROUTE FOUND FOR ROUTER******")
                        print(f"ROUTE {new_dst} : cost reduced from {self.cur_table[new_dst]['metric']} to {new_metric}")
                        self.route_change_flags[new_dst] = True
                        self.cur_table = self.router.modify_entry(self.cur_table, new_dst, receive_from, new_metric)   
        return (better_route, poison_route)

    def handle_unreachable_route(self):
        for dst in self.cur_table.copy():
            if self.handle_collected_all_poison_reverse and self.cur_table[dst]['metric']>15 and dst != self.router.rtr_id:
                #self.cur_table.pop(dst)
                print(f"\nRoute to {dst} has been popped ; all poison_reverse received")
                self.poison_entry_needed = set()
                self.poison_reverse_needed = set()
                self.cur_table.pop(dst)
               
        #self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)

    def handle_route_via_crashed_rtr(self, dst_id):
        for reachable in self.cur_table.copy():
            if reachable != self.router.rtr_id:
                if reachable in self.cur_table:
                    if self.cur_table[reachable]['next-hop'] == dst_id:
                        self.poison_entry_needed.add(reachable)
                        self.event_timeout(reachable)
                        self.timer_timeout(reachable)
        if dst_id != self.router.rtr_id:
            self.event_remove(dst_id)
        self.send_packet() 

    def handle_collected_all_poison_reverse(self):
        return True if (len(self.poison_reverse_needed)==0 and len(self.poison_entry_needed)==0) else False


if __name__ == "__main__":
    config = Config(sys.argv[1])
    config.unpack()
    print(config)
    
    router = Router(int(config.params['router-id'][0]), config.params['input-ports'], config.params['outputs'])
    rip_routing = Demon(router, config.params['timers'])
