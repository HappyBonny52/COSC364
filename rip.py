#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
import select
import socket
import random as rand
from threading import Timer
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
             timers: {4}""".format(self.path, self.params['router-id'],
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
        self.inputs = [input_port for input_port in inputs] #list
        self.output = self.decompose_output(outputs) #list
        self.outputs = self.output[0] #list
        self.metrics = self.output[1] #list
        self.peer_rtr_id = self.output[2] #list
        
    
    def decompose_output(self, outputs):
        """split output format by '-' and sort by each item into list
        # output format [peer's_input_port - metric(link cost) - peer's router id (peer's_input_port is equal to current router's output_port)]"""
        #split output by '-'
        split_output = [outputs[i].split('-') for i in range(len(outputs))] 

        ports, metrices, peer_rtr_ids = [], [], []
        for i in range(len(split_output)):
            ports.append(int(split_output[i][0]))
            metrices.append(int(split_output[i][1]))
            peer_rtr_ids.append(int(split_output[i][2]))
        
        return [ports, metrices, peer_rtr_ids]

class Demon:
    def __init__(self, Router, timers=None):
        """Initialize Demon with input ports for creating UDP sockets 
        <socket_list> : list of binded sockets indexed in its corresponding input port
        """
        self.router = Router
        self.socket_list = self.create_socket()
        self.timeouts = {}
        self.garbage_collects = {}        
        if timers:
            self.timers = {'periodic':int(timers[0]),'timeout':int(timers[1]), 'garbage-collection':int(timers[2])}   
        else:
            self.timers = {'periodic':6, 'timeout':36, 'garbage-collection':24}
        
        self.posion_reverse_collects = []
        self.cur_table = [{ 'dest' : self.router.rtr_id, 'next-hop' : self.router.rtr_id,  'metric' : 0}]
        self.response_pkt = self.rip_response_packet(self.compose_rip_entry(self.cur_table))
  
        self.display_table(self.cur_table)
        self.periodic_update()
        self.packet_exchange()

    def create_socket(self):
        """Creating UDP sockets and to bind one with each of input_port"""
        socket_list = []
        for i in range(len(self.router.inputs[i])):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind('127.0.0.1', int(self.router.inputs[i])) #bind with local host
            socket_list.append(sock)
        return socket_list
        
    def remove_entry(self, dst_id):
        """Simply removes the first entry with matching dst_id field"""
        del self.garbage_collects[dst_id]
        for i in range(len(self.cur_table)):
            if self.cur_table[i]['dest'] == dst_id:
                del self.cur_table[i]
                break
        print("Removed entry for destRtrId: ", dst_id)
        self.display_table(self.cur_table)
    
    def remove_garbage_collection(self, dst_id):
        """Used for removing the Timer thread object that will eventually call remove_entry(dst_id) for a given dst_id"""
        if self.garbage_collects.get(dst_id, None) :
            self.garbage_collects[dst_id].cancel()
            del self.garbage_collects[dst_id]
    
    def garbage_collection(self, dst_id):
        """Used for adding a Timer thread object that will eventually call remove_entry(dst_id) for a given dst_id"""
        del self.timeouts[dst_id]
        if not self.garbage_collects.get(dst_id, None):
            for i in range(len(self.cur_table)):
                if self.cur_table[i]['dest'] == dst_id:
                    self.cur_table[i]['metric'] = 16
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
        display = f"\nRouting table of router {self.router.rtr_id}\n"
        display += '+-----------------------------------------------------------------------+\n'
        display += '|  Destination  |  Next-hop  |  Cost  |  Route Change Flag  |   Timer   |\n'
        display += '+-----------------------------------------------------------------------+\n'
        for i in range(len(contents)):
            space = '  ' if contents[i]['metric'] < 10 else ' ' #For drawing tidy table
            display += "|    router {0}   |  router {1}  |   {2}{3}  |                     |           |\n".format(contents[i]['dest'],
                                                                                                         contents[i]['next-hop'],
                                                                                                         contents[i]['metric'],
                                                                                                         space)
        display += '+-----------------------------------------------------------------------+\n'
        print(display)
        
    def generate_table_entry(self, entry):
        content = []
        dest, next_hop, metrics = entry[0], entry[1], entry[2]
        for i in range(len(entry[0])):
            content.append({'dest' : dest[i], 'next-hop' : next_hop[i], 'metric' : metrics[i]})
        return content

    def update_entry(self, current_table, new_entry, receive_from):
        update = current_table
        link_cost = self.router.metrics[self.router.peer_rtr_id.index(receive_from)]
        dests = [update[i]['dest'] for i in range(len(update))]
        better_path = False

        for i in range(len(new_entry)):
            if (new_entry[i]['dest'] not in dests) and (new_entry[i]['dest'] != self.router.rtr_id):
                print("INSIDE 1ST IF: ", new_entry[i]['dest'])
                self.timeout_check(new_entry[i]['dest'])
                self.remove_garbage_collection(new_entry[i]['dest'])
                new = self.modify_entry(new_entry[i], link_cost, receive_from)
                update.append(new)

            elif (new_entry[i]['dest'] in dests):
                if new_entry[i]['dest'] != self.router.rtr_id:
                    print("INSIDE 2ND IF: ", new_entry[i]['dest'])
                    self.timeout_check(new_entry[i]['dest'])
                    self.remove_garbage_collection(new_entry[i]['dest'])
                if (new_entry[i]['metric'] + link_cost) < update[dests.index(new_entry[i]['dest'])]['metric']:
                    better_path = True
                    obsolete = update[dests.index(new_entry[i]['dest'])]
                    update.remove(obsolete)
                    new = self.modify_entry(new_entry[i], link_cost, receive_from)
                    update.append(new)
                    
        self.cur_table = update
        self.response_pkt = self.rip_response_packet(self.compose_rip_entry(self.cur_table))
        if better_path :
            print("Triggered update : Send packets due to the route change")
            self.send_packet()
        self.display_table(self.cur_table)
        return update

    def modify_entry(self, entry, cost, receive_from):
        entry['next-hop'] = receive_from
        entry['metric'] += cost 
        return entry
        
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
        
        for i in range(len(entry)): #the item in range() will be replaced by lists of list entry contents
            #first 32 bits of rip entry
            rip_entry += afi.to_bytes(2, 'big')
            rip_entry += must_be_zero.to_bytes(2, 'big')
            # second to fifth of rip entry
            rip_entry += entry[i]['dest'].to_bytes(4, 'big')
            rip_entry += must_be_zero.to_bytes(4, 'big')
            rip_entry += must_be_zero.to_bytes(4, 'big')
            rip_entry += entry[i]['metric'].to_bytes(4, 'big')
        return rip_entry
   
    def send_packet(self):
        #randomized periodic update for sending packet
        #i used this for debugging timers -david
        """
        self.display_table(self.cur_table)
        print(threading.enumerate())
        print(self.timeouts)
        print(self.garbage_collects)"""

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sending_socket:
                for i in range(len(self.router.outputs)):
                    customized_packet = self.split_horizon_with_poison_reverse(self.cur_table, self.router.outputs[i]) #customized_packet for each output
                    sending_socket.sendto(customized_packet, ('127.0.0.1', self.router.outputs[i])) 

    def split_horizon_with_poison_reverse(self, table, port):
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
        peer_rtr = self.router.peer_rtr_id[self.router.outputs.index(port)] 
        filtered = []
        for i in range(len(table)):
            if table[i]['metric'] > 15: #posion_reverse
                filtered.append(table[i]) #not filtering entry as it has to be send to peer router 
            else:
                if ((table[i]['next-hop'] and table[i]['dest']) != peer_rtr):#split_horizon
                    filtered.append(table[i]) #filtered entry from if condition is added to the rip entry for packet
        return self.rip_response_packet(self.compose_rip_entry(filtered))
    
    def is_packet_valid(self, packet):
        #===========================================================================#
        #__________________Codes here need to be cleaned____________________________#
        #____________Coded Roughly in order to implement poison reverse_____________#
        #___________________________________________________________________________#
        #===========================================================================#
        dest_ids, next_hops, metrics = [], [], []
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
            if not (0 <= metric <= 15):
                if metric > 15:
                    self.posion_reverse_collects.append(rtr_id_as_ip_addr)
                else :
                    flag = False
                    print("Packet Invalid : Wrong value of metric")


            dest_ids.append(dest_id)
            next_hops.append(rtr_id_as_ip_addr)
            metrics.append(metric)

        return [dest_ids, next_hops, metrics] if is_valid else False

    def receive_packet(self):
        while True:
            read_socket_lis, _, _ = select.select(self.socket_list, [], [])
            for read_socket in read_socket_lis:
                for i in range(len(self.router.inputs)):
                    receive_from = self.router.peer_rtr_id[i]
                    if read_socket == self.socket_list[i]:
                        print(f'\nReceived packet from router {self.router.peer_rtr_id[i]}')
                        if self.router.peer_rtr_id[i] != self.router.rtr_id:
                            print("INSIDE RECIEVE_PACKET: ", self.router.peer_rtr_id[i])
                            self.timeout_check(self.router.peer_rtr_id[i]) #This line will initiate timeout for the peer routers
                        resp_pkt, port = self.socket_list[i].recvfrom(RECV_BUFFSIZE)
                        print(f"This is the port I received : {port}")
                        checked_packet = self.is_packet_valid(resp_pkt)
                        if  checked_packet == False:
                            print(f"Received packet from router {receive_from} failed validity check!\nDrop this packet....")
                        else:
                            self.response_pkt = resp_pkt
                            new_content = self.generate_table_entry(checked_packet)
                            print(f"----Received entries----\n{new_content}")
                            self.update_entry(self.cur_table, new_content, receive_from)
                        
    def periodic_update(self):

        period = round(rand.uniform(0.8*self.timers['periodic'],1.2*self.timers['periodic']), 2) #Generates random float between [0.8*periodic time, 1.2*periodic time] and rounds to 2dp
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
   