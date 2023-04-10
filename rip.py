#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
import select
import socket
import datetime 
from threading import Timer

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
        self.rtrId = rtrId
        self.inputs = [input_port for input_port in inputs]
        self.outputs, self.metrics, self.peer_rtr_id = self.decompose_output(outputs)
        

        self.initial_info = RoutingInformation(self.rtrId, self.inputs,  self.outputs, self.metrics, self.peer_rtr_id, 0)
        self.initial_table = self.initial_info.generate_table_entry()
        self.initial_display = RoutingTable(None, self.initial_table, [], self.rtrId)
        print(f"Router ID : {self.rtrId}")
        print(self.initial_display)
    
    def decompose_output(self, outputs):
        """
        split output format by '-' and sort by each item into list
        # output format
        # peer's_input_port - metric(link cost) - peer's router id (peer's_input_port is equal to current router's output_port)
        """
        #split output by '-'
        split_output = [outputs[i].split('-') for i in range(len(outputs))] 
        
        ports, metrices, peer_rtr_ids = [], [], []
        for i in range(len(split_output)):
            ports.append(int(split_output[i][0]))
            metrices.append(int(split_output[i][1]))
            peer_rtr_ids.append(int(split_output[i][2]))

        #return three lists
        #return [ports], [metrices], [peer_rtr_ids]
        return ports, metrices, peer_rtr_ids
        
class RoutingInformation:
     def __init__(self, router_id, input_ports, output_port_list, metric_list, peer_rtr_id_list, timer):
        self.routerID = int(router_id)
        self.input_ports =[int(input_port) for input_port in input_ports]
        self.flag = 0
        self.timers = 0
        self.output_port_list = output_port_list
        self.metric_list = metric_list
        self.peer_rtr_id_list = peer_rtr_id_list
        self.new_entry = self.generate_table_entry()

     def generate_table_entry(self):
        entry = []
        for i in range(len(self.output_port_list)):
            entry.append({'router-id' : self.routerID, 
                          'dest-rtr' : self.peer_rtr_id_list[i], 
                          'input' : self.input_ports[i], 
                          'output' : self.output_port_list[i], 
                          'metric' : self.metric_list[i], 
                          'timer' : self.timers})
        return entry


