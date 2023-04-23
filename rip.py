import sys
import select
import socket
import random as rand
from threading import Timer, Lock
import threading

RECV_BUFFSIZE = 1024 

#___Class Config_____________________________________________________________________________________________________________________ 
class Config:
    """Config object initialised with argument string that is the string representation
    of the config filepath for <obj> as initialised object name and <param> as the paramter in correct format
    each parameter's value can be accessed by <obj>.params["<param>"] and will give
    a list of string representation of the value/s """
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
        is_wrong_value = False
         
        for line in config:
            #checks if line is even worth further parsing ie. is a parameter line
            if line.split(' ', 1)[0] in self.params:   
                #parses the line, param is a string and value is a list of strings
                param = line.split(' ', 1)[0]
                value = line.split(' ', 1)[1].replace(' ', '').split(',')
                try:
                    #error handles
                    if not value:
                        #no value
                        raise IndexError
                except(IndexError):
                    is_wrong_value = True
                    print("PARAMETER <{}> MISSING VALUES. PLEASE CHECK CONFIG".format(param))
                else:
                    try:
                        if param == "router-id":
                            if not self.__isRouterIdValid(int(value[0])):
                                #router-id is out of range
                                raise ValueError
                    except(ValueError):
                        is_wrong_value = True
                        print("PARAMETER <{}> INVALID VALUE. PLEASE CHECK CONFIG".format(param))

                    else:
                        try:
                            if param == "input-ports":
                                for port in value:
                                    if not self.__isPortValid(int(port)):
                                        #input-ports is out of range
                                        raise ValueError
                        except(ValueError):
                            is_wrong_value = True
                            print("PARAMETER <{}> INVALID VALUE. PLEASE CHECK CONFIG".format(param))
                        else:
                            try:
                                if param == "outputs":
                                    for output in value:
                                        parsed = output.split("-")
                                        if not self.__isRouterIdValid(int(parsed[2])):
                                            #output router id is out of range
                                            raise ValueError
                                        if not self.__isPortValid(int(parsed[0])):
                                            #output port is out of range
                                            raise ValueError
                            except(ValueError):
                                is_wrong_value = True
                                print("PARAMETER <{}> INVALID VALUE. PLEASE CHECK CONFIG".format(param))
                            else:

                                #inserts the value in config file as the value for params dict for given key: param
                                self.params[param] = value
                    
        #checks for missing required parameters by finding if any of the required fields are still None
        for param in self.params:
            try:
                if self.params[param] == None and param not in self.__req_params:
                    raise TypeError
            except(TypeError):
                is_wrong_value = True
                if param != 'timers':
                    print("Error : Config Validity check failed! <{}> is MISSING or not VALID! ".format(param))
        if is_wrong_value :
            sys.exit(1)

#___Class Router_____________________________________________________________________________________________________________________ 

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

#___Class Demon_____________________________________________________________________________________________________________________ 

