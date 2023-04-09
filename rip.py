#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
import select
import socket
import datetime 
from threading import Timer

RECV_BUFFSIZE = 1024
start = True
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
        
      
class RoutingInformation:
     def __init__(self, router_id, input_ports, output_port_list, metric_list, peer_rtr_id_list, hop_list, timer):
        self.routerID = int(router_id)

        self.input_ports =[int(input_port) for input_port in input_ports]

        self.timers = 0
        self.hop = 0
        self.hop_list = hop_list
        self.output_port_list = output_port_list
        self.metric_list = metric_list
        self.peer_rtr_id_list = peer_rtr_id_list
        if start == True:
            self.current_contents = self.generate_table_entry()
            RoutingTable(self.current_contents, [])
        else:
            RoutingTable(self.current_contents, self.add_received_info())

     def hop_count(self, port, hop):
        return hop+1

     def generate_table_entry(self):
         routing_table_entry_lis = []
         for i in range(len(self.output_port_list)):
             routing_table_entry_lis.append([self.routerID, self.peer_rtr_id_list[i], self.input_ports[i], self.output_port_list[i], self.metric_list[i], self.hop_list[i], self.timers])
         return routing_table_entry_lis

     def add_received_info(self, entry):
         for i in range(len(self.output_port_list)):
             entry.append([self.routerID, self.peer_rtr_id_list[i], self.input_ports[i], self.output_port_list[i], self.metric_list[i], self.hop_list[i], self.timers])
         return entry

class RoutingTable:
    """ Temp skeleton of routing table entry """
    def __init__(self, contents, newEntry):
        self.contents = contents
        self.new_entry = newEntry
        #Print out routing information just for checking 
        #(This area will be triggered by timer or update event after implementation of timer/updateEvent)
        print(f"\nRouting Information of router {self.contents[0][0]}\n")
        print(self.__str__())
        #________________________________________________________________________________________________

    def __str__(self):
        output = "Routing table-------------------------------------------------------------------------+\n"
        for i in range(len(self.contents)):
            output += "|destRtrId: {0}  |  port: {1} (connected to outputport {2})  |  cost: {3}  |  hop : {4}  |\n".format(self.contents[i][1],
                                                                                         self.contents[i][2],
                                                                                         self.contents[i][3],
                                                                                         self.contents[i][4],
                                                                                         self.contents[i][5]
                                                                                         )
        output += '+-------------------------------------------------------------------------------------+\n'
        return output
            
    def addEntry(self, entry):
        self.contents.append(self.new_entry)
        
    def removeLastEntry(self):
        self.contents.pop()
        
    def removeEntry(self, index):
        self.contents.pop(index)
    
    def removeSpecificEntry(self, entry):
        self.contents.remove(entry)
     
def bellmanFord(vertices, edges, source):
    """
    BellmanFord algorithm implemented with the definition from Wikipedia:
    https://en.wikipedia.org/wiki/Bellman%E2%80%93Ford_algorithm
    
    This implementation does not consider the possibility of negative weight cycles
    as negative weight would not be possible in a routing context.
    
    takes arguments:
    
    <vertices> : array of length N, where N is the number of vertex in graph, only used for counting purposes so the values don't actually matter
    <edges> : array of (u, v, w) tuples representing edges
    <source> : source vertex index
    returns arrays distance and predecessor
    
    <distance> : the index of each element represents the vertex index and the value of each element represents the total weight to reach that vertex from source
    <predecessor> : the index of each element represents the vertex index and the value of each element represents the vertex index of the least weight to reach the vertex
    
    """
    distance = [ float('inf') for i in range(len(vertices))]
    predecessor = [ None for i in range(len(vertices))]
    distance[source] = 0
    
        
    for i in range(len(vertices) - 1):
        for edge in edges:
            u, v, w = edge
            if distance[u] + w < distance[v]:
                distance[v] = distance[u] + w
                predecessor[v] = u
                        
    return distance, predecessor


