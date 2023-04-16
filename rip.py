#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
import select
import socket
import random as rand
from threading import Timer, Lock
import threading


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
        self.inputs = inputs
        self.neighbor = self.decompose_output(outputs)
    
    def decompose_output(self, outputs):
        """split output format by '-' and sort by each item into list
        # output format [peer's_input_port - metric(link cost) - peer's router id (peer's_input_port is equal to current router's output_port)]"""
        #split output by '-'
        neighbor = {}
        for output in outputs:
            neighbor[int(output.split('-')[2])] = {'cost': int(output.split('-')[1]), 
                                                   'output' : int(output.split('-')[0])}
        return neighbor

class Demon:
    def __init__(self, Router, timers=None):
        """Initialize Demon with input ports for creating UDP sockets 
        <socket_list> : list of binded sockets indexed in its corresponding input port
        """
        self.router = Router
        
        self.timeouts = {}
        self.garbage_collects = {}        
        if timers:
            self.timers = {'periodic':int(timers[0]),'timeout':int(timers[1]), 'garbage-collection':int(timers[2])}   
        else:
            self.timers = {'periodic':6, 'timeout':10, 'garbage-collection':10}
            
        self.socket_list = self.create_socket()

        
        self.poison_collect = []
        self.cur_table = self.generate_table_entry([self.router.rtr_id], self.router.rtr_id, [0])
        self.response_pkt = self.rip_response_packet(self.compose_rip_entry(self.cur_table))
  
        self.display_table(self.cur_table)
        self.periodic_update()
        self.packet_exchange()

    def create_socket(self):
        """Creating UDP sockets and to bind one with each of input_port"""
        socket_list = []
        for i in range(len(self.router.inputs)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', int(self.router.inputs[i]))) #bind with local host         
            socket_list.append(sock)
        return socket_list
        
    def remove_entry(self, dst_id):
        """Simply removes the first entry with matching dst_id field"""
        if self.garbage_collects.get(dst_id, None):
            del self.garbage_collects[dst_id]
            
        if self.cur_table.get(dst_id, None) and dst_id != self.router.rtr_id:###########remove 1
            print("Passing def remove_entry 1")
            print("poison reverse added for router ", dst_id)
            self.poison_collect.append(dst_id)##################
            print("Poison collect list = ", self.poison_collect)
            self.cur_table[dst_id]['metric'] = 16###################### remove 2
            print("Send new route with metric 16 of router", dst_id)
            self.send_packet()###############################
            ##########################################
            for dst in self.cur_table.copy():
                if self.cur_table[dst]['next-hop'] == dst_id:
                    print("Passing def remove_entry 2")
                    print("poison reverse added for router ", dst)
                    self.poison_collect.append(dst)##################
                    print("Poison collect list = ", self.poison_collect)
                    self.cur_table[dst]['metric'] = 16######################
                    print("Send new route with metric 16 AS IT IS NEXT HOP router", dst)
                    self.cur_table.pop(dst)
                    self.send_packet()###############################
                    print("Poison collect list = ", self.poison_collect)
            #########################################
            if dst_id in list(self.cur_table):
                self.cur_table.pop(dst_id)
            
        print_lock = threading.Lock()
        print_lock.acquire()
        print("Removed entry for destRtrId: ", dst_id)

        self.display_table(self.cur_table)
        print_lock.release()
        
    def remove_garbage_collection(self, dst_id):
        """Used for removing the Timer thread object that will eventually call remove_entry(dst_id) for a given dst_id"""
        if self.garbage_collects.get(dst_id, None) :
            self.garbage_collects[dst_id].cancel()
            del self.garbage_collects[dst_id]
    
    def garbage_collection(self, dst_id):
        """Used for adding a Timer thread object that will eventually call remove_entry(dst_id) for a given dst_id"""
        if self.timeouts.get(dst_id, None):
            del self.timeouts[dst_id]
        
        if not self.garbage_collects.get(dst_id, None):
            print(f"Haven't heard from router {dst_id} for so long !")
            self.garbage_collects[dst_id] = Timer(self.timers['garbage-collection'], lambda: self.remove_entry(dst_id))
            self.garbage_collects[dst_id].start()

    def timeout_check(self, dst_id):
        """
        For a given dst_id, it either adds a new Timer thread object that will eventually call garbage_collection(dst_id)
        OR
        'Refreshes' the timer for given dst_id in self.timeouts dictionary by creating a new Timer thread object
        it should be fine on memory because of python garbage collection as long as the old Timer thread object isn't referenced anywhere else**********
        """        
        if self.timeouts.get(dst_id, None):
            self.timeouts[dst_id].cancel()
            del self.timeouts[dst_id]
        self.timeouts[dst_id] = Timer(self.timers['timeout'], lambda: self.garbage_collection(dst_id))
        self.timeouts[dst_id].start()

    def display_table(self, contents):
        dest = list(contents)
        display = f"Routing table of router {self.router.rtr_id}\n"
        display += '+-----------------------------------------------------------------------+\n'
        display += '|  Destination  |  Next-hop  |  Cost  |  Route Change Flag  |   Timer   |\n'
        display += '+-----------------------------------------------------------------------+\n'
        for entry in contents:
            space = '  ' if contents[entry]['metric'] < 10 else ' ' #For drawing tidy table
            display += "|    router {0}   |  router {1}  |   {2}{3}  |                     |           |\n".format(entry,
                                                                                                         contents[entry]['next-hop'],
                                                                                                         contents[entry]['metric'],
                                                                                                         space)
        display += '+-----------------------------------------------------------------------+\n'
        print(display)
        
    def generate_table_entry(self, dst_id, next_hop, cost):
        content = {}
        for i in range(len(dst_id)):
            content[dst_id[i]] = {'next-hop' : next_hop, 'metric' : cost[i]}
        return content

    def update_entry(self, current_table, new_entry, receive_from):
        update = current_table
        print(f"----Current_table-------- \n{update}\n")
        link_cost = self.router.neighbor[receive_from]['cost']
        known_dst = list(current_table)
        better_path = False

        for new_dst in new_entry:
            new_metric = new_entry[new_dst]['metric'] + link_cost
            ############################################################### ----- 3
            if new_dst in self.poison_collect and new_dst != self.router.rtr_id:
                if new_dst in self.poison_collect:
                    if 0 <= new_entry[new_dst]['metric'] <= 15:
                        update = self.add_entry(update, new_dst, receive_from, new_metric)
                        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Passing 3-1")
                        print("poison reverse removed for router", new_dst)
                        self.poison_collect.remove(new_dst)#################
                        print("poison reverse list", self.poison_collect )
                if new_dst in update.keys() and new_dst in self.poison_collect:
                    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Passing 3-2")
                    print("poison reverse removed for router", new_dst)
                    self.poison_collect.remove(new_dst)
                    print("poison reverse list", self.poison_collect )
                    update.pop(new_dst)
            ################################################################ 
            elif new_dst != self.router.rtr_id:
                new_metric = new_entry[new_dst]['metric'] + link_cost
                #if new_dst in self.router.neighbor:
                #    self.timeout_check(new_dst)
                #    self.remove_garbage_collection(new_dst) 
                if (new_dst not in known_dst):
                    print(f"******NOTICE : NEW ROUTE FOUND : ROUTER {new_dst} IS REACHABLE******" )
                    update = self.add_entry(update, new_dst, receive_from, new_metric)

                else:
                    if not current_table[new_dst]['metric']>15 : # if new_dst in known_dst
                        if (new_metric < update[new_dst]['metric']):
                            print(f"******NOTICE : BETTER ROUTE FOUND FOR ROUTER {new_dst} : COST REDUCED FROM {update[new_dst]['metric']} to {new_metric}******" )
                            better_path = True
                            update = self.modify_entry(update, new_dst, receive_from, new_metric)
                    else :
                        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Passing 3-2")
                        print("poison reverse removed for router", new_dst)
                        self.poison_collect.remove(new_dst)
                        print("poison reverse list", self.poison_collect )
                        update.pop(new_dst)
                        print("garbage time start")
                        self.remove_garbage_collection(new_dst) 

                              
        self.cur_table = update
        self.response_pkt = self.rip_response_packet(self.compose_rip_entry(self.cur_table))
        if better_path :
            print("Triggered update : Send packets due to the route change")
            self.send_packet()
        print("Poison collect list = ", self.poison_collect)
        print(f"----Updated Table--------")
        self.display_table(self.cur_table)
        return update

    def add_entry(self, table, dst_rtr, next_hop, cost):
        table[dst_rtr] = {'next-hop' : next_hop , 'metric' : cost}
        return table

    def modify_entry(self, table, dst_rtr, next_hop, cost):
        table[dst_rtr]['next-hop'] = next_hop
        table[dst_rtr]['metric'] = cost 
        return table
        
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
        resp_pkt += command.to_bytes(1, 'big') #command (convert int to 1byte)
        resp_pkt += version.to_bytes(1, 'big') #version (convert int to 1byte)
        resp_pkt += must_be_zero_as_rtr_id.to_bytes(2,'big') #must_be_zero (convert int to 2byte)

        #adding rip entry into response_packet(bytearray)
        resp_pkt += rip_entry
        return resp_pkt

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
        #zeroed out components of first line in rip entry 
        afi, must_be_zero = 0, 0 #afi = address family identifier

        # destination router as ipv4 address containing its metric
        dst_rtr = list(entry)
        for i in range(len(entry)): #Looping entries as it can be up to 25
            # First line in comment above
            rip_entry += afi.to_bytes(2, 'big') #afi
            rip_entry += must_be_zero.to_bytes(2, 'big') #must_be_zero field 
            # Second to Fifth line in comment above 
            rip_entry += dst_rtr[i].to_bytes(4, 'big') # destination router
            rip_entry += must_be_zero.to_bytes(4, 'big') # must_be_zero 
            rip_entry += must_be_zero.to_bytes(4, 'big') # must_be_zero 
            rip_entry += entry[dst_rtr[i]]['metric'].to_bytes(4, 'big') # metric
        return rip_entry
   
    def send_packet(self):
        #randomized periodic update for sending packet
        #i used this for debugging timers -david
        """
        self.display_table(self.cur_table)
        print(threading.enumerate())
        print(self.timeouts)
        print(self.garbage_collects)"""
        peer = self.router.neighbor
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sending_socket:
                for i in range(len(peer)):
                    port = list(peer.values())[i]['output']
                    peer_rtr = list(peer)[i]
                    customized_pkt = self.split_horizon_with_poison_reverse(peer_rtr, port) #customized_packet for each output
                    sending_socket.sendto(customized_pkt, ('127.0.0.1', port)) 

    def split_horizon_with_poison_reverse(self, peer_rtr, port):
        """
        Implement split_horizon by filtering entries and generate customized packet for each peer router.
        Customization : Remove entries that indicate connected peer router(who will be received packet)
        is known as the next hop router with the minimum cost to reach a certain destination router
        in current routing table.
        In short, check if the router receiving this packet already knows about this information
        if it does[it means entries are redundant for peer router], then filter this information 
        and send the other information in routing table
        For poison_reverse, split-horizon-filter process will not be conducted for entry with metric more than 15
        and apply split horizon to the other entries
        """
        table = self.cur_table
        filtered = {}
        for dest in table:
            if table[dest]['metric'] > 15: #poison_reverse
                filtered[dest] = table[dest] #not filtering entry as it has to be send to peer router 
            else:
                if (table[dest]['next-hop'] and dest) != peer_rtr:#split_horizon
                    filtered[dest] = table[dest]#filtered entry from if condition is added to the rip entry for packet
        return self.rip_response_packet(self.compose_rip_entry(filtered))
    
    def is_packet_valid(self, packet, receive_from):
        #===========================================================================#
        #__________________Codes here need to be cleaned____________________________#
        #____________Coded Roughly in order to implement poison reverse_____________#
        #___________________________________________________________________________#
        #===========================================================================#
        entry = {}
        command = int.from_bytes(packet[0:1], "big") #command should be 2
        version = int.from_bytes(packet[1:2], "big") #version should be 2
        rtr_id_as_ip_addr = int.from_bytes(packet[2:4], "big") 
        is_valid = True

        if command != 2:
            is_valid = False
            print("Packet Invalid : Wrong value of command")
        if  version != 2:
            is_valid = False
            print("Packet Invalid : Wrong value of version")
        if not (1 <= rtr_id_as_ip_addr <= 64000) : #This should be in range of 1024 <= x <= 64000
            is_valid = False
            print("Packet Invalid : Wrong value of router")

        for i in range((len(packet)-4)// 20):
            afi = (int.from_bytes(packet[4+20*i:6+20*i], "big"))
            must_be_zeros = ( int.from_bytes(packet[6+20*i:8+20*i], "big") +  int.from_bytes(packet[12+20*i:20+20*i], "big") ) 
            dest_id = int.from_bytes(packet[(8+20*i):(12+20*i)], "big")
            metric= int.from_bytes(packet[(20+20*i):(24+20*i)], "big")
            if afi != 0:
                is_valid = False
                print("Packet Invalid : Wrong value of address family identifier")
            if must_be_zeros != 0:
                is_valid = False
                print("Packet Invalid : Wrong value of must_be_zero field")
            if not (1 <= dest_id <= 64000):
                is_valid = False
                print("Packet Invalid : Wrong value of destination router id")
            else :
                if not (0 <= metric <= 15):
                    if metric >= 15:
                        if metric in self.poison_collect:
                            if dest_id in list(self.cur_table):
                                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Passing 2-1")
                                self.cur_table.pop(dest_id)
                        else:
                            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Passing 2-2")
                            print("poison reverse added for router ", dest_id)
                            self.poison_collect.append(dest_id)
                            print("poison reverse added for router ", dest_id)
                            entry[dest_id] = {'next-hop': receive_from, 'metric': 16}
                    #############################################################################
                    if metric < 0:
                        flag = False
                        print("Packet Invalid : Wrong value of metric")
            if dest_id not in self.poison_collect:
                entry[dest_id] = {'next-hop': receive_from, 'metric': metric}


        return entry if is_valid else False

    def receive_packet(self):
        while True:
            read_socket_lis, _, _ = select.select(self.socket_list, [], [])
            for read_socket in read_socket_lis:
                for i in range(len(self.router.inputs)):
                    receive_from = list(self.router.neighbor)[i]
                    if read_socket == self.socket_list[i]:
                        print(f'\nReceived packet from router {receive_from}')
                        if receive_from != self.router.rtr_id:
                            self.timeout_check(receive_from) #This line will initiate timeout for the peer routers
                            self.remove_garbage_collection(receive_from) 
                        if receive_from in self.poison_collect:
                            self.poison_collect.append(receive_from)
                        resp_pkt, port = self.socket_list[i].recvfrom(RECV_BUFFSIZE)
                        checked_packet = self.is_packet_valid(resp_pkt, receive_from)
                        if  checked_packet == False:
                            print(f"Received packet from router {receive_from} failed validity check!\nDrop this packet....")
                        else:
                            self.response_pkt = resp_pkt
                            
                            print(f"----Received entries-----\n{checked_packet}")
                            self.update_entry(self.cur_table, checked_packet, receive_from)
                        
    def periodic_update(self):
        #Generates random float between [0.8*periodic time, 1.2*periodic time] and rounds to 2dp
        period = round(rand.uniform(0.8*self.timers['periodic'],1.2*self.timers['periodic']), 2) 
        threading.Timer(period, self.periodic_update).start()

        print(f"Periodic Update : Sending packet ...... ")
        self.send_packet()
                       
    def packet_exchange(self):
        try:
            while True:
                self.receive_packet()
                raise KeyboardInterrupt

        except KeyboardInterrupt:
            print('Keyboard Interrupted!')
        sys.exit(1)


if __name__ == "__main__":
    config = Config(sys.argv[1])
    config.unpack()
    print(config)
    
    router = Router(int(config.params['router-id'][0]), config.params['input-ports'], config.params['outputs'])
    rip_routing = Demon(router, config.params['timers'])
   
