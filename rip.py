import sys
import select
import socket
import threading
import random as rand
from threading import Timer, Lock


RECV_BUFFSIZE = 1024 

#___Class Config_____________________________________________________________________________________________________________________ 
class Config:
    """Config object initialised with argument string that is 
    the string representation of the config filepath for <obj> 
    as initialised object name and <param> as the paramter in correct format
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
    def __isMetricValid(self, metric):
        """ Checks if metric is in range of 1 <= metric <= 16"""
         #The metric field contains a value between 1 and 15 (inclusive) which
         #specifies the current metric for the destination; or the value 16
         #(infinity), which indicates that the destination is not reachable. 
         #----Referred from RFC 2453 - rip version 2
        return False if not (1<=metric<=16) else True

    def __isPortValid(self, port):
        """Checks if port is in range of 1024 <= port <= 64000
        returns True if in range and False otherwise"""
        return False if port < 1024 or port > 64000 else True
   
    def __isRouterIdValid(self, routerId):
        """Checks routerId is in range of 1 <= routerId <= 64000
        returns True if in range and False otherwise"""       
        return False if routerId < 1 or routerId > 64000 else True

    def __isOutputValid(self, value, inputs):
        is_output_wrong = False
        outputs, costs, peers, wrong_outputs = [], [], [], []
        wrong_costs, wrong_peers, duplicated_peer = [], [], []
        
        for line in value:
            if len(line.split("-"))!=3 or '' in line.split("-"):
                print("ERROR : ONE OF VALUES IS MISSING IN OUTPUTS ! UNABLE TO READ CONFIG")
                return sys.exit(1)
            else:
                output, cost, peer = int(line.split("-")[0]), int(line.split("-")[1]), int(line.split("-")[2])
                outputs.append(output) 
                if not self.__isPortValid(output):
                    is_output_wrong = True
                    wrong_outputs.append(output)
                costs.append(cost)
                if not self.__isMetricValid(cost):
                    is_output_wrong = True
                    wrong_costs.append(cost)
                peers.append(peer)
                if int(peer) == int(self.params["router-id"][0]) or len(list(peers)) !=  len(set(peers)):
                    is_output_wrong = True
                    duplicated_peer.append(peer)
                
                if not self.__isRouterIdValid(int(peer)):
                    is_output_wrong = True
                    wrong_peers.append(peer)

        #check if output port is not valid as there's an existing inputs with the same port number
        is_duplicated = [output for output in outputs if output in inputs]
        if len(is_duplicated) != 0:
            is_output_wrong = True
            print("ERROR : OUTPUT_PORT is duplicated\n\tExisting PORT_NUMBER : {} ".format(is_duplicated))
        if len(wrong_outputs) != 0:
            all_wrong_outputs = set(is_duplicated+wrong_outputs)
            print("ERROR : OUTPUT_PORT invalid\n\tWrong OUTPUT : {} ".format(list(all_wrong_outputs)))
        if len(wrong_costs) != 0:
            print("ERROR : METRIC invalid\n\tWrong METRIC : {} ".format(wrong_costs))
        if len(wrong_peers) != 0:
            if len(duplicated_peer) != 0:
                print("ERROR : PEER_ROUTER_ID is duplicated.\n\tExisting ROUTER_ID : {} ".format(duplicated_peer[0]))
            print("ERROR : PEER_ROUTER_ID invalid\n\tWrong PEER_ROUTER_ID : {} ".format(list(set(wrong_peers+duplicated_peer))))
        return is_output_wrong

    def _is_missing_value(self, config):
        is_missing = False
        for line in config:
            if line.split(' ', 1)[0] in self.params: 
                param = line.split(' ', 1)[0]
                value = line.split(' ', 1)[1].replace(' ', '').split(',')
                self.params[param] = value

        for param in self.params:
            try:
                if param == 'router-id':
                    if  self.params[param] == ['']:
                        print(f"MISSING PARAMETER {param.upper()}")
                        is_missing = True
                        raise ValueError
                    if len(self.params[param]) > 1:
                        print(f"ERROR : ROUTER ID IS NOT UNIQUE")
                        is_missing = True
                        raise ValueError
                if param == 'input-ports':
                    if len(self.params[param]) == [''] :
                        print(f"MISSING PARAMETER {param.upper()}")
                        is_missing = True
                        raise ValueError
                if param == 'outputs':
                    if len(self.params[param]) == [''] :
                        print(f"MISSING PARAMETER {param.upper()}")
                        is_missing = True
                        raise ValueError
                if len(self.params['outputs']) != len(self.params['input-ports']):
                    print(f"ERROR : The number of outputs and input-ports are not matched")
                    is_missing = True
                    raise ValueError
                        
            except(ValueError):
                print("ERROR : UNABLE TO READ CONFIG ! FILL OUT MISSING VALUES FIRST TO READ CONFIG FILE ")
                sys.exit(1)
        return is_missing

            
        
    def detailed_config_check(self):
        config_file = open(self.path, "r")
        config = config_file.read().split('\n')
        config_file.close()

        is_packet_valid = True
        if not self._is_missing_value(config):
            if not self.__isRouterIdValid(int(self.params["router-id"][0])):
                is_packet_valid = False
                print("ERROR : ['ROUTER-ID'] invalid\n\tWrong ROUTER_ID : {}".format(self.params['router-id']))
            
            wrong_inputs = [int(port) for port in self.params['input-ports'] if not self.__isPortValid(int(port))]
            if len(wrong_inputs) != 0:
                is_packet_valid = False
                print(f"ERROR : ['INPUT-PORTS'] invalid\n\tWrong INPUT_PORT : {wrong_inputs} ")

            is_output_invalid = self.__isOutputValid(self.params['outputs'], self.params['input-ports'])
            if is_output_invalid:
                is_packet_valid = False
                print("ERROR : ['OUTPUTS'] contain invalid values")

            if not is_packet_valid :
                print("UNABLE TO READ CONFIG")
                sys.exit(1)
        else:
            sys.exit(1)
        

#___Class Router_____________________________________________________________________________________________________________________ 

class Router:
    """For this router to have its own information based on config file"""
    def __init__(self,  rtrId, inputs, outputs):
        
        self.rtr_id = int(rtrId) # of type int
        self.inputs = [int(input_port) for input_port in inputs] # list of input ports
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
        for i in range(len(entry)):
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
                    #filter entry with known information to peer router
                    filtered[dest] = self.cur_table[dest]
        return self.rip_response_packet(self.compose_rip_entry(filtered))
   
    def send_packet(self):
        peer = self.router.neighbor
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sending_socket:
                for i in range(len(peer)):
                    port = list(peer.values())[i]['output']
                    peer_rtr = list(peer)[i]
                    #customized_packet for each output
                    customized_pkt = self.split_horizon_with_poison_reverse(peer_rtr, port)
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
        """To detect timeout for peer router and all reachable route via peer router"""
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
        command = int.from_bytes(packet[0:1], "big")
        version = int.from_bytes(packet[1:2], "big") 
        rtr_id_as_ip_addr = int.from_bytes(packet[2:4], "big") 
        is_valid = True
        #When Packet Size is wrong
        if len(packet)%4 != 0 or not (24<=len(packet)<=504): 
            is_valid = False
            print("Packet Invalid : Packet Size is wrong")
            if len(packet)<20:
                print("Error : Packet Size is too small")
                print("Rip entry should be at least more than one\n")
            if len(packet)>504:
                print("Error : Packet Size is too Big")
                print("Rip entries can be contained at most 25\n")
            return False

        if command != 2: #command should be 2
            is_valid = False
            print("Packet Invalid [Common Header] : Wrong value for command")
        if  version != 2: #version should be 2
            is_valid = False
            print("Packet Invalid [Common Header] : Wrong value for version")
        if not (1 <= rtr_id_as_ip_addr <= 64000) :#This should be in range of 1 <= x <= 64000
            is_valid = False
            print("Packet Invalid [Common Header] : Wrong value for router id")

        for i in range((len(packet)-4)// 20):
            afi = (int.from_bytes(packet[4+20*i:6+20*i], "big"))
            must_be_zeros = int.from_bytes(packet[6+20*i:8+20*i], "big") 
            must_be_zeros += int.from_bytes(packet[12+20*i:20+20*i], "big")
            dest_id = int.from_bytes(packet[(8+20*i):(12+20*i)], "big")
            metric= int.from_bytes(packet[(20+20*i):(24+20*i)], "big") 
            if afi != 0: #afi should be 0
                is_valid = False
                print(f"Packet Invalid [Rip entry {i}] : Wrong value for address family identifier")
            if must_be_zeros != 0 : 
                is_valid = False
                print(f"Packet Invalid [Rip entry {i}] : Wrong value for must_be_zero field")
            if not (1 <= dest_id <= 64000): #This should be in range of 1 <= x <= 64000
                is_valid = False
                print(f"Packet Invalid [Rip entry {i}] : Wrong value for destination router id")
            #metric should be between 1 to 16 
            #but before calculating new metric for connected peer router,
            #peer can send entry itself with metric 0
            if not (0 <= metric <= 15): 
                if  metric == 16:
                    # send this entry to garbage_collection for generating poison
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
        self.timeouts[dst_id] = Timer(self.timers['timeout'], lambda: self.timer_garbage_collection(dst_id))
        self.timeouts[dst_id].start()

    def timer_garbage_collection(self, dst_id):
        """Used for adding a Timer thread object that will 
        eventually call entry_remove(dst_id) for a given dst_id"""
        if self.timeouts.get(dst_id, None):
            self.timeouts[dst_id].cancel()
            del self.timeouts[dst_id]
        
        if not self.garbage_collects.get(dst_id, None) :
            if dst_id != self.router.rtr_id:
                self.entry_timeout(dst_id) #generate poison entry
                print(f"Route for reaching * ROUTER {dst_id} * crashed!")
                self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)
                print("TRIGGERED UPDATE : Due to unreachable route detection!")
                self.send_packet()
                self.garbage_collects[dst_id] = Timer(self.timers['garbage-collection'], lambda: self.entry_remove(dst_id))
                self.garbage_collects[dst_id].start()

    def timer_remove_garbage_collection(self, dst_id):
        """Used for removing the Timer thread object that will 
        eventually call entry_remove(dst_id) for a given dst_id"""
        if self.garbage_collects.get(dst_id, None) :
            self.garbage_collects[dst_id].cancel()
            self.timer_status[dst_id] = "         "
            del self.garbage_collects[dst_id]

    #_____Update and entry process_______________________________________________________________________________________

    def update_periodic(self):
         #Generates random float between [0.8*periodic time, 1.2*periodic time] and rounds to 2dp
        period = round(rand.uniform(0.8*self.timers['periodic'],1.2*self.timers['periodic']), 2)
        threading.Timer(period, self.update_periodic).start()

        print(f"Periodic Update : Sending packet ...... ")
        self.send_packet()
                       
    def entry_update(self, new_entry, receive_from):
        link_cost = self.router.neighbor[receive_from]['cost']

        for new_dst in new_entry:
            new_metric = new_entry[new_dst]['metric'] + link_cost
            if new_metric <=15: # Only deal with entries that are not poisoned
                if (new_dst not in self.cur_table): # if new_dst not in current_table
                    self.route_change_flags[new_dst] = True
                    self.timer_status[new_dst] = '         '
                    print(f"******NOTICE : NEW ROUTE FOUND : ROUTER {new_dst} IS REACHABLE******" )
                    self.cur_table = self.router.add_entry(self.cur_table, new_dst, receive_from, new_metric)

                else : # if new_dst in current_table      
                    self.route_change_flags[new_dst] = False
                    if (new_metric < self.cur_table[new_dst]['metric']):
                        if self.timer_status[new_dst] != "TIMED_OUT":
                            self.route_change_flags[new_dst] = True
                            print(f"******NOTICE : BETTER ROUTE FOUND FOR ROUTER******")
                            print(f"ROUTE {new_dst} : cost reduced from {self.cur_table[new_dst]['metric']} to {new_metric}")
                            self.cur_table = self.router.modify_entry(self.cur_table, new_dst, receive_from, new_metric)           
                                    
        self.response_pkt = self.rip_response_packet(self.compose_rip_entry(self.cur_table))
        self.entry_unreachable(receive_from)

        print(f"----Updated Table--------")
        self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)
    
    def entry_unreachable(self, receive_from):
        """Remove entries containing unreachable route with metric more than 16"""
        #This is for removing entries with metric over 15 by pure link calculation
        #But the poisoned entries are not removed as they have to be sent to peers
        for dst in self.cur_table.copy():
            if self.timer_status[dst] == "TIMED_OUT":
                self.route_change_flags[dst] = True
            if self.timer_status[dst] != "TIMED_OUT" and self.cur_table[dst]['metric']>15:
                if dst != self.router.rtr_id:
                    print(f"Route to {dst} via {receive_from} is unreachable")
                    self.cur_table.pop(dst) 
               
        self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)

    def entry_timeout(self, dst_id):
        """Set timeout entries for showing timed_out situation in routing table"""
        if dst_id in self.cur_table :
            self.cur_table[dst_id]['metric'] = 16
            self.timer_status[dst_id]= "TIMED_OUT"
            self.route_change_flags[dst_id] = True 

    def entry_remove(self, dst_id):
        if self.garbage_collects.get(dst_id, None):
            del self.garbage_collects[dst_id]
            
        if self.cur_table.get(dst_id, None) and dst_id != self.router.rtr_id:
            print(f"Remove entry for * Route {dst_id} * ")
            self.cur_table.pop(dst_id)

            print_lock = threading.Lock()
            print_lock.acquire()
            self.timer_remove_garbage_collection(dst_id)
            self.router.display_table(self.cur_table, self.route_change_flags, self.timer_status)
            print_lock.release()


if __name__ == "__main__":
    config = Config(sys.argv[1])
    config.detailed_config_check()
    print(config)
    
    router = Router(int(config.params['router-id'][0]), config.params['input-ports'], config.params['outputs'])
    rip_routing = Demon(router, config.params['timers'])
