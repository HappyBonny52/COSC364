import sys
import socket

def unpackConfig(config_path):
    
    """
    Function to unpack config parameters and returns them in their string representation
    
    <params> : a dict of string key and obj values of parameters that can exist in the config file.
    <req_params> : a set of strings of required parameters for the program to function properly, the
    program will terminate if any one of these parameters aren't present in the config.txt
    
    returns the array of values of <params> dict in the order of (router-id, input-ports, ouputs, timers)
    """
    
    print("Config Path: ", config_path)
    
    config_file = open(config_path, "r")
    config = config_file.read().split('\n')
    config_file.close()

    params = {
        'router-id':None,
        'input-ports':None,
        'outputs':None,
        'timers':None
    }
    req_params = {'router-id', 'input-ports', 'outputs'}
    
    for line in config:
        
        if line.split(' ', 1)[0] in params:
            
            try:
                param = line.split(' ', 1)[0]
                value = line.split(' ', 1)[1].replace(' ', '')
                
                if not value:
                    raise IndexError
                
                params[param] = list(x.strip() for x in value.split(','))
                
            except(IndexError):
                print("PARAMETER <{}> MISSING VALUES. PLEglobal variables or in mainASE CHECK CONFIG".format(param))
                sys.exit(1)
                
    for param in params:
        if params[param] == None and param in req_params:
            raise TypeError("PARAMETER <{}> MISSING. PLEASE CHECK CONFIG".format(param))
        
    return params.values()
    
class RoutingTable:
    """ Temp skeleton of routing table """
    def __init__(self, destAddress, nextAddress, flag, timers, metric=1):
        self.destAddress = destAddress
        self.metric = metric
        self.nextAddress = nextAddress
        self.flag = flag
        self.timers = timers
    def __str__(self):
        return "destAddress: {0}\nmetric: {1}\nnextAddress: {2}\nflag : {3}\ntimers: {4}"    
    
    
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

def main():
    config_path = sys.argv[1]
    router_id, input_ports, outputs, timers = unpackConfig(sys.argv[1]);
    print(router_id, input_ports, outputs, timers)

main()