class Demon:
    def __init__(self,  RoutingInformation):
        """Initialize Demon with input ports for creating UDP sockets 
        <input_port_list> : tuple form of ('', input port) for binding
        
        <socket_list> : list of binded sockets indexed in its corresponding input port
        """
        self.routerID = RoutingInformation.routerID
        self.input_ports = RoutingInformation.input_ports
        self.output_port_list = RoutingInformation.output_port_list
        self.hop_list = RoutingInformation.hop_list
        self.metric_list = RoutingInformation.metric_list
        self.peer_rtr_id_list = RoutingInformation.peer_rtr_id_list
        self.socket_list = self.create_socket()
        self.response_pkt = self.generate_rip_response_packet(self.compose_rip_entry())
        self.info_exchange_to_neighbors()
        self.response_msg = None

    
    def create_socket(self):
        """Creating UDP sockets and to bind one with each of input_port"""
        input_port_addr = [('', int(input_port)) for input_port in self.input_ports]
        socket_list = []
        for i in range(len(input_port_addr)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(input_port_addr[i])
            socket_list.append(sock)
        return socket_list

    def generate_rip_response_packet(self, rip_entry):
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
        command, version, must_be_zero_as_rtr_id = 2, 2, self.routerID
   
        #create bytearray for response_packet
        response_pkt_bytearray = bytearray()

        #adding common header into response_packet(bytearray)
        response_pkt_bytearray += command.to_bytes(1, 'big')
        response_pkt_bytearray += version.to_bytes(1, 'big')
        response_pkt_bytearray += must_be_zero_as_rtr_id.to_bytes(2,'big')
        #adding rip entry into response_packet(bytearray)
        response_pkt_bytearray += rip_entry
        return response_pkt_bytearray

    def compose_rip_entry(self):
        """
        #   RIP ENTRY FORMAT
        #+--------------------------------------------------------------+
        #|  address family identifier(2 bytes) + must be zero (2 bytes) |
        #|                   IPv4 address (4 bytes)                     |
        #|                   Subnet Mask (4 bytes)                     |
        #|                   must be zero (4 bytes)                     |
        #|                       metric(4 bytes)                        |
        #+--------------------------------------------------------------+
        #The number of rip entry can be up to 25(including)
        """

        entry_bytearray = bytearray()
        address_family_identifier = 2
        must_be_zero = 0
        
        for i in range(len(self.output_port_list)): #the item in range() will be replaced by lists of list entry contents
            #first 32 bits of rip entry
            entry_bytearray += address_family_identifier.to_bytes(2, 'big')
            entry_bytearray += must_be_zero.to_bytes(2, 'big')
            # second to fifth of rip entry
            entry_bytearray += self.peer_rtr_id_list[i].to_bytes(4, 'big')
            entry_bytearray += must_be_zero.to_bytes(4, 'big')
            entry_bytearray += self.output_port_list[i].to_bytes(4, 'big')
            entry_bytearray += f"{self.metric_list[i]}--{self.hop_list[i]}".encode('utf-8')
        return entry_bytearray

    def send_packet(self):
        Timer(7, self.send_packet).start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sending_socket:
                for i in range(len(self.output_port_list)):
                    sending_socket.connect(('127.0.0.1', self.output_port_list[i]))
                    sending_socket.sendto(self.response_pkt, ('127.0.0.1', self.output_port_list[i])) 
                print(f"sending response_pkt ")#:{self.response_pkt.hex()}")
    
    def is_packet_valid(self, packet):
        return packet

    def unpack_received_packet(self,cur_rtr, packet, input_port, output_port):
        input_ports = []
        outputs = [] 
        metrices = [] #link cost
        peerids = [] #dest router
        hops = [] #hop count
        
        for i in range((len(packet)-4)// 20):
            cost_and_hop = packet[(20+20*i):(24+20*i)].decode().split('--')
            input_ports.append(input_port)
            outputs.append(output_port)
            metrices.append(cost_and_hop[0])
            peerids.append(int.from_bytes(packet[(8+20*i):(12+20*i)], "big"))
            hops.append(cost_and_hop[1])
        RoutingInformation(cur_rtr, input_ports, outputs, metrices, peerids, hops, 0)
                            #Demon(routing_info)
                            #router_id, input_ports, output_port_list, metric_list, peer_rtr_id_list, hop_list


    def receive_packet(self):
        while True:
            read_socket_lis, _, _ = select.select(self.socket_list, [], [])
            for read_socket in read_socket_lis:
                for i in range(len(self.input_ports)):
                    if read_socket == self.socket_list[i]:
                        print(f'Received packet from router id : {self.peer_rtr_id_list[i]} :')
                        resp_pkt, port = self.socket_list[i].recvfrom(RECV_BUFFSIZE)
                        print("  Received response_pkt : ") #, resp_pkt.hex())

                        try:
                            self.response_msg = self.is_packet_valid(resp_pkt)
                        except Exception as e:
                            print(e)
                            print("Response Packet check has been failed.")
                            print("Discard the received response packet.\n")
                        else: 
                            self.unpack_received_packet(self.routerID, self.response_msg, self.input_ports[i], self.output_port_list[i]) 
                            for i in range((len(self.response_msg)-4)// 20):
                                print(f"destRouter = router-id-", int.from_bytes(self.response_msg[(8+20*i):(12+20*i)], "big"))
                                print(f"Next Hop : ", int.from_bytes(self.response_msg[(16+20*i):(20+20*i)], "big"))
                                print(f"cost, hop: ", self.response_msg[(20+20*i):(24+20*i)].decode())
                            


    def info_exchange_to_neighbors(self):
        try:
            while True:
                print("started")
                start = False
                self.send_packet()
                self.receive_packet()
                
                raise KeyboardInterrupt

        except KeyboardInterrupt:
            print('Keyboard Interrupted!')
        sys.exit(1)

                

def decompose_ouput_port(outputs):
         """Function for splitting output into output_port, metric, peer_rtr_id and create list of each in corresponding order"""
         #output form 
         #"peer's_input_port - metric(link cost) - peer's router id"
         #peer's_input_port is equal to current router's output_port
         splitted_lis = [outputs[i].split('-') for i in range(len(outputs))] #split by '-', lists of list 
         ports, metrices, peer_rtr_ids, hops = [], [], [], []
         for indx in range(len(splitted_lis)):
             ports.append(int(splitted_lis[indx][0]))
             metrices.append(int(splitted_lis[indx][1]))
             hops.append(int(1))
             peer_rtr_ids.append(int(splitted_lis[indx][2]))

         return [ports, metrices, peer_rtr_ids, hops]
                        
       

def main():
    config = Config(sys.argv[1])
    config.unpack()
   
    #routingTable = RoutingTable
    
    print(config)
    routing_info = RoutingInformation(int(config.params['router-id'][0]),  config.params['input-ports'], 
    decompose_ouput_port(config.params['outputs'])[0], decompose_ouput_port(config.params['outputs'])[1], decompose_ouput_port(config.params['outputs'])[2], decompose_ouput_port(config.params['outputs'])[3], 0)
    Demon(routing_info)
    
    #demon = Demon(config.params['router-id'],  config.params['input-ports'], config.params['outputs'])
    #demon.receiving_packet()
    #print('Input_port_list : ',demon.input_port_list)
    #print('Binded socket with port list : ', demon.socket_list)
    #print('Rip_response_pkt : ', demon.compose_rip_entry())


if __name__ == "__main__":
    main()