class Demon:
    def __init__(self, Router, timers=None):
        if timers:
            self.timers = {'periodic':int(timers[0]),'timeout':int(timers[1]), 'garbage-collection':int(timers[2])}   
        else:
            self.timers = {'periodic':1, 'timeout':6, 'garbage-collection':4}
        self.router = Router
        self.tick = 0
        self.route_change_flags = {self.router.rtr_id: False}
        self.timer_status = {self.router.rtr_id: "         "}
        self.timeouts, self.garbage_collects = {}, {}
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
                #not filtering entry as it has to be sent to peer router 
                filtered[dest] = self.cur_table[dest] 
            else:
                #split_horizon
                if (self.cur_table[dest]['next-hop'] != peer_rtr and dest != peer_rtr) :
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
                        print(f'\nReceived packet from ROUTER {receive_from}')
                        self.detect_timeout(receive_from)                  
                        resp_pkt, port = self.socket_list[i].recvfrom(RECV_BUFFSIZE)
                        checked_packet = self.is_packet_valid(resp_pkt, receive_from)
                        if  checked_packet:
                            self.response_pkt = resp_pkt
                            self.entry_update(checked_packet, receive_from)
                        else:
                            print(f"Received packet from router {receive_from} failed validity check!")
                            print("Drop this packet....")
                            
    def detect_timeout(self, receive_from):
        if receive_from != self.router.rtr_id:
            self.timer_timeout(receive_from) 
            for reachable in self.cur_table.copy():
                if reachable != self.router.rtr_id:
                    if reachable in self.cur_table:
                        if self.cur_table[reachable]['next-hop'] == receive_from:
                            self.timer_timeout(reachable)
 

    def is_packet_valid(self, packet, receive_from):
        """Check if the received packet is valid return packet contents if True else return False """
        entry = {}
        command = int.from_bytes(packet[0:1], "big") #command should be 2
        version = int.from_bytes(packet[1:2], "big") #version should be 2
        rtr_id_as_ip_addr = int.from_bytes(packet[2:4], "big") #This should be in range of 1024 <= x <= 64000
        is_valid = True

        if len(packet)%4!= 0 or not (24<=len(packet)<=504): #When Packet Size is wrong
            is_valid = False
            print("Packet Invalid : Packet Size is wrong")
            if len(packet)<20:
                print("Error : Packet Size is too small")
                print("Rip entry should be at least more than one\n")
            if len(packet)>504:
                print("Error : Packet Size is too Big")
                print("Rip entries can be contained at most 25\n")
            return False
        if command != 2:
            is_valid = False
            print("Packet Invalid [Common Header] : Wrong value for command")
        if  version != 2:
            is_valid = False
            print("Packet Invalid [Common Header] : Wrong value for version")
        if not (1 <= rtr_id_as_ip_addr <= 64000) :
            is_valid = False
            print("Packet Invalid [Common Header] : Wrong value for router id")

        for i in range((len(packet)-4)// 20):
            afi = (int.from_bytes(packet[4+20*i:6+20*i], "big"))#afi should be 0
            must_be_zeros = ( int.from_bytes(packet[6+20*i:8+20*i], "big") +  int.from_bytes(packet[12+20*i:20+20*i], "big") ) 
            dest_id = int.from_bytes(packet[(8+20*i):(12+20*i)], "big")#This should be in range of 1024 <= x <= 64000
            metric= int.from_bytes(packet[(20+20*i):(24+20*i)], "big") #This should be in range of 0 <= x <= 15
            if afi != 0:
                is_valid = False
                print(f"Packet Invalid [Rip entry {i}] : Wrong value for address family identifier")
            if must_be_zeros != 0 :
                is_valid = False
                print(f"Packet Invalid [Rip entry {i}] : Wrong value for must_be_zero field")
            if not (1 <= dest_id <= 64000):
                is_valid = False
                print(f"Packet Invalid [Rip entry {i}] : Wrong value for destination router id")
            if not (0 <= metric <= 15):
                if 20 > metric > 15:
                    self.timer_garbage_collection(dest_id)
                else:
                    flag = False
                    print(f"Packet Invalid [Rip entry {i}] : Wrong value for metric")

            entry[dest_id] = {'next-hop': receive_from, 'metric': metric} 
        return entry if is_valid else False

    def packet_exchange(self):
        try:
            while True:
                self.receive_packet()
                raise KeyboardInterrupt

        except KeyboardInterrupt:
            print('Keyboard Interrupted!')
        sys.exit(1)

    #_____Timer Event_______________________________________________________________________________________

    def timer_timeout(self, dst_id):
        """ For a given dst_id, it either adds a new Timer thread object 
        that will eventually call timer_garbage_collection(dst_id) OR 'Refreshes' the timer 
        for given dst_id in self.timeouts dictionary by creating a new Timer thread object"""    
        if self.timeouts.get(dst_id, None):
            self.timeouts[dst_id].cancel()
            del self.timeouts[dst_id]
        else:
            self.timeouts[dst_id] = Timer(self.timers['timeout'], lambda: self.timer_garbage_collection(dst_id))
            self.timeouts[dst_id].start()

    def timer_garbage_collection(self, dst_id):
        """Used for adding a Timer thread object that will eventually call entry_remove(dst_id) for a given dst_id"""
        if self.timeouts.get(dst_id, None):
            self.timeouts[dst_id].cancel()
            del self.timeouts[dst_id]
        
        if not self.garbage_collects.get(dst_id, None) :
            if dst_id != self.router.rtr_id:
                self.entry_timeout(dst_id)
                for reachable in self.cur_table:
                    if reachable != self.router.rtr_id:
                        if self.cur_table[reachable]['next-hop'] == dst_id:
                            self.entry_timeout(reachable)
                            self.tick = 0
                print(f"Route for reaching * ROUTER {dst_id} * crashed!")
                self.send_packet()
                self.garbage_collects[dst_id] = Timer(self.timers['garbage-collection'], lambda: self.entry_remove(dst_id))
                self.garbage_collects[dst_id].start()

    def timer_remove_garbage_collection(self, dst_id):
        """Used for removing the Timer thread object that will eventually call entry_remove(dst_id) for a given dst_id"""
        if self.garbage_collects.get(dst_id, None) :
            self.garbage_collects[dst_id].cancel()
            self.timer_status[dst_id] = "         "
            del self.garbage_collects[dst_id]

    #_____Update and entry process_______________________________________________________________________________________

    def update_periodic(self):

        period = round(rand.uniform(0.8*self.timers['periodic'],1.2*self.timers['periodic']), 2) #Generates random float between [0.8*periodic time, 1.2*periodic time] and rounds to 2dp
        threading.Timer(period, self.update_periodic).start()

        print(f"Periodic Update : Sending packet ...... ")
        self.send_packet()
                       
    def entry_update(self, new_entry, receive_from):
        link_cost = self.router.neighbor[receive_from]['cost']
        better_path = False

        for new_dst in new_entry:
            new_metric = new_entry[new_dst]['metric'] + link_cost
            if (new_dst not in self.cur_table): # if new_dst not in current_table
                if new_entry[new_dst]['metric'] <= 15:
                    self.route_change_flags[new_dst] = True
                    self.timer_status[new_dst] = '         '
                    print(f"******NOTICE : NEW ROUTE FOUND : ROUTER {new_dst} IS REACHABLE******" )
                    self.cur_table = self.router.add_entry(self.cur_table, new_dst, receive_from, new_metric)

            else : # if new_dst in current_table      
                self.route_change_flags[new_dst] = False
                if (new_metric < self.cur_table[new_dst]['metric']) and new_metric <=15:
                    if self.timer_status[new_dst] != "TIMED_OUT":
                        better_path = True
                        self.route_change_flags[new_dst] = True
                        print(f"******NOTICE : BETTER ROUTE FOUND FOR ROUTER******")
                        print(f"ROUTE {new_dst} : cost reduced from {self.cur_table[new_dst]['metric']} to {new_metric}")
                        self.cur_table = self.router.modify_entry(self.cur_table, new_dst, receive_from, new_metric)           
                                    
        self.response_pkt = self.rip_response_packet(self.compose_rip_entry(self.cur_table))
        self.entry_unreachable(receive_from)

        if better_path :
            print("Triggered update : Send packets due to the route change")
            self.send_packet()
        print(f"----Updated Table--------")
        self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)
    
    def entry_unreachable(self, receive_from):
        """Remove entries containing unreachable route with metric more than 16"""
        self.tick += 1
        if self.tick >=self.timers['garbage-collection']+2:
            for dst in self.cur_table.copy():
                if self.timer_status[dst] == "TIMED_OUT" and dst != self.router.rtr_id and not self.garbage_collects.get(dst, None):
                    print(f"Route to {dst} via {receive_from} is unreachable")
                    self.cur_table.pop(dst) 
                    self.tick = 0
            
        for dst in self.cur_table.copy():
            if self.timer_status[dst] != "TIMED_OUT" and self.cur_table[dst]['metric']>15 and dst != self.router.rtr_id:
                print(f"Route to {dst} via {receive_from} is unreachable")
                self.cur_table.pop(dst) 
        
               
        self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)

    def entry_timeout(self, dst_id):
        if dst_id in self.cur_table:
            self.cur_table[dst_id]['metric'] = 16
            self.timer_status[dst_id]= "TIMED_OUT"
            self.route_change_flags[dst_id] = True 

    def entry_remove(self, dst_id):
        if self.garbage_collects.get(dst_id, None):
            del self.garbage_collects[dst_id]
            
        if self.cur_table.get(dst_id, None) and dst_id != self.router.rtr_id:
            print(f"Remove entry for * Route {dst_id} * ")
            self.cur_table.pop(dst_id)
            self.tick = 0
            
            print_lock = threading.Lock()
            print_lock.acquire()
            self.timer_remove_garbage_collection(dst_id)
            self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)
            print_lock.release()


if __name__ == "__main__":
    config = Config(sys.argv[1])
    config.unpack()
    print(config)
    
    router = Router(int(config.params['router-id'][0]), config.params['input-ports'], config.params['outputs'])
    rip_routing = Demon(router, config.params['timers'])