class RoutingTable:
    """ Temp skeleton of routing table entry """
    def __init__(self, Router, contents, new_entry, received_from):

        
        self.router = Router
        self.contents = contents
        self.new_entry = new_entry
        self.table = self.update_entry(new_entry, received_from)
        

    def __str__(self):
        if self.router!=None :
            print(f"Router ID : {self.router.rtrId}") 
        output = "Routing table--------------------------------------------------+\n"
        for i in range(len(self.contents)):
            output += "|destRtrId: {0}  |  port: {1} (next-hop : {2})  |  Metric : {3}  |\n".format(self.contents[i]['dest-rtr'],
                                                                                         self.contents[i]['input'],
                                                                                         self.contents[i]['output'],
                                                                                         self.contents[i]['metric']
                                                                                         )
        output += '+--------------------------------------------------------------+\n'
        return output
    
    def update_entry(self, given_entry, receive_from):
        entry = self.contents + given_entry
        if self.router == None:
            return self.contents
        else :
            dest = []
            final_content = []
            link_cost = self.router.metrics[self.router.peer_rtr_id.index(receive_from)]
            for i in range(len(entry)):
                if (entry[i]['dest-rtr'] in self.router.peer_rtr_id) and (entry[i]['dest-rtr'] not in dest) :
                    dest.append(entry[i]['dest-rtr'])
                    final_content.append(entry[i])

                if (entry[i]['dest-rtr'] not in dest) and (entry[i]['dest-rtr'] != self.router.rtrId) :
                    dest.append(entry[i]['dest-rtr'])
                    entry[i]['input'] = self.router.inputs[self.router.peer_rtr_id.index(receive_from)]
                    entry[i]['output'] = self.router.outputs[self.router.peer_rtr_id.index(receive_from)]
                    entry[i]['metric'] += link_cost 
                    final_content.append(entry[i])

                if entry[i]['dest-rtr'] in dest:
                    #print(f"compare {entry[i]['metric']} and {final_content[dest.index(entry[i]['dest-rtr'])]['metric']}")
                    if (entry[i]['metric'] + link_cost) < final_content[dest.index(entry[i]['dest-rtr'])]['metric']:
                        final_content.remove(final_content[dest.index(entry[i]['dest-rtr'])])
                        dest.remove(dest[dest.index(entry[i]['dest-rtr'])])
                        entry[i]['input'] = self.router.inputs[self.router.peer_rtr_id.index(receive_from)]
                        entry[i]['output'] = self.router.outputs[self.router.peer_rtr_id.index(receive_from)]
                        entry[i]['metric'] += link_cost 
                        final_content.append(entry[i])
                        dest.append(entry[i]['dest-rtr'])
                    else :
                        pass
            self.contents = final_content
            #print("final contents ? ", self.contents)
            print(self.__str__())
            return final_content
           
     
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
    def __init__(self, Router, RoutingInformation, RoutingTable):
        """Initialize Demon with input ports for creating UDP sockets 
        <socket_list> : list of binded sockets indexed in its corresponding input port
        """
        #there are some self.xx variables that can be removed and replaced to Router.xx
        #Planning to cleaner variables when clean up codes in Demon
        self.response_msg = None
        self.poison = False
        self.router = Router
        self.currentTable = RoutingTable.table
        self.routerID = RoutingInformation.routerID
        self.input_ports = RoutingInformation.input_ports
        self.output_port_list = RoutingInformation.output_port_list
        self.metric_list = RoutingInformation.metric_list
        self.peer_rtr_id_list = RoutingInformation.peer_rtr_id_list
        self.socket_list = self.create_socket()
        self.response_pkt = None
        self.info_exchange_to_neighbors()
        
    
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

    def compose_rip_entry(self, destID, metrics):
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

        entry_bytearray = bytearray()
        address_family_identifier = 2
        must_be_zero = 0
        
        for i in range(len(destID)): #the item in range() will be replaced by lists of list entry contents
            #first 32 bits of rip entry
            entry_bytearray += address_family_identifier.to_bytes(2, 'big')
            entry_bytearray += must_be_zero.to_bytes(2, 'big')
            # second to fifth of rip entry
            entry_bytearray += destID[i].to_bytes(4, 'big')
            entry_bytearray += must_be_zero.to_bytes(4, 'big')
            entry_bytearray += must_be_zero.to_bytes(4, 'big')
            entry_bytearray += metrics[i].to_bytes(4, 'big')
        return entry_bytearray
   
    def send_packet(self):
        #Triggered update and randomization of regular update need to be implemented
        #This timer below is regular update happening at the same time (For checking purpose). ->need to be modified
        Timer(7, self.send_packet).start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sending_socket:
                for i in range(len(self.output_port_list)):
                    sending_socket.connect(('127.0.0.1', self.output_port_list[i]))
                    sending_socket.sendto(self.split_horizon(self.output_port_list[i]), ('127.0.0.1', self.output_port_list[i])) 
                print(f"sending response packet ...... ")#:{self.response_pkt.hex()}")

    def split_horizon(self, port):
        routingTable = self.currentTable
        output = []
        dest = []
        metric = []
        for i in range(len(routingTable)):
            if routingTable[i]['output'] != port:
                output.append(routingTable[i]['output'])
                dest.append(routingTable[i]['dest-rtr'])
                metric.append(routingTable[i]['metric'])

        packet = self.generate_rip_response_packet(self.compose_rip_entry(dest, metric))
        return packet
    
    def is_packet_valid(self, packet):
        """"For packet validity check"""
        # Not implemented yet
        return packet

    def unpack_received_packet(self, cur_rtr, packet, input_port, output_port, receive_from):
        input_ports = []
        outputs = [] 
        metrices = [] #link cost
        peerids = [] #dest router
        
        for i in range((len(packet)-4)// 20):
            input_ports.append(input_port)
            outputs.append(output_port)
            metrices.append(int.from_bytes(packet[(20+20*i):(24+20*i)], "big"))
            peerids.append(int.from_bytes(packet[(8+20*i):(12+20*i)], "big"))

        new = RoutingInformation(cur_rtr, input_ports, outputs, metrices, peerids, 0)
        RoutingTable(self.router, self.currentTable, new.new_entry, receive_from)
                            


    def receive_packet(self):
        while True:
            read_socket_lis, _, _ = select.select(self.socket_list, [], [])
            for read_socket in read_socket_lis:
                for i in range(len(self.input_ports)):
                    if read_socket == self.socket_list[i]:
                        print(f'\nReceived packet from router id : {self.peer_rtr_id_list[i]}')
                        resp_pkt, port = self.socket_list[i].recvfrom(RECV_BUFFSIZE)
                        #print("  Received response_pkt : ") #, resp_pkt.hex())

                        try:
                            self.response_msg = self.is_packet_valid(resp_pkt)
                        except Exception as e:
                            print(e)
                            print("Response Packet check has been failed.")
                            print("Discard the received response packet.\n")
                        else: 
                            #for checking what entries I received
                            for j in range((len(self.response_msg)-4)// 20):
                                print("----Received entries [destRtr : {0}, next-hop : {1}, metric : {2}]\n".format( int.from_bytes(self.response_msg[(8+20*j):(12+20*j)], "big"),
                                self.output_port_list[i], int.from_bytes(self.response_msg[(20+20*j):(24+20*i)], "big")))
                            self.unpack_received_packet(self.routerID, self.response_msg, self.input_ports[i], self.output_port_list[i], self.peer_rtr_id_list[i]) 
                            


    def info_exchange_to_neighbors(self):
        try:
            while True:
                print("started")
                
                self.send_packet()
                self.receive_packet()
                
                raise KeyboardInterrupt

        except KeyboardInterrupt:
            print('Keyboard Interrupted!')
        sys.exit(1)

                


                        
       

def main():
    config = Config(sys.argv[1])
    config.unpack()
    print(config)

    router = Router(int(config.params['router-id'][0]),  config.params['input-ports'], config.params['outputs'])
    routing = Demon(router, router.initial_info, router.initial_display)



if __name__ == "__main__":
    main()