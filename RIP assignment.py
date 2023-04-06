#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
import select
import socket
import datetime 

RECV_BUFFSIZE = 1024

class Config:
    """
    Config object initialised with argument string that is the string representation
    of the config filepath
    
    for <obj> as initialised object name and <param> as the paramter in correct format
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
        if port < 1024 or port > 64000:
            return False
        else:
            return True
        
    def __isRouterIdValid(self, routerId):
        """Checks routerId is in range of 1 <= routerId <= 64000
        returns True if in range and False otherwise"""        
        if routerId < 1 or routerId > 64000:
            return False
        else:
            return True
        
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
        
      
    
class RoutingTable:
    """ Temp skeleton of routing table entry """
    def __init__(self, destRtrId, port, cost, hop, timers):
        self.destRtrId = destRtrId
        self.port = port
        self.cost = cost
        self.hop = hop
        self.timers = timers
        self.contents = self.generate_entry()

    def __str__(self):
        output = "Routing table______________________________________________________\n"
        for i in range(len(self.contents)):
            output += "|destRtrId: {0}  |  port: {1}  |  cost: {2}  |  hop : {3}  |  timers: {4}|\n".format(self.contents[i][0],
                                                                                         self.contents[i][1],
                                                                                         self.contents[i][2],
                                                                                         self.contents[i][3],
                                                                                         self.contents[i][4])
        output += '___________________________________________________________________\n'
        return output
    def generate_entry(self):
        entry_lis = []
        for i in range(len(self.destRtrId)):
            entry_lis.append([self.destRtrId[i], self.port[i], self.cost[i], self.hop, self.timers])
        return entry_lis
            
    def addEntry(self, entry):
        self.contents.append(entry)
        
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
    def __init__(self,  router_id, input_ports, output_ports):
        """Initialize Demon with input ports for creating UDP sockets 
        <input_port_list> : tuple form of ('', input port) for binding
        
        <socket_list> : list of binded sockets indexed in its corresponding input port
        """
        self.routerID = int(router_id[0])
        self.input_port_list = [('',int(input_port)) for input_port in input_ports]
        self.input_port_lis =[int(input_port) for input_port in input_ports]
        self.output_port_list, self.metric_lis, self.peer_rtr_id_lis = self.decompose_ouput_port(output_ports)
        self.socket_list = [0]*len(self.input_port_lis)
        self.entrylis = []
        self.response_pkt = self.generate_rip_res_pkt()
        print("\nRouting Information\n")
        print(RoutingTable(self.peer_rtr_id_lis, self.input_port_lis, self.metric_lis, hop = 1, timers = 0))
        self.generate_rip_res_pkt()
        self.sending_packet()
    
    def create_socket(self):
        """Creating UDP sockets and to bind one with each of sockets"""
        for i in range(len(self.input_port_list)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(self.input_port_list[i])
            self.socket_list[i]=sock
        return self.socket_list   

    def generate_rip_res_pkt(self):
        #commond header (consists of command(8bits), version(8bits), must_be_zero(16bits) = routerid)
        command, version, must_be_zero_as_rtr_id = 2, 2, self.routerID
        flatten_entry = [item for sublist in self.compose_rip_entry() for item in sublist]
        front_rtr_id, back_rtr_id = (must_be_zero_as_rtr_id&0xFF00)>>8, must_be_zero_as_rtr_id&0x00FF

        #print("flatten_entry : ", flatten_entry)
        entry_len = len(flatten_entry)
        pkt_len = 4 + entry_len
        res_pkt = bytearray(pkt_len)
        res_pkt[0], res_pkt[1], res_pkt[2], res_pkt[3] = command, version, front_rtr_id, back_rtr_id
        for i in range(entry_len):
            #print("entry component{0} : {1}".format(i, flatten_entry[i]))
            res_pkt[4+i] = flatten_entry[i]
        return res_pkt

    def decompose_ouput_port(self, output_ports):
        splitted_lis = [output_ports[i].split('-') for i in range(len(output_ports))]
        port_lis, metric_lis, peer_rtr_id_lis = [], [], []
        for indx in range(len(splitted_lis)):
            port_lis.append(int(splitted_lis[indx][0]))
            metric_lis.append(int(splitted_lis[indx][1]))
            peer_rtr_id_lis.append(int(splitted_lis[indx][2]))
        return port_lis, metric_lis, peer_rtr_id_lis
            
    def compose_rip_entry(self):
        entrylis = []
        address_family_identifier = 2
        front_addr_fam_id, back_addr_fam_id = (address_family_identifier&0xFF00)>>8, address_family_identifier&0x00FF
        for i in range(len(self.output_port_list)):
            first_peer_rtr_id, second_peer_rtr_id =(self.peer_rtr_id_lis[i]&0xFF000000)>>24, (self.peer_rtr_id_lis[i]&0x00FF0000)>>16
            third_peer_rtr_id, forth_peer_rtr_id = (self.peer_rtr_id_lis[i]&0x0000FF00)>>8, (self.peer_rtr_id_lis[i]&0x000000FF)
            first_metric, second_metric =(self.metric_lis[i]&0xFF000000)>>24, (self.metric_lis[i]&0x00FF0000)>>16
            third_metric, forth_metric = (self.metric_lis[i]&0x0000FF00)>>8, (self.metric_lis[i]&0x000000FF)
            entrylis.append([front_addr_fam_id, back_addr_fam_id, 0x00, 0x00, first_peer_rtr_id, second_peer_rtr_id, third_peer_rtr_id, forth_peer_rtr_id, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, first_metric, second_metric, third_metric, forth_metric])
        #self.entrylis = entrylis
        return entrylis

    def sending_packet(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sending_socket:
                for i in range(len(self.output_port_list)):
                    sending_socket.connect(('127.0.0.1', self.output_port_list[i]))
                    sending_socket.sendto(self.response_pkt, ('127.0.0.1', self.output_port_list[i])) 
                print(f"sending response_pkt :{self.response_pkt.hex()}")

    def receiving_packet(self):
        read_socket_lis, write_socket_lis, except_socket_lis = select.select(self.socket_list, [], [])
        for read_socket in read_socket_lis:
            for i in range(len(self.input_port_lis)):
                if read_socket == self.socket_list[i]:
                    print(f'Received packet from router id : {self.peer_rtr_id_lis[i]} :')
                    resp_pkt, port = self.socket_list[i].recvfrom(RECV_BUFFSIZE)
                    print("  Received response_pkt : ", resp_pkt.hex())
                        
                        
                 

class ManuallyExit(Exception):
   def __str__(self):
      return "Program exited"    
       

def main():
    config = Config(sys.argv[1])
    config.unpack()
   
    #routingTable = RoutingTable
    
    print(config)
    
    demon = Demon( config.params['router-id'],  config.params['input-ports'], config.params['outputs'])
    demon.create_socket()
    demon.receiving_packet()
    #print('Input_port_list : ',demon.input_port_list)
    #print('Binded socket with port list : ', demon.socket_list)
    #print('Rip_response_pkt : ', demon.compose_rip_entry())


if __name__ == "__main__":
    main()