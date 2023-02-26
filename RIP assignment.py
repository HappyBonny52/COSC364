import sys

def unpackConfig(config_path):
    
    """
    Function to unpack config parameters and returns them in their string representation
    
    <params> : a dict of string key and obj values of parameters that can exist in the config file.
    <req_params> : a set of strings of required parameters for the progra to function properly, the
    pr
    
    <req_params> is 
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
    
def main():
    config_path = sys.argv[1]
    router_id, input_ports, outputs, timers = unpackConfig(sys.argv[1]);
    print(router_id, input_ports, outputs, timers)

